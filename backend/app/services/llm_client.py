"""
LLM Provider 抽象层
提供统一的函数接口，屏蔽 DashScope（OpenAI SDK）和 Gemini（原生 SDK）的差异。
Service 层统一使用 OpenAI 格式 messages，GeminiProvider 内部做转换。
"""
import json
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Optional

from app.config import settings

logger = logging.getLogger(__name__)


# ── 数据类 ──────────────────────────────────────────────

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON string


@dataclass
class ChatResponse:
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None


# ── 抽象基类 ────────────────────────────────────────────

class BaseLLMProvider(ABC):
    @abstractmethod
    def chat(self, model: str, messages: list[dict], **kwargs) -> ChatResponse:
        ...

    @abstractmethod
    async def achat(self, model: str, messages: list[dict], **kwargs) -> ChatResponse:
        ...

    @abstractmethod
    def chat_stream(self, model: str, messages: list[dict], **kwargs) -> Iterator[str]:
        ...


# ── DashScope Provider（OpenAI SDK）──────────────────────

class DashScopeProvider(BaseLLMProvider):
    def __init__(self):
        from openai import OpenAI, AsyncOpenAI
        self._sync = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
        )
        self._async = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
        )

    def chat(self, model, messages, **kwargs):
        tools = kwargs.pop("tools", None)
        tool_choice = kwargs.pop("tool_choice", None)
        call_kwargs = dict(model=model, messages=messages, **kwargs)
        if tools:
            call_kwargs["tools"] = tools
        if tool_choice:
            call_kwargs["tool_choice"] = tool_choice

        resp = self._sync.chat.completions.create(**call_kwargs)
        return self._to_response(resp)

    async def achat(self, model, messages, **kwargs):
        tools = kwargs.pop("tools", None)
        tool_choice = kwargs.pop("tool_choice", None)
        call_kwargs = dict(model=model, messages=messages, **kwargs)
        if tools:
            call_kwargs["tools"] = tools
        if tool_choice:
            call_kwargs["tool_choice"] = tool_choice

        resp = await self._async.chat.completions.create(**call_kwargs)
        return self._to_response(resp)

    def chat_stream(self, model, messages, **kwargs):
        kwargs.pop("tools", None)
        kwargs.pop("tool_choice", None)
        resp = self._sync.chat.completions.create(
            model=model, messages=messages, stream=True, **kwargs
        )
        for chunk in resp:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @staticmethod
    def _to_response(resp) -> ChatResponse:
        msg = resp.choices[0].message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                )
                for tc in msg.tool_calls
            ]
        return ChatResponse(content=msg.content, tool_calls=tool_calls)


# ── Gemini Provider（原生 google.genai SDK）──────────────

