import base64
import os
import re
from collections.abc import AsyncIterator

import google.generativeai as genai
import httpx
from openai import OpenAI

from backend.config import settings
from backend.templates import SYSTEM_PROMPT, format_user_prompt

SUPPORTED_PROVIDERS = {"gemini", "openai", "claude", "deepseek", "mistral", "kimi", "groq", "ollama"}
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OPENAI_REASONING_MODELS = {"o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o4-mini"}
_THINK_PATTERN = re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE)


def _http_client() -> httpx.Client:
    return httpx.Client(verify=settings.verify_ssl)


def _clean_response(text: str | None) -> str:
    return _THINK_PATTERN.sub("", text or "").strip()


def _provider_key(provider: str, api_key: str = "") -> str:
    if api_key:
        return api_key
    env_names = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "kimi": "KIMI_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    return os.getenv(env_names.get(provider, ""), "").strip()


def _missing_key_message(provider: str) -> str:
    labels = {
        "gemini": "Gemini",
        "openai": "OpenAI",
        "claude": "Anthropic",
        "deepseek": "DeepSeek",
        "mistral": "Mistral",
        "kimi": "Kimi",
        "groq": "Groq",
    }
    return f"Please enter your {labels.get(provider, provider)} API key in the sidebar or configure it in the backend environment."


def _provider_error(provider: str) -> str:
    return f"{provider} Error: Provider request failed. Check the provider configuration and try again."


def _openai_client(api_key: str, base_url: str | None = None) -> OpenAI:
    kwargs = {"api_key": api_key, "http_client": _http_client()}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _build_history_messages(history: list | None, system_prompt: str, user_prompt: str) -> list:
    messages = [{"role": "system", "content": system_prompt}]
    for msg in (history or [])[-settings.max_history_messages:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})
    return messages


def _sanitize_utf8(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _decode_data_url(image_data: str) -> tuple[str, bytes, str] | None:
    if "," not in image_data:
        return None
    header, encoded = image_data.split(",", 1)
    mime_type = header.split(":")[1].split(";")[0]
    return mime_type, base64.b64decode(encoded), encoded


def generate_tests_gemini(
    source_code: str,
    api_key: str,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.6,
    image_data: str | None = None,
    history: list | None = None,
) -> str:
    api_key = _provider_key("gemini", api_key)
    if not api_key:
        return _missing_key_message("gemini")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_PROMPT)
        config = genai.GenerationConfig(temperature=temperature)
        gemini_history = []
        for msg in (history or [])[-settings.max_history_messages:]:
            role = "user" if msg.get("role") == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg.get("content", "")]})

        content = [format_user_prompt(source_code)]
        if image_data:
            decoded = _decode_data_url(image_data)
            if decoded:
                mime_type, img_bytes, _ = decoded
                content.append({"mime_type": mime_type, "data": img_bytes})

        if gemini_history:
            response = model.start_chat(history=gemini_history).send_message(content, generation_config=config)
        else:
            response = model.generate_content(content, generation_config=config)
        return _clean_response(response.text)
    except Exception:
        return _provider_error("Gemini")


def generate_tests_openai(
    source_code: str,
    api_key: str,
    model_name: str = "gpt-4o",
    temperature: float = 0.6,
    image_data: str | None = None,
    history: list | None = None,
) -> str:
    api_key = _provider_key("openai", api_key)
    if not api_key:
        return _missing_key_message("openai")
    try:
        client = _openai_client(api_key=api_key)
        user_content = [{"type": "text", "text": format_user_prompt(source_code)}]
        if image_data:
            user_content.append({"type": "image_url", "image_url": {"url": image_data}})

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in (history or [])[-settings.max_history_messages:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_content})

        params = {"model": model_name, "messages": messages}
        if model_name not in _OPENAI_REASONING_MODELS:
            params["temperature"] = temperature
        response = client.chat.completions.create(**params)
        return _clean_response(response.choices[0].message.content)
    except Exception:
        return _provider_error("OpenAI")


