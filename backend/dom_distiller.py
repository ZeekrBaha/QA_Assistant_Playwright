import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from backend.config import settings

SEMANTIC_TAGS = {
    "button",
    "a",
    "input",
    "select",
    "textarea",
    "form",
    "label",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "nav",
    "header",
    "footer",
    "main",
    "article",
}
IMPORTANT_ATTRS = {
    "id",
    "name",
    "role",
    "aria-label",
    "data-testid",
    "data-test-id",
    "placeholder",
    "type",
    "href",
    "value",
}


def distill_html(html_snippet: str) -> str:
    if not html_snippet or not html_snippet.strip():
        return ""

    soup = BeautifulSoup(html_snippet, "html.parser")

    for tag in soup(["script", "style", "meta", "link", "noscript", "svg", "path", "iframe"]):
        tag.decompose()

    for tag in soup.find_all(True):
        has_important_attr = any(attr in tag.attrs for attr in IMPORTANT_ATTRS)
        if tag.name not in SEMANTIC_TAGS and not has_important_attr:
            tag.unwrap()
            continue

        cleaned_attrs: dict[str, Any] = {}
        for attr, value in tag.attrs.items():
            if attr in IMPORTANT_ATTRS or attr == "class":
                cleaned_attrs[attr] = " ".join(value) if isinstance(value, list) else value
        tag.attrs = cleaned_attrs

    distilled = re.sub(r"\n\s*\n", "\n", str(soup))
    return distilled.strip()


async def fetch_and_distill_url(url: str) -> str:
    headers = {"User-Agent": "QA-Assistant-Reliable/0.1"}
    try:
        safe_url = validate_public_http_url(url)
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False, verify=settings.verify_ssl) as client:
            response = await _get_with_safe_redirects(client, safe_url, headers)
            try:
                response.raise_for_status()
                html = await _read_capped_response(response, settings.max_dom_fetch_bytes)
            finally:
                await response.aclose()
            return distill_html(html)
    except Exception as exc:
        return f"[Failed to fetch and distill URL {url}: {exc}]"


def validate_public_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are allowed.")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname.")
    if parsed.username or parsed.password:
        raise ValueError("URL must not include userinfo.")

    for address in _resolve_host(parsed.hostname):
        ip = ipaddress.ip_address(address)
        if _is_blocked_ip(ip):
            raise ValueError("URL resolves to a private or unsafe network address.")

    return url


async def _get_with_safe_redirects(client: httpx.AsyncClient, url: str, headers: dict) -> httpx.Response:
    current_url = url
    for _ in range(settings.max_url_redirects + 1):
        validate_public_http_url(current_url)
        request = client.build_request("GET", current_url, headers=headers)
        response = await client.send(request, stream=True)
        if response.status_code not in {301, 302, 303, 307, 308}:
            return response

        location = response.headers.get("location")
        if not location:
            return response
        current_url = urljoin(str(response.url), location)
        await response.aclose()

    raise ValueError(f"URL exceeded redirect limit of {settings.max_url_redirects}.")


async def _read_capped_response(response: httpx.Response, max_bytes: int) -> str:
    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        raise ValueError(f"Response exceeds {max_bytes} byte limit.")

    total = 0
    chunks = []
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"Response exceeds {max_bytes} byte limit.")
        chunks.append(chunk)
    return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")


def _resolve_host(hostname: str) -> set[str]:
    try:
        return {str(result[4][0]) for result in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname: {hostname}") from exc


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not ip.is_global


async def process_message_for_dom(message: str, is_locator_mode: bool = False) -> dict:
    result = {
        "message": message,
        "distilled_dom": None,
        "source_url": None,
        "fetch_error": None,
    }

    if _looks_like_html(message):
        distilled = distill_html(message)
        if len(distilled) > 10:
            result["distilled_dom"] = distilled
            result["message"] = _build_grounded_locator_prompt(distilled, "html_snippet") if is_locator_mode else message
        return result

    urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', message)
    if urls and is_locator_mode:
        distilled_parts = []
        for raw_url in urls[:2]:
            url = raw_url if raw_url.startswith(("http://", "https://")) else f"https://{raw_url}"
            distilled = await fetch_and_distill_url(url)
            result["source_url"] = url
            if distilled.startswith("[Failed"):
                result["fetch_error"] = distilled
                continue
            if len(distilled.strip()) < 50:
                result["fetch_error"] = f"[Warning] The page at {url} returned very little HTML. It may be JavaScript rendered."
            distilled_parts.append(distilled)

        if distilled_parts:
            combined = "\n\n".join(distilled_parts)
            result["distilled_dom"] = combined
            result["message"] = _build_grounded_locator_prompt(combined, urls[0])

    return result


def _looks_like_html(message: str) -> bool:
    lowered = message.lower()
    return any(token in lowered for token in ("<div", "<button", "<a ", "<input", "<form", "<select", "<textarea"))


def _build_grounded_locator_prompt(distilled_dom: str, source: str) -> str:
    return f"""STRICT DOM LOCATOR GENERATION TASK

SOURCE: {source}

Rules:
1. Only use elements present in the DOM below.
2. Ask for framework and language if not provided.
3. Prefer stable locators: role, label, data-testid, id, then CSS.
4. If requested, generate a Page Object Model and test code.

DISTILLED DOM:
```html
{distilled_dom}
```"""
