import hashlib
import json
import re
from typing import Any

import httpx

from .config import settings
from . import db


def parse_json(value: Any, default: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def fingerprint(payload: dict[str, Any]) -> str:
    if payload.get("groupKey"):
        return hashlib.sha256(json.dumps({
            "groupKey": payload["groupKey"],
            "status": payload.get("status"),
            "alerts": [{"labels": a.get("labels", {}), "startsAt": a.get("startsAt"), "endsAt": a.get("endsAt")} for a in payload.get("alerts", [])],
        }, sort_keys=True).encode()).hexdigest()
    alerts = payload.get("alerts") or [payload]
    stable = [{"labels": a.get("labels", {}), "startsAt": a.get("startsAt")} for a in alerts]
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def merged_labels(payload: dict[str, Any]) -> dict[str, str]:
    labels = dict(payload.get("commonLabels") or {})
    alerts = payload.get("alerts") or []
    if alerts:
        labels.update(alerts[0].get("labels") or {})
    return {str(k): str(v) for k, v in labels.items()}


def select_runbook(labels: dict[str, str]) -> dict[str, Any] | None:
    best = None
    best_score = 0
    for runbook in db.get_runbooks():
        match = parse_json(runbook["match_labels"], {})
        if match and all(labels.get(str(k)) == str(v) for k, v in match.items()):
            if len(match) > best_score:
                best, best_score = runbook, len(match)
    return best


def alert_summary(payload: dict[str, Any]) -> str:
    alerts = payload.get("alerts") or [payload]
    names = [a.get("labels", {}).get("alertname", "unnamed-alert") for a in alerts]
    return ", ".join(names)


async def ollama_reason(payload: dict[str, Any], runbook: dict[str, Any] | None) -> dict[str, Any]:
    if not settings.ollama_enabled:
        return {}
    steps = parse_json(runbook.get("steps") if runbook else "[]", [])
    prompt = {
        "task": "You are an SRE incident triage assistant. Return strict JSON with keys summary, impact, priority (1-4), recommended_actions.",
        "alert": payload,
        "runbook": {"name": runbook.get("name"), "description": runbook.get("description"), "steps": steps} if runbook else None,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
            response = await client.post(f"{settings.ollama_base_url.rstrip('/')}/api/generate", json={"model": settings.ollama_model, "prompt": json.dumps(prompt), "stream": False, "format": "json"})
            response.raise_for_status()
            generated = response.json().get("response", "{}")
            return json.loads(generated)
    except Exception as exc:  # reasoning is optional; alert delivery must survive it
        return {"reasoning_error": str(exc)}


def task_content(payload: dict[str, Any], runbook: dict[str, Any] | None, reasoning: dict[str, Any]) -> tuple[str, str, int]:
    labels = merged_labels(payload)
    severity = labels.get("severity", runbook.get("severity", "warning") if runbook else "warning").lower()
    priority = {"critical": 1, "high": 2, "warning": 3, "info": 4}.get(severity, 3)
    priority = int(reasoning.get("priority", priority)) if str(reasoning.get("priority", "")).isdigit() else priority
    name = reasoning.get("summary") or f"[{severity.upper()}] {alert_summary(payload)}"
    runbook_steps = parse_json(runbook["steps"], []) if runbook else []
    description = "\n".join([
        "## Grafana alert",
        f"Labels: `{json.dumps(labels, sort_keys=True)}`",
        f"Starts at: {((payload.get('alerts') or [{}])[0]).get('startsAt', 'unknown')}",
        "",
        "## SRE triage",
        str(reasoning.get("impact", "Automated alert received; investigate according to the runbook.")),
        "",
        "## Recommended actions",
        "\n".join(f"- {item}" for item in (reasoning.get("recommended_actions") or runbook_steps or ["Review the Grafana panel and recent changes."])),
        "",
        f"Runbook: {runbook.get('name', 'No matching runbook') if runbook else 'No matching runbook'}",
    ])
    return name[:250], description, max(1, min(4, priority))


async def send_to_clickup(name: str, description: str, priority: int, labels: dict[str, str]) -> str:
    if settings.clickup_dry_run:
        return "dry-run"
    if not settings.clickup_api_token or not settings.clickup_list_id:
        raise RuntimeError("CLICKUP_API_TOKEN and CLICKUP_LIST_ID are required")
    tags = [re.sub(r"[^a-zA-Z0-9_-]", "-", value)[:30] for key, value in labels.items() if key in {"service", "environment", "severity"}]
    body = {"name": name, "description": description, "priority": str(priority), "tags": tags}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"https://api.clickup.com/api/v2/list/{settings.clickup_list_id}/task", headers={"Authorization": settings.clickup_api_token, "Content-Type": "application/json"}, json=body)
        response.raise_for_status()
        return str(response.json().get("id", "unknown"))


async def process_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = parse_json(event["payload"], {})
    labels = merged_labels(payload)
    runbook = select_runbook(labels)
    db.update_event(event["id"], runbook_id=runbook["id"] if runbook else None, status="processing", error=None)
    reasoning = await ollama_reason(payload, runbook)
    name, description, priority = task_content(payload, runbook, reasoning)
    try:
        task_id = await send_to_clickup(name, description, priority, labels)
        return db.update_event(event["id"], status="delivered", clickup_task_id=task_id, error=None) or event
    except Exception as exc:
        return db.update_event(event["id"], status="failed", error=str(exc)) or event