def generate_tests_claude(
    source_code: str,
    api_key: str,
    model_name: str = "claude-opus-4-7",
    temperature: float = 0.6,
    image_data: str | None = None,
    history: list | None = None,
) -> str:
    api_key = _provider_key("claude", api_key)
    if not api_key:
        return _missing_key_message("claude")
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, http_client=_http_client())
        user_content = [{"type": "text", "text": format_user_prompt(source_code)}]
        if image_data:
            decoded = _decode_data_url(image_data)
            if decoded:
                mime_type, _, encoded = decoded
                user_content.append({"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": encoded}})

        claude_messages = []
        for msg in (history or [])[-settings.max_history_messages:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in {"user", "assistant"} and content:
                claude_messages.append({"role": role, "content": content})
        claude_messages.append({"role": "user", "content": user_content})
        response = client.messages.create(
            model=model_name,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=claude_messages,
            temperature=temperature,
        )
        return _clean_response(response.content[0].text)
    except Exception:
        return _provider_error("Claude")


def generate_tests_openai_compatible(
    provider: str,
    source_code: str,
    api_key: str,
    model_name: str,
    temperature: float,
    base_url: str,
    history: list | None = None,
) -> str:
    api_key = _provider_key(provider, api_key)
    if not api_key:
        return _missing_key_message(provider)
    try:
        system_prompt = _sanitize_utf8(SYSTEM_PROMPT) if provider == "kimi" else SYSTEM_PROMPT
        user_prompt = _sanitize_utf8(format_user_prompt(source_code)) if provider == "kimi" else format_user_prompt(source_code)
        client = _openai_client(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model_name,
            messages=_build_history_messages(history, system_prompt, user_prompt),
            temperature=temperature,
        )
        return _clean_response(response.choices[0].message.content)
    except Exception:
        return _provider_error(provider.title())


def generate_tests_ollama(
    source_code: str,
    api_key: str = "",
    model_name: str = "llama3.2",
    temperature: float = 0.6,
    history: list | None = None,
    image_data: str | None = None,
) -> str:
    try:
        client = _openai_client(api_key="ollama", base_url=f"{OLLAMA_BASE_URL}/v1")
        response = client.chat.completions.create(
            model=model_name,
            messages=_build_history_messages(history, SYSTEM_PROMPT, format_user_prompt(source_code)),
            temperature=temperature,
        )
        return _clean_response(response.choices[0].message.content)
    except Exception:
        return (
            "Ollama Error: Could not reach Ollama.\n\n"
            "Ollama is not running or not installed.\n\n"
            "macOS:\n```bash\nbrew install ollama\nollama serve\n```\n\n"
            f"Pull a model: `ollama pull {model_name}`"
        )


def generate_tests(
    provider: str,
    message: str,
    api_key: str = "",
    model_name: str = "",
    temperature: float = 0.6,
    image_data: str | None = None,
    history: list | None = None,
) -> str:
    if provider not in SUPPORTED_PROVIDERS:
        return f"Unknown provider: {provider}"
    defaults = {
        "gemini": "gemini-2.5-flash",
        "openai": "gpt-4o",
        "claude": "claude-opus-4-7",
        "deepseek": "deepseek-chat",
        "mistral": "mistral-large-latest",
        "kimi": "kimi-k2.6",
        "groq": "llama-3.3-70b-versatile",
        "ollama": "llama3.2",
    }
    model = model_name or defaults[provider]
    if provider == "gemini":
        return generate_tests_gemini(message, api_key, model, temperature, image_data, history)
    if provider == "openai":
        return generate_tests_openai(message, api_key, model, temperature, image_data, history)
    if provider == "claude":
        return generate_tests_claude(message, api_key, model, temperature, image_data, history)
    if provider == "deepseek":
        return generate_tests_openai_compatible(provider, message, api_key, model, temperature, "https://api.deepseek.com", history)
    if provider == "mistral":
        return generate_tests_openai_compatible(provider, message, api_key, model, temperature, "https://api.mistral.ai/v1", history)
    if provider == "kimi":
        return generate_tests_openai_compatible(provider, message, api_key, model, temperature, "https://api.moonshot.ai/v1", history)
    if provider == "groq":
        return generate_tests_openai_compatible(provider, message, api_key, model, temperature, "https://api.groq.com/openai/v1", history)
    return generate_tests_ollama(message, api_key, model, temperature, history, image_data)


def generate_image_openai(prompt: str, api_key: str) -> str:
    api_key = _provider_key("openai", api_key)
    if not api_key:
        return _missing_key_message("openai")
    try:
        client = _openai_client(api_key=api_key)
        response = client.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024", quality="standard", n=1)
        return f"![Generated Image]({response.data[0].url})"
    except Exception:
        return "Image Generation Error: Provider request failed. Check the provider configuration and try again."


def generate_image_gemini(prompt: str, api_key: str, model_name: str = "gemini-2.0-flash-preview-image-generation") -> str:
    api_key = _provider_key("gemini", api_key)
    if not api_key:
        return _missing_key_message("gemini")
    try:
        from google.generativeai import types as gtypes

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt, generation_config=gtypes.GenerationConfig(response_modalities=["IMAGE", "TEXT"]))
        for part in response.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                img_b64 = base64.b64encode(part.inline_data.data).decode()
                return f"![Generated Image](data:{part.inline_data.mime_type};base64,{img_b64})"
        return "Gemini returned no image. Try a different prompt or model."
    except Exception:
        return "Gemini Image Generation Error: Provider request failed. Check the provider configuration and try again."