class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        from google import genai
        from google.genai import types

        http_options = types.HttpOptions(timeout=30_000)
        socks5 = settings.gemini_sock5_proxy
        http_proxy = settings.gemini_http_proxy
        api_key = settings.gemini_api_key

        logger.info(
            "[Gemini] 初始化: api_key=%s, socks5_proxy=%s, http_proxy=%s",
            f"{api_key[:8]}***" if api_key else "(空)",
            socks5 or "(无)",
            http_proxy or "(无)",
        )

        if socks5 or http_proxy:
            if socks5:
                http_options.client_args = {"proxy": socks5}
            if http_proxy:
                http_options.async_client_args = {"proxy": http_proxy}

        self._client = genai.Client(
            vertexai=False,
            api_key=api_key,
            http_options=http_options,
        )
        logger.info("[Gemini] Client 创建成功")

    # ── 消息格式转换 ──

    @staticmethod
    def _convert_messages(messages: list[dict]):
        """
        OpenAI 格式 messages → (system_instruction, contents)
        - system → system_instruction 字符串
        - user → Content(role="user")
        - assistant → Content(role="model")
        - assistant with tool_calls → Content(role="model") with FunctionCall parts
        - tool → Content(role="user") with FunctionResponse part
        """
        from google.genai import types

        system_parts = []
        contents = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content") or ""

            if role == "system":
                system_parts.append(content)

            elif role == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=content)],
                ))

            elif role == "assistant":
                parts = []
                if content:
                    parts.append(types.Part.from_text(text=content))
                # 处理 tool_calls
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        args = fn.get("arguments", "{}")
                        if isinstance(args, str):
                            args = json.loads(args)
                        parts.append(types.Part.from_function_call(
                            name=fn.get("name", ""),
                            args=args,
                        ))
                if parts:
                    contents.append(types.Content(role="model", parts=parts))

            elif role == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                # 需要从之前的 assistant 消息中找到对应的函数名
                fn_name = GeminiProvider._find_fn_name(messages, tool_call_id)
                result = content
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except (json.JSONDecodeError, TypeError):
                        result = {"result": result}
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name=fn_name,
                        response=result,
                    )],
                ))

        system_instruction = "\n\n".join(system_parts) if system_parts else None
        return system_instruction, contents

    @staticmethod
    def _find_fn_name(messages: list[dict], tool_call_id: str) -> str:
        """从消息历史中根据 tool_call_id 找到对应的函数名"""
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    if tc.get("id") == tool_call_id:
                        return tc.get("function", {}).get("name", "")
        return ""

    @staticmethod
    def _convert_tools(tools: list[dict]) -> list:
        """OpenAI tools format → Gemini FunctionDeclaration format"""
        from google.genai import types

        declarations = []
        for tool in tools:
            if tool.get("type") != "function":
                continue
            fn = tool["function"]
            params = fn.get("parameters")
            # 转为 Gemini Schema
            schema = None
            if params:
                schema = GeminiProvider._convert_schema(params)
            declarations.append(types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=schema,
            ))
        return [types.Tool(function_declarations=declarations)] if declarations else []

    @staticmethod
    def _convert_schema(schema: dict):
        """递归将 JSON Schema 转为 Gemini Schema"""
        from google.genai import types

        schema_type = schema.get("type", "object")
        type_map = {
            "string": types.Type.STRING,
            "integer": types.Type.INTEGER,
            "number": types.Type.NUMBER,
            "boolean": types.Type.BOOLEAN,
            "array": types.Type.ARRAY,
            "object": types.Type.OBJECT,
        }

        kwargs = {
            "type": type_map.get(schema_type, types.Type.STRING),
        }

        if "description" in schema:
            kwargs["description"] = schema["description"]

        if schema_type == "object" and "properties" in schema:
            kwargs["properties"] = {
                k: GeminiProvider._convert_schema(v)
                for k, v in schema["properties"].items()
            }
            if "required" in schema:
                kwargs["required"] = schema["required"]

        if schema_type == "array" and "items" in schema:
            kwargs["items"] = GeminiProvider._convert_schema(schema["items"])

        return types.Schema(**kwargs)

    def _build_config(self, **kwargs):
        """构建 Gemini GenerateContentConfig"""
        from google.genai import types

        config_kwargs = {}
        if "temperature" in kwargs:
            config_kwargs["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            config_kwargs["max_output_tokens"] = kwargs["max_tokens"]

        tools = kwargs.get("tools")
        if tools:
            config_kwargs["tools"] = self._convert_tools(tools)

        tool_choice = kwargs.get("tool_choice")
        if tool_choice == "auto":
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            )

        return types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    def _to_response(self, resp) -> ChatResponse:
        """Gemini response → ChatResponse"""
        content = None
        tool_calls = None

        if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
            text_parts = []
            tc_list = []
            for part in resp.candidates[0].content.parts:
                if part.text:
                    text_parts.append(part.text)
                if part.function_call:
                    fc = part.function_call
                    tc_list.append(ToolCall(
                        id=fc.id if hasattr(fc, 'id') and fc.id else f"call_{fc.name}",
                        name=fc.name,
                        arguments=json.dumps(dict(fc.args) if fc.args else {}, ensure_ascii=False),
                    ))

            if text_parts:
                content = "".join(text_parts)
            if tc_list:
                tool_calls = tc_list

        return ChatResponse(content=content, tool_calls=tool_calls)

    def chat(self, model, messages, **kwargs):
        system_instruction, contents = self._convert_messages(messages)
        config = self._build_config(**kwargs)

        call_kwargs = {"model": model, "contents": contents}
        if system_instruction:
            if config is None:
                from google.genai import types
                config = types.GenerateContentConfig(system_instruction=system_instruction)
            else:
                config.system_instruction = system_instruction
        if config:
            call_kwargs["config"] = config

        logger.info("[Gemini] chat 请求: model=%s, messages=%d条", model, len(messages))
        try:
            resp = self._client.models.generate_content(**call_kwargs)
        except Exception as e:
            logger.error(
                "[Gemini] chat 失败: model=%s, error_type=%s, error=%s",
                model, type(e).__name__, e,
                exc_info=True,
            )
            raise
        logger.info("[Gemini] chat 成功: model=%s", model)
        return self._to_response(resp)

    async def achat(self, model, messages, **kwargs):
        system_instruction, contents = self._convert_messages(messages)
        config = self._build_config(**kwargs)

        call_kwargs = {"model": model, "contents": contents}
        if system_instruction:
            if config is None:
                from google.genai import types
                config = types.GenerateContentConfig(system_instruction=system_instruction)
            else:
                config.system_instruction = system_instruction
        if config:
            call_kwargs["config"] = config

        logger.info("[Gemini] achat 请求: model=%s, messages=%d条", model, len(messages))
        try:
            resp = await self._client.aio.models.generate_content(**call_kwargs)
        except Exception as e:
            logger.error(
                "[Gemini] achat 失败: model=%s, error_type=%s, error=%s",
                model, type(e).__name__, e,
                exc_info=True,
            )
            raise
        logger.info("[Gemini] achat 成功: model=%s", model)
        return self._to_response(resp)

    def chat_stream(self, model, messages, **kwargs):
        kwargs.pop("tools", None)
        kwargs.pop("tool_choice", None)
        system_instruction, contents = self._convert_messages(messages)
        config = self._build_config(**kwargs)

        call_kwargs = {"model": model, "contents": contents}
        if system_instruction:
            if config is None:
                from google.genai import types
                config = types.GenerateContentConfig(system_instruction=system_instruction)
            else:
                config.system_instruction = system_instruction
        if config:
            call_kwargs["config"] = config

        for chunk in self._client.models.generate_content_stream(**call_kwargs):
            if chunk.text:
                yield chunk.text


