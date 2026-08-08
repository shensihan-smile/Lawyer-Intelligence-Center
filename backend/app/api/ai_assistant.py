"""AI 助手 API — 智能起草文书、合同条款审查、法律检索"""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services import ai_client

router = APIRouter()

AI_MODEL = "glm-4.7-flash"

# ========== 功能 System Prompts ==========

SYSTEM_PROMPTS = {
    "draft": (
        "你是一位资深诉讼律师和法律文书起草专家。"
        "请根据用户描述的案情，起草一份法律文书初稿。\n\n"
        "规则：\n"
        "1. 文书格式规范，符合中国法院文书格式标准\n"
        "2. 包含「当事人信息」「事实与理由」「诉讼请求」等标准结构\n"
        "3. 事实陈述清晰，法律依据充分\n"
        "4. 使用法律专业术语，但保持可读性\n"
        "5. 需要用户补充的信息用{委托人}{对方当事人}{受理法院}{案由}{当前日期}等占位符标注，不得编造\n"
        "6. 文书末尾附上「注意事项」提示用户核实关键信息\n\n"
        "如果用户未明确文书类型（起诉状/答辩状/代理词等），请先询问。"
        "输出纯文本，用空行和编号分节，勿用 Markdown 符号。"
    ),
    "review": (
        "你是一位资深商事合同审查律师。请审查用户提供的合同条款，逐条识别法律风险并给出专业建议。\n\n"
        "输出格式：\n"
        "## 🔴 高风险\n"
        "- 条款原文：「引述原文」\n"
        "- 风险分析：...\n"
        "- 修改建议：「给出可直接替换的条款文本」\n"
        "- 谈判策略：...\n\n"
        "## 🟡 中风险\n"
        "（同上格式）\n\n"
        "## 🟢 建议优化\n"
        "（同上格式）\n\n"
        "## 📋 审查总结\n"
        "（2-3句话总结整体风险和核心建议）\n\n"
        "注意：对每个风险点给出可操作的修改方案，不仅指出问题更要给出解决办法。"
        "若条款无重大风险，明确写「未发现重大法律风险」。"
        "输出纯文本，勿用 Markdown 符号。"
    ),
    "research": (
        "你是一位法律研究专家。请根据用户的问题，梳理相关的法律规定和司法观点。\n\n"
        "输出格式：\n"
        "## 📜 相关法条\n"
        "- 《XX法》第X条：条文主要内容概述\n"
        "- 司法解释：名称+关键条款内容概述\n\n"
        "## ⚖️ 裁判观点\n"
        "- 主流观点：...（注明来源法院或案例类型）\n"
        "- 争议观点（如存在）：...\n\n"
        "## 💡 实务建议\n"
        "基于以上法律依据，给出2-3条具体操作建议\n\n"
        "注意：引用法条应准确完整，不得编造条文号；"
        "不确定时标注「此为检索方向建议，需以官方文本核实为准」。"
        "输出纯文本，用空行分节，勿用 Markdown 符号。"
    ),
    "general": (
        "你是律师智能中心内置的 AI 法律助手。请专业、简洁地回答用户的法律问题。"
        "不确定时明确说明，不要编造。"
    ),
}

MODE_CONFIG = {
    "draft":    {"temperature": 0.3, "max_tokens": 4096},
    "review":   {"temperature": 0.2, "max_tokens": 4096},
    "research": {"temperature": 0.1, "max_tokens": 2048},
    "general":  {"temperature": 0.4, "max_tokens": 2048},
}


# ========== 请求/响应模型 ==========

class ChatMsg(BaseModel):
    role: str          # "user" | "assistant"
    content: str


class ChatReq(BaseModel):
    mode: str = "general"        # draft | review | research | general
    messages: List[ChatMsg] = []
    temperature: Optional[float] = None


# ========== API 端点 ==========

@router.post("/chat")
def ai_chat(
    data: ChatReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 助手对话（一次性返回）

    请求: {mode: "draft"|"review"|"research", messages: [{role, content}]}
    返回: {reply: str, mode: str}
    """
    if not ai_client.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI 服务未配置，请在 backend/.env 中设置 OPENAI_API_KEY",
        )

    # 获取模式配置
    cfg = MODE_CONFIG.get(data.mode, MODE_CONFIG["general"])
    system_content = SYSTEM_PROMPTS.get(data.mode, SYSTEM_PROMPTS["general"])

    # 构造消息列表（system prompt + 最近16条对话）
    full_messages = [{"role": "system", "content": system_content}]
    for m in data.messages[-16:]:
        content = m.content[:6000] if m.content else ""
        if content:
            full_messages.append({"role": m.role, "content": content})

    temperature = data.temperature if data.temperature is not None else cfg["temperature"]

    reply = ai_client.chat_multi(
        full_messages,
        temperature=temperature,
        max_tokens=cfg["max_tokens"],
        model=AI_MODEL,
    )

    return {"reply": reply, "mode": data.mode}


@router.post("/stream")
def ai_chat_stream(
    data: ChatReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 助手对话（SSE 流式返回）

    请求格式同 /chat，返回 SSE 事件流：
    data: {"delta": "文本..."}
    data: [DONE]
    """
    if not ai_client.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI 服务未配置，请在 backend/.env 中设置 OPENAI_API_KEY",
        )

    cfg = MODE_CONFIG.get(data.mode, MODE_CONFIG["general"])
    system_content = SYSTEM_PROMPTS.get(data.mode, SYSTEM_PROMPTS["general"])

    full_messages = [{"role": "system", "content": system_content}]
    for m in data.messages[-16:]:
        content = m.content[:6000] if m.content else ""
        if content:
            full_messages.append({"role": m.role, "content": content})

    temperature = data.temperature if data.temperature is not None else cfg["temperature"]
    max_tokens = cfg["max_tokens"]

    def generate():
        try:
            for delta in ai_client.chat_stream(
                full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=AI_MODEL,
            ):
                if delta:
                    yield "data: " + json.dumps({"delta": delta}, ensure_ascii=False) + "\n\n"
        except Exception as e:
            print(f"[AI] SSE 流式中断: {e}")
            yield "data: " + json.dumps({"error": "生成中断，请重试"}, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/status")
def ai_status(current_user: User = Depends(get_current_user)):
    """检查 AI 服务是否可用"""
    return {
        "available": ai_client.is_available(),
        "model": ai_client.MODEL if ai_client.is_available() else "",
    }