def generate_image(prompt: str, provider: str = "openai", model_name: str = "", api_key: str = "") -> str:
    if provider == "gemini":
        return generate_image_gemini(prompt, api_key, model_name or "gemini-2.0-flash-preview-image-generation")
    if provider == "openai":
        return generate_image_openai(prompt, api_key)
    return "Image generation is available only with OpenAI or Gemini."


def get_ollama_models() -> list[str]:
    try:
        with _http_client() as client:
            response = client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            response.raise_for_status()
            return [model["name"] for model in response.json().get("models", [])]
    except Exception:
        return []


async def _stream_openai_compatible(client, model_name, messages, temperature, skip_temperature=False) -> AsyncIterator[str]:
    params = {"model": model_name, "messages": messages, "stream": True}
    if not skip_temperature:
        params["temperature"] = temperature
    response = client.chat.completions.create(**params)

    inside_think = False
    buffer = ""
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            buffer += token
            if not inside_think and "<think>" in buffer.lower():
                index = buffer.lower().index("<think>")
                if index > 0:
                    yield buffer[:index]
                buffer = buffer[index:]
                inside_think = True
            if inside_think:
                if "</think>" in buffer.lower():
                    index = buffer.lower().index("</think>") + len("</think>")
                    buffer = buffer[index:].lstrip()
                    inside_think = False
                continue
            if buffer:
                yield buffer
                buffer = ""
    if buffer and not inside_think:
        yield buffer


async def stream_tests_gemini(source_code: str, api_key: str, model_name: str, temperature: float, image_data: str | None, history: list | None):
    response = generate_tests_gemini(source_code, api_key, model_name, temperature, image_data, history)
    yield response


async def stream_tests_openai(source_code: str, api_key: str, model_name: str, temperature: float, image_data: str | None, history: list | None):
    api_key = _provider_key("openai", api_key)
    if not api_key:
        yield _missing_key_message("openai")
        return
    try:
        client = _openai_client(api_key=api_key)
        user_content = [{"type": "text", "text": format_user_prompt(source_code)}]
        if image_data:
            user_content.append({"type": "image_url", "image_url": {"url": image_data}})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in (history or [])[-settings.max_history_messages:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_content})
        async for token in _stream_openai_compatible(client, model_name, messages, temperature, model_name in _OPENAI_REASONING_MODELS):
            yield token
    except Exception:
        yield _provider_error("OpenAI")