# ── 路由与缓存 ──────────────────────────────────────────

_MODULE_OVERRIDE = {
    "memoir": "llm_provider_memoir",
    "summary": "llm_provider_summary",
    "topic": "llm_provider_topic",
    "profile": "llm_provider_profile",
    "intervention": "llm_provider_intervention",
}

_providers: dict[str, BaseLLMProvider] = {}
_lock = threading.Lock()


def _resolve_provider(module: str) -> str:
    """解析模块应该使用的 provider 名称：模块级 override > 全局默认"""
    override_field = _MODULE_OVERRIDE.get(module)
    if override_field:
        override_value = getattr(settings, override_field, "")
        if override_value:
            return override_value
    return settings.llm_provider_default


def _get_provider_config(provider: str) -> tuple[str, str]:
    """返回 provider 的 (model_main, model_fast)"""
    if provider == "gemini":
        return settings.gemini_model, settings.gemini_model_fast
    return settings.dashscope_model, settings.dashscope_model_fast


def _get_provider_instance(name: str) -> BaseLLMProvider:
    """获取或创建 provider 实例（带缓存和锁）"""
    with _lock:
        if name not in _providers:
            if name == "gemini":
                _providers[name] = GeminiProvider()
            else:
                _providers[name] = DashScopeProvider()
        return _providers[name]


def get_model(module: str, fast: bool = False) -> str:
    """获取模块对应的模型名称"""
    provider = _resolve_provider(module)
    model_main, model_fast = _get_provider_config(provider)
    return model_fast if fast else model_main


# ── 统一调用接口 ────────────────────────────────────────

def llm_chat(module: str, *, messages: list[dict], fast: bool = False, **kwargs) -> ChatResponse:
    """同步调用 LLM"""
    provider_name = _resolve_provider(module)
    provider = _get_provider_instance(provider_name)
    model = get_model(module, fast=fast)
    return provider.chat(model, messages, **kwargs)


async def llm_achat(module: str, *, messages: list[dict], fast: bool = False, **kwargs) -> ChatResponse:
    """异步调用 LLM"""
    provider_name = _resolve_provider(module)
    provider = _get_provider_instance(provider_name)
    model = get_model(module, fast=fast)
    return await provider.achat(model, messages, **kwargs)


def llm_chat_stream(module: str, *, messages: list[dict], fast: bool = False, **kwargs) -> Iterator[str]:
    """流式调用 LLM"""
    provider_name = _resolve_provider(module)
    provider = _get_provider_instance(provider_name)
    model = get_model(module, fast=fast)
    return provider.chat_stream(model, messages, **kwargs)
