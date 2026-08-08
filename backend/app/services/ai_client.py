"""AI 客户端服务（OpenAI API 封装）

支持 OpenAI 兼容的 API 服务，包括：
- OpenAI 官方 API
- 智谱 AI (Zhipu/GLM)：设置 OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
- DeepSeek、通义千问等任何 OpenAI 兼容服务
"""
import os
import re
import json
from openai import OpenAI


# 从环境变量读取 API Key
API_KEY = os.getenv("OPENAI_API_KEY", "")
# 自定义 API 地址（智谱等 OpenAI 兼容服务）
BASE_URL = os.getenv("OPENAI_BASE_URL", "")
# 模型名称（默认 glm-4.6v-flash，智谱免费多模态模型）
MODEL = os.getenv("OPENAI_MODEL", "glm-4.6v-flash")

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


def chat(prompt: str, system_message: str = "", temperature: float = 0.3,
         max_tokens: int = 2048, model: str = "") -> str:
    """发送对话请求，返回 AI 回复文本

    Args:
        prompt: 用户消息
        system_message: 系统提示词（设定 AI 行为）
        temperature: 温度参数（0=最确定，1=最随机）
        max_tokens: 最大输出 token 数（默认 2048）
        model: 模型名称，为空则使用默认 MODEL

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
            model=model or MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"[AI] 调用失败: {e}")
        return ""


def chat_multi(messages: list, temperature: float = 0.3,
               max_tokens: int = 4096, model: str = "") -> str:
    """多轮对话请求（messages 已包含 system prompt）

    Args:
        messages: [{role, content}, ...] 格式的消息列表
        temperature: 温度参数
        max_tokens: 最大输出 token 数
        model: 模型名称，为空则使用默认 MODEL

    Returns:
        AI 回复内容，失败返回空字符串
    """
    client = _get_client()
    if not client:
        return ""

    try:
        response = client.chat.completions.create(
            model=model or MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"[AI] 调用失败: {e}")
        return ""


def chat_stream(messages: list, temperature: float = 0.3,
                max_tokens: int = 4096, model: str = ""):
    """流式对话请求，逐块返回 AI 回复文本

    Args:
        messages: [{role, content}, ...] 格式的消息列表（含 system prompt）
        temperature: 温度参数
        max_tokens: 最大输出 token 数
        model: 模型名称，为空则使用默认 MODEL

    Yields:
        文本增量；失败时抛出异常（由调用者处理）
    """
    client = _get_client()
    if not client:
        raise RuntimeError("AI 客户端未初始化，请检查 OPENAI_API_KEY 配置")

    stream = client.chat.completions.create(
        model=model or MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


def chat_json(prompt: str, system_message: str = "",
              temperature: float = 0.1, model: str = "") -> dict:
    """发送对话请求，从回复中提取 JSON 对象

    用于需要结构化输出的场景（如信息提取）。
    会自动处理 LLM 输出中的 markdown 代码块包裹。

    Args:
        prompt: 用户消息
        system_message: 系统提示词
        temperature: 温度参数（提取类任务建议 0.1）
        model: 模型名称，为空则使用默认 MODEL

    Returns:
        解析后的 dict，失败返回空 dict {}
    """
    response = chat(prompt, system_message=system_message,
                    temperature=temperature, max_tokens=2048, model=model)

    if not response:
        return {}

    # 尝试直接解析
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试从大括号包裹的文本中提取
    m = re.search(r'\{[\s\S]*\}', response)
    if m:
        try:
            return json.loads(m.group(0).strip())
        except json.JSONDecodeError:
            pass

    print(f"[AI] JSON 解析失败，原始响应: {response[:300]}")
    return {}
