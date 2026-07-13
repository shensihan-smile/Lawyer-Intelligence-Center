"""AI 客户端服务（OpenAI API 封装）"""
import os
import json
from openai import OpenAI


# 从环境变量读取 API Key
# 用户需设置环境变量：OPENAI_API_KEY=sk-xxxx
# 或在项目根目录创建 .env 文件
API_KEY = os.getenv("OPENAI_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # 可选：自定义 API 地址
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # 使用性价比高的模型

_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    """获取 AI 客户端实例"""
    global _client
    if API_KEY and _client is None:
        kwargs = {"api_key": API_KEY}
        if BASE_URL:
            kwargs["base_url"] = BASE_URL
        _client = OpenAI(**kwargs)
    return _client


def is_available() -> bool:
    """检查 AI 服务是否可用"""
    return bool(API_KEY)


def chat(prompt: str, system_message: str = "", temperature: float = 0.3) -> str:
    """发送对话请求，返回 AI 回复文本

    Args:
        prompt: 用户消息
        system_message: 系统提示词（设定 AI 行为）
        temperature: 温度参数（0=最确定，1=最随机）

    Returns:
        AI 回复内容，失败返回空字符串
    """
    client = _get_client()
    if not client:
        return ""

    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"[AI] 调用失败: {e}")
        return ""
