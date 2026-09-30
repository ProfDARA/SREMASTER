import hmac
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from . import db
from .config import settings
from .services import fingerprint, process_event

app = FastAPI(title="SRE Alert Brain", version="1.0.0")


class RunbookIn(BaseModel):
    name: str
    description: str = ""
    match_labels: dict[str, str] = Field(default_factory=dict)
    steps: list[str] = Field(default_factory=list)
    severity: str = "warning"
    owner: str = ""


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhooks/grafana", status_code=202)
async def grafana_webhook(payload: dict[str, Any], background_tasks: BackgroundTasks, x_webhook_secret: str | None = Header(default=None)) -> dict[str, Any]:
    if settings.webhook_shared_secret and not hmac.compare_digest(x_webhook_secret or "", settings.webhook_shared_secret):
        raise HTTPException(status_code=401, detail="invalid webhook secret")
    event, created = db.create_event(fingerprint(payload), payload)
    if not event:
        raise HTTPException(status_code=500, detail="could not persist event")
    if created:
        background_tasks.add_task(process_event, event)
    return {"accepted": True, "duplicate": not created, "event_id": event["id"], "status": "queued" if created else event["status"]}


@app.get("/api/runbooks")
def runbooks() -> list[dict[str, Any]]:
    return db.get_runbooks()


@app.post("/api/runbooks")
def add_runbook(body: RunbookIn) -> dict[str, Any]:
    return db.create_runbook(body.model_dump())


@app.get("/api/events")
def events(limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, Any]]:
    return db.list_events(limit)


@app.post("/api/events/{event_id}/retry")
async def retry_event(event_id: int) -> dict[str, Any]:
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    return await process_event(event)