async def stream_tests_claude(source_code: str, api_key: str, model_name: str, temperature: float, image_data: str | None, history: list | None):
    api_key = _provider_key("claude", api_key)
    if not api_key:
        yield _missing_key_message("claude")
        return
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, http_client=_http_client())
        user_content = [{"type": "text", "text": format_user_prompt(source_code)}]
        if image_data:
            decoded = _decode_data_url(image_data)
            if decoded:
                mime_type, _, encoded = decoded
                user_content.append({"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": encoded}})
        claude_messages = []
        for msg in (history or [])[-settings.max_history_messages:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in {"user", "assistant"} and content:
                claude_messages.append({"role": role, "content": content})
        claude_messages.append({"role": "user", "content": user_content})
        with client.messages.stream(model=model_name, max_tokens=4096, system=SYSTEM_PROMPT, messages=claude_messages, temperature=temperature) as stream:
            for text in stream.text_stream:
                yield text
    except Exception:
        yield _provider_error("Claude")


async def stream_tests_openai_provider(provider: str, source_code: str, api_key: str, model_name: str, temperature: float, base_url: str, history: list | None):
    api_key = _provider_key(provider, api_key)
    if not api_key:
        yield _missing_key_message(provider)
        return
    try:
        system_prompt = _sanitize_utf8(SYSTEM_PROMPT) if provider == "kimi" else SYSTEM_PROMPT
        user_prompt = _sanitize_utf8(format_user_prompt(source_code)) if provider == "kimi" else format_user_prompt(source_code)
        client = _openai_client(api_key=api_key, base_url=base_url)
        async for token in _stream_openai_compatible(client, model_name, _build_history_messages(history, system_prompt, user_prompt), temperature):
            yield token
    except Exception:
        yield _provider_error(provider.title())


async def stream_tests_ollama(source_code: str, api_key: str, model_name: str, temperature: float, image_data: str | None, history: list | None):
    try:
        client = _openai_client(api_key="ollama", base_url=f"{OLLAMA_BASE_URL}/v1")
        async for token in _stream_openai_compatible(client, model_name, _build_history_messages(history, SYSTEM_PROMPT, format_user_prompt(source_code)), temperature):
            yield token
    except Exception:
        yield "Ollama Error: Could not reach Ollama."


async def stream_tests(
    provider: str,
    message: str,
    api_key: str = "",
    model_name: str = "",
    temperature: float = 0.6,
    image_data: str | None = None,
    history: list | None = None,
) -> AsyncIterator[str]:
    if provider not in SUPPORTED_PROVIDERS:
        yield f"Unknown provider: {provider}"
        return
    defaults = {
        "gemini": "gemini-2.5-flash",
        "openai": "gpt-4o",
        "claude": "claude-opus-4-7",
        "deepseek": "deepseek-chat",
        "mistral": "mistral-large-latest",
        "kimi": "kimi-k2.6",
        "groq": "llama-3.3-70b-versatile",
        "ollama": "llama3.2",
    }
    model = model_name or defaults[provider]
    if provider == "gemini":
        async for token in stream_tests_gemini(message, api_key, model, temperature, image_data, history):
            yield token
    elif provider == "openai":
        async for token in stream_tests_openai(message, api_key, model, temperature, image_data, history):
            yield token
    elif provider == "claude":
        async for token in stream_tests_claude(message, api_key, model, temperature, image_data, history):
            yield token
    elif provider == "deepseek":
        async for token in stream_tests_openai_provider(provider, message, api_key, model, temperature, "https://api.deepseek.com", history):
            yield token
    elif provider == "mistral":
        async for token in stream_tests_openai_provider(provider, message, api_key, model, temperature, "https://api.mistral.ai/v1", history):
            yield token
    elif provider == "kimi":
        async for token in stream_tests_openai_provider(provider, message, api_key, model, temperature, "https://api.moonshot.ai/v1", history):
            yield token
    elif provider == "groq":
        async for token in stream_tests_openai_provider(provider, message, api_key, model, temperature, "https://api.groq.com/openai/v1", history):
            yield token
    else:
        async for token in stream_tests_ollama(message, api_key, model, temperature, image_data, history):
            yield token
