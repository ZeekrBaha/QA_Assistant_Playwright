import base64
import re
from urllib.parse import urlparse

import httpx

from backend.config import settings


def normalize_domain(domain: str) -> str:
    domain = domain.strip().rstrip("/")
    if not domain.startswith(("http://", "https://")):
        domain = f"https://{domain}"
    parsed = urlparse(domain)
    if parsed.scheme != "https":
        raise ValueError("Atlassian domain must use HTTPS.")
    if not parsed.hostname:
        raise ValueError("Atlassian domain must include a hostname.")
    if parsed.path or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Atlassian domain must be a hostname only.")
    return f"https://{parsed.netloc.lower()}"


def auth_headers(email: str, api_token: str) -> dict:
    token = base64.b64encode(f"{email}:{api_token}".encode("ascii")).decode("ascii")
    return {"Authorization": f"Basic {token}", "Accept": "application/json"}


def extract_adf_text(adf_node: dict) -> str:
    if not isinstance(adf_node, dict):
        return ""

    parts = []
    if adf_node.get("type") == "text":
        parts.append(adf_node.get("text", ""))

    for child in adf_node.get("content", []) or []:
        text = extract_adf_text(child)
        if text:
            parts.append(text)
        if child.get("type") in {"paragraph", "heading", "listItem"}:
            parts.append("\n")

    return " ".join(parts).replace(" \n ", "\n").strip()


def format_jira_issue(issue_key: str, data: dict) -> str:
    fields = data.get("fields", {})
    summary = fields.get("summary", "No Summary")
    description = extract_adf_text(fields.get("description", {})) or "No Description"
    return f"Jira Issue: {issue_key}\nSummary: {summary}\n\nDescription:\n{description}"


def get_jira_issue(domain: str, email: str, api_token: str, issue_key: str) -> str:
    url = f"{normalize_domain(domain)}/rest/api/3/issue/{issue_key}"
    try:
        response = httpx.get(url, headers=auth_headers(email, api_token), timeout=10.0, verify=settings.verify_ssl)
        response.raise_for_status()
        return format_jira_issue(issue_key, response.json())
    except httpx.HTTPStatusError as exc:
        return f"[ERROR] Jira API returned {exc.response.status_code}: {exc.response.text}"
    except Exception as exc:
        return f"[ERROR] Failed to fetch Jira issue: {exc}"


def format_jira_search(data: dict) -> str:
    issues = data.get("issues", [])
    if not issues:
        return "No issues found matching this query."

    lines = [f"Found {len(issues)} issues:"]
    for issue in issues:
        fields = issue.get("fields", {})
        status = fields.get("status", {}).get("name", "Unknown Status")
        priority = fields.get("priority", {}).get("name", "Unknown Priority")
        assignee = fields.get("assignee")
        assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
        lines.append(f"- **{issue.get('key', 'UNKNOWN')}** [{status} | {priority}]: {fields.get('summary', 'No Summary')} (Assignee: {assignee_name})")
    return "\n".join(lines)


def search_jira_jql(domain: str, email: str, api_token: str, jql: str) -> str:
    url = f"{normalize_domain(domain)}/rest/api/3/search/jql"
    body = {"jql": jql, "maxResults": 15, "fields": ["summary", "status", "assignee", "priority"]}
    try:
        response = httpx.post(url, headers=auth_headers(email, api_token), json=body, timeout=15.0, verify=settings.verify_ssl)
        response.raise_for_status()
        return format_jira_search(response.json())
    except httpx.HTTPStatusError as exc:
        return f"[ERROR] Jira Search API returned {exc.response.status_code}: {exc.response.text}"
    except Exception as exc:
        return f"[ERROR] Failed to search Jira: {exc}"


def strip_html(text: str) -> str:
    return re.sub("<[^<]+>", " ", text).strip()
