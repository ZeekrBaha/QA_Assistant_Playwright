import pytest
from fastapi.testclient import TestClient

import backend.server as server_module
from backend import logic
from backend.atlassian import extract_adf_text, format_jira_issue, format_jira_search, normalize_domain
from backend.dom_distiller import distill_html, process_message_for_dom, validate_public_http_url
from backend.repo_integration import propose_test_file, run_repo_tests, scan_repo, write_proposed_file
from backend.server import app

client = TestClient(app)


def test_asgi_deployment_entrypoint_exports_application():
    from api.index import app as deployment_app

    assert deployment_app is app


def test_health():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate_routes_known_provider(monkeypatch):
    captured = {}

    def fake_generate_tests(**kwargs):
        captured.update(kwargs)
        return "mocked provider response"

    monkeypatch.setattr(server_module, "generate_tests", fake_generate_tests)

    response = client.post(
        "/api/generate",
        json={
            "provider": "openai",
            "message": "Write Playwright tests",
            "temperature": 0,
            "model_name": "gpt-4o",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "mocked provider response"
    assert captured["provider"] == "openai"
    assert captured["model_name"] == "gpt-4o"
    assert captured["temperature"] == 0


def test_backend_auth_gate_when_token_is_configured(monkeypatch):
    monkeypatch.setenv("QA_ASSISTANT_ACCESS_TOKEN", "secret-token")

    blocked = client.post("/api/generate", json={"provider": "openai", "message": "hello"})
    allowed = client.post(
        "/api/generate",
        headers={"X-Backend-Token": "secret-token"},
        json={"provider": "openai", "message": "hello"},
    )

    assert blocked.status_code == 401
    assert allowed.status_code == 200


def test_generate_rejects_oversized_message(monkeypatch):
    monkeypatch.setenv("QA_ASSISTANT_MAX_MESSAGE_CHARS", "10")

    response = client.post(
        "/api/generate",
        json={"provider": "openai", "message": "this message is too long"},
    )

    assert response.status_code == 422


def test_generate_routes_unknown_provider():
    response = client.post(
        "/api/generate",
        json={"provider": "unknown", "message": "hello"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "Unknown provider: unknown"


def test_openai_provider_uses_env_key_and_model(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            message = type("Message", (), {"content": "real OpenAI adapter response"})
            choice = type("Choice", (), {"message": message})
            return type("Response", (), {"choices": [choice]})

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = FakeChat()

    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    monkeypatch.setattr(logic, "OpenAI", FakeOpenAI)

    result = logic.generate_tests(
        provider="openai",
        message="Generate a tiny Playwright test",
        api_key="",
        model_name="gpt-4o",
        temperature=0,
    )

    assert result == "real OpenAI adapter response"
    assert captured["client_kwargs"]["api_key"] == "env-openai-key"
    assert captured["model"] == "gpt-4o"
    assert captured["temperature"] == 0
    assert captured["messages"][0]["role"] == "system"


def test_reasoning_model_omits_temperature(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            message = type("Message", (), {"content": "reasoning response"})
            choice = type("Choice", (), {"message": message})
            return type("Response", (), {"choices": [choice]})

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    monkeypatch.setattr(logic, "OpenAI", FakeOpenAI)

    logic.generate_tests(provider="openai", message="hello", model_name="o4-mini", temperature=0.2)

    assert captured["model"] == "o4-mini"
    assert "temperature" not in captured


def test_dom_distillation_keeps_semantic_elements_and_removes_noise():
    html = """
    <div><script>alert(1)</script><button data-testid="save">Save</button><span>Wrapped</span></div>
    """

    distilled = distill_html(html)

    assert "<script" not in distilled
    assert '<button data-testid="save">Save</button>' in distilled
    assert "Wrapped" in distilled


def test_ssrf_protection_rejects_unsafe_urls():
    with pytest.raises(ValueError, match="Only http and https"):
        validate_public_http_url("file:///etc/passwd")

    with pytest.raises(ValueError, match="private or unsafe"):
        validate_public_http_url("http://127.0.0.1:8000")


@pytest.mark.asyncio
async def test_process_message_for_dom_builds_locator_prompt_for_html():
    result = await process_message_for_dom('<button id="submit">Submit</button>', is_locator_mode=True)

    assert result["distilled_dom"] == '<button id="submit">Submit</button>'
    assert "STRICT DOM LOCATOR GENERATION TASK" in result["message"]
    assert "submit" in result["message"]


def test_jira_helper_parses_adf_and_formats_issue():
    adf = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Given checkout"},
                    {"type": "text", "text": "when payment succeeds"},
                ],
            }
        ],
    }

    text = extract_adf_text(adf)
    formatted = format_jira_issue("PROJ-123", {"fields": {"summary": "Checkout", "description": adf}})

    assert "Given checkout" in text
    assert "Jira Issue: PROJ-123" in formatted
    assert "Summary: Checkout" in formatted
    assert "payment succeeds" in formatted


def test_jira_search_format_and_domain_normalization():
    data = {
        "issues": [
            {
                "key": "PROJ-1",
                "fields": {
                    "summary": "Login",
                    "status": {"name": "To Do"},
                    "priority": {"name": "High"},
                    "assignee": {"displayName": "Ada"},
                },
            }
        ]
    }

    assert normalize_domain("company.atlassian.net/") == "https://company.atlassian.net"
    assert "**PROJ-1** [To Do | High]: Login (Assignee: Ada)" in format_jira_search(data)


def test_repo_scan_and_proposal_are_limited_to_allowed_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_ASSISTANT_ALLOWED_REPO_ROOTS", str(tmp_path))
    repo = tmp_path / "app"
    repo.mkdir()
    (repo / "package.json").write_text('{"scripts":{"test":"vitest"},"devDependencies":{"@playwright/test":"latest","vite":"latest"}}', encoding="utf-8")

    scan = scan_repo(str(repo))
    proposal = propose_test_file(str(repo), "cover login", "playwright")

    assert "vite" in scan["frameworks"]
    assert "playwright" in scan["test_frameworks"]
    assert proposal["relative_path"] == "tests/generated-workflow.spec.ts"
    assert "cover login" in proposal["content"]


def test_repo_scan_rejects_paths_outside_allowed_roots(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setenv("QA_ASSISTANT_ALLOWED_REPO_ROOTS", str(allowed))

    response = client.post("/api/repo/scan", json={"repo_path": str(outside)})

    assert response.status_code == 400


def test_repo_write_requires_approval_and_safe_relative_path(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_ASSISTANT_ALLOWED_REPO_ROOTS", str(tmp_path))

    with pytest.raises(ValueError, match="explicit approval"):
        write_proposed_file(str(tmp_path), "tests/example.spec.ts", "content", approved=False)

    with pytest.raises(ValueError, match="safe relative"):
        write_proposed_file(str(tmp_path), "../escape.spec.ts", "content", approved=True)

    result = write_proposed_file(str(tmp_path), "tests/example.spec.ts", "content", approved=True)
    assert result["written"] is True
    assert (tmp_path / "tests" / "example.spec.ts").read_text(encoding="utf-8") == "content"


def test_repo_test_command_allowlist(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_ASSISTANT_ALLOWED_REPO_ROOTS", str(tmp_path))

    with pytest.raises(ValueError, match="allowlisted"):
        run_repo_tests(str(tmp_path), "rm -rf .")

    result = run_repo_tests(str(tmp_path), "python3 -m pytest")
    assert result["command"] == "python3 -m pytest"
    assert result["exit_code"] in {0, 1, 5}
