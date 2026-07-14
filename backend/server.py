import json
import os
import subprocess

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from backend.atlassian import get_jira_issue, search_jira_jql
from backend.config import settings
from backend.dom_distiller import process_message_for_dom
from backend.logic import generate_image, generate_tests, get_ollama_models, stream_tests
from backend.repo_integration import propose_test_file, run_repo_tests, scan_repo, write_proposed_file
from backend.security import require_backend_token, require_configured_backend_token
from backend.web_search import perform_web_search

protected = [Depends(require_backend_token)]
repo_protected = [Depends(require_configured_backend_token)]
app = FastAPI(title="QA Assistant Reliable API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    provider: str
    message: str = Field(min_length=1)
    api_key: str = Field(default="", max_length=20_000)
    temperature: float = Field(default=0.6, ge=0, le=2)
    model_name: str = Field(default="", max_length=200)
    image_data: str | None = None
    is_locator_mode: bool = False
    conversation_history: list | None = None

    @field_validator("message")
    @classmethod
    def message_size(cls, value: str) -> str:
        if len(value) > settings.max_message_chars:
            raise ValueError(f"message exceeds {settings.max_message_chars} characters")
        return value

    @field_validator("image_data")
    @classmethod
    def image_size(cls, value: str | None) -> str | None:
        if value and len(value) > settings.max_image_data_chars:
            raise ValueError(f"image_data exceeds {settings.max_image_data_chars} characters")
        return value

    @field_validator("conversation_history")
    @classmethod
    def history_size(cls, value: list | None) -> list | None:
        if value is None:
            return value
        if len(value) > settings.max_history_messages:
            raise ValueError(f"conversation_history exceeds {settings.max_history_messages} messages")
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("conversation_history entries must be objects")
            content = item.get("content", "")
            if not isinstance(content, str):
                raise ValueError("conversation_history content must be a string")
            if len(content) > settings.max_history_content_chars:
                raise ValueError(f"conversation_history content exceeds {settings.max_history_content_chars} characters")
        return value


class GenerateResponse(BaseModel):
    response: str
    distilled_dom: str | None = None
    source_url: str | None = None
    dom_warning: str | None = None


class GenerateImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4_000)
    provider: str = "openai"
    api_key: str = Field(default="", max_length=20_000)
    model_name: str = Field(default="", max_length=200)


class JiraRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=300)
    email: str = Field(min_length=1, max_length=320)
    api_token: str = Field(min_length=1, max_length=20_000)
    issue_key: str = Field(min_length=1, max_length=100)


class RovoRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=300)
    email: str = Field(min_length=1, max_length=320)
    api_token: str = Field(min_length=1, max_length=20_000)
    jql: str = Field(min_length=1, max_length=10_000)


class ToolResponse(BaseModel):
    content: str
    error: bool = False


class WebSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1_000)


class RepoScanRequest(BaseModel):
    repo_path: str = Field(min_length=1, max_length=1_000)


class RepoProposalRequest(BaseModel):
    repo_path: str = Field(min_length=1, max_length=1_000)
    instruction: str = Field(min_length=1, max_length=10_000)
    output_mode: str = Field(default="playwright", max_length=80)


class RepoWriteRequest(BaseModel):
    repo_path: str = Field(min_length=1, max_length=1_000)
    relative_path: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=250_000)
    approved: bool = False
    allow_overwrite: bool = False


class RepoTestRequest(BaseModel):
    repo_path: str = Field(min_length=1, max_length=1_000)
    command: str = Field(min_length=1, max_length=200)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/generate", response_model=GenerateResponse, dependencies=protected)
async def generate(req: GenerateRequest):
    dom_result = await process_message_for_dom(req.message, req.is_locator_mode)
    response = generate_tests(
        provider=req.provider,
        message=dom_result["message"],
        api_key=req.api_key,
        model_name=req.model_name,
        temperature=req.temperature,
        image_data=req.image_data,
        history=req.conversation_history or [],
    )
    return GenerateResponse(
        response=response,
        distilled_dom=dom_result.get("distilled_dom"),
        source_url=dom_result.get("source_url"),
        dom_warning=dom_result.get("fetch_error"),
    )


@app.post("/api/stream", dependencies=protected)
async def stream_generate(req: GenerateRequest):
    dom_result = await process_message_for_dom(req.message, req.is_locator_mode)

    async def event_stream():
        meta = {}
        if dom_result.get("distilled_dom"):
            meta["distilled_dom"] = dom_result["distilled_dom"][:3000]
        if dom_result.get("source_url"):
            meta["source_url"] = dom_result["source_url"]
        if dom_result.get("fetch_error"):
            meta["dom_warning"] = dom_result["fetch_error"]
        if meta:
            yield f"data: {json.dumps({'type': 'meta', **meta})}\n\n"

        async for token in stream_tests(
            provider=req.provider,
            message=dom_result["message"],
            api_key=req.api_key,
            model_name=req.model_name,
            temperature=req.temperature,
            image_data=req.image_data,
            history=req.conversation_history or [],
        ):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/generate_image", response_model=GenerateResponse, dependencies=protected)
async def generate_image_endpoint(req: GenerateImageRequest):
    return GenerateResponse(response=generate_image(req.prompt, req.provider, req.model_name, req.api_key))


@app.post("/api/atlassian/jira", response_model=ToolResponse, dependencies=protected)
async def fetch_jira(req: JiraRequest):
    content = get_jira_issue(req.domain, req.email, req.api_token, req.issue_key)
    return ToolResponse(content=content, error=content.startswith("[ERROR]"))


@app.post("/api/atlassian/rovo", response_model=ToolResponse, dependencies=protected)
async def fetch_rovo(req: RovoRequest):
    content = search_jira_jql(req.domain, req.email, req.api_token, req.jql)
    return ToolResponse(content=content, error=content.startswith("[ERROR]"))


@app.post("/api/web_search", response_model=ToolResponse, dependencies=protected)
async def fetch_web_search(req: WebSearchRequest):
    content = perform_web_search(req.query)
    return ToolResponse(content=content, error=content.startswith("[ERROR]"))


@app.get("/api/ollama/models", dependencies=protected)
async def ollama_models():
    models = get_ollama_models()
    return {"models": models, "connected": bool(models)}


@app.post("/api/repo/scan", dependencies=repo_protected)
async def repo_scan(req: RepoScanRequest):
    try:
        return scan_repo(req.repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/repo/propose", dependencies=repo_protected)
async def repo_propose(req: RepoProposalRequest):
    try:
        return propose_test_file(req.repo_path, req.instruction, req.output_mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/repo/write", dependencies=repo_protected)
async def repo_write(req: RepoWriteRequest):
    try:
        return write_proposed_file(req.repo_path, req.relative_path, req.content, req.approved, req.allow_overwrite)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/repo/test", dependencies=repo_protected)
async def repo_test(req: RepoTestRequest):
    try:
        return run_repo_tests(req.repo_path, req.command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=408, detail="Test command timed out.") from exc


frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        return FileResponse(os.path.join(frontend_dist, "index.html"))
