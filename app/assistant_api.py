"""Local React prototype API over canonical, fixed audited reference evidence.

Run from the repo root: PYTHONPATH=src uvicorn app.assistant_api:app --host 127.0.0.1 --port 8766
No private-upload endpoint, arbitrary paths, shared conversations or stored keys.
"""
import hashlib
import json
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from railpulse.assistant import EvidenceAssistant
from railpulse.assistant.catalog import MODELS, CATALOG_DATE, validate_model
from railpulse.assistant.llm import make_selector
from railpulse.assistant.service import ROOT
from railpulse.core.runtime import DEFAULT_RUN

app = FastAPI(title="RailPulse assistant prototype", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
ALLOWED_ORIGINS = {"http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:8766", "http://127.0.0.1:8766"}


@app.middleware("http")
async def local_only(request, call_next):
    if request.headers.get("origin") and request.headers["origin"] not in ALLOWED_ORIGINS:
        return JSONResponse({"detail": "Origin not permitted"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def service():
    records = json.loads((ROOT / "outputs/dashboard/architecture-audit/decisions.json").read_text())["records"]
    sha = hashlib.sha256((DEFAULT_RUN / "models/bundle.json").read_bytes()).hexdigest()
    return EvidenceAssistant(records, run_directory=DEFAULT_RUN, bundle_sha256=sha)


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    previous_question: str | None = Field(default=None, min_length=1, max_length=2000)
    subsystem: Literal["door", "acv", "rail", "shm"] | None = None
    file_ids: list[str] = Field(default_factory=list, max_length=100)
    provider: Literal["openai", "anthropic"] | None = None
    model: str | None = Field(default=None, max_length=100)
    api_key: SecretStr | None = None
    consent: bool = False
    engineer_instructions: str = Field(default="", max_length=1500)
    engineer_context: str = Field(default="", max_length=2000)
    engineer_author: str = Field(default="", max_length=80)
    audience: Literal["plain", "technician", "engineer"] = "plain"
    detail: Literal["concise", "detailed"] = "concise"
    focus: Literal["auto", "quality", "evaluation", "review"] = "auto"


@app.get("/api/assistant/context")
def context():
    current = service()
    return {"api_schema_version": 4, "models": MODELS, "catalog_date": CATALOG_DATE, "run_id": DEFAULT_RUN.name,
            "knowledge": {"method": "hybrid-tfidf-lsa-v1", "documents": len({d["source"] for d in current.documents}),
                          "chunks": len(current.documents), "corpus_sha256": current.corpus_hash, "local_only": True},
            "dataset_label": "Audited reference replay · not live telemetry",
            "files": [{"subsystem": domain, "file_id": filename} for domain, filename in
                      sorted({(r["subsystem"], r["file_id"]) for r in current.records})],
            "record_count": len(current.records), "bundle_sha256": current.bundle_hash}


class KnowledgeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    subsystem: Literal["door", "acv", "rail", "shm"] | None = None


@app.post("/api/assistant/knowledge/search")
async def search_knowledge(request: Request):
    """Read-only tool for dashboard clients; never calls an external provider."""
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 8192:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
    try:
        query = KnowledgeQuery.model_validate(json.loads(payload))
        if not query.question.strip():
            raise ValueError("Empty question")
    except (ValueError, TypeError):
        return JSONResponse({"detail": "Invalid knowledge query"}, status_code=400)
    def retrieve():
        current = service()
        from railpulse.assistant.knowledge import VERSION
        return {"results": current.search_reference_docs(query.question, query.subsystem),
                "method": VERSION, "corpus_sha256": current.corpus_hash,
                "warnings": current.source_warnings, "local_only": True,
                "limitations": "Documentation is reference material, not live findings or operational authority."}
    try:
        return await run_in_threadpool(retrieve)
    except Exception:
        return JSONResponse({"detail": "Knowledge service unavailable"}, status_code=503)


@app.post("/api/assistant/ask")
async def ask(request: Request):
    # Parse manually so validation errors NEVER echo an API key or raw request.
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 16384:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
    try:
        query = Query.model_validate(json.loads(payload))
        if not query.question.strip():
            raise ValueError("Empty question")
        if query.provider:
            validate_model(query.provider, query.model)
    except (ValueError, TypeError):
        return JSONResponse({"detail": "Invalid question, scope or model selection"}, status_code=400)

    def answer():
        current = service()
        selector = None
        warning = None
        if query.provider:
            if query.consent and query.api_key and query.api_key.get_secret_value().strip():
                try:
                    selector = make_selector(provider=query.provider, model=query.model,
                                             api_key=query.api_key.get_secret_value())
                except Exception:
                    warning = "Provider configuration unavailable. Local evidence used; check optional dependencies and model access."
            else:
                warning = "No authorised API key supplied. Local evidence used."
        response = current.ask(query.question, subsystem=query.subsystem, file_ids=query.file_ids,
                               previous_question=query.previous_question,
                               selector=selector, consent=query.consent,
                               engineer_instructions=query.engineer_instructions, engineer_context=query.engineer_context,
                               engineer_author=query.engineer_author, audience=query.audience, detail=query.detail, focus=query.focus)
        if warning:
            response["warnings"].append(warning)
        response["dataset_label"] = "Audited reference replay · not live telemetry"
        response["requested_model"] = query.model
        return response

    try:
        return await run_in_threadpool(answer)
    except (ValueError, KeyError, TypeError):
        return JSONResponse({"detail": "Selected evidence scope is unavailable"}, status_code=400)
    except Exception:
        return JSONResponse({"detail": "Evidence service unavailable"}, status_code=503)
