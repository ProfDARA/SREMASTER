import json
from pathlib import Path
from typing import Any

from .config import settings
from . import db


def load_file_runbooks() -> dict[str, Any]:
    """Load JSON runbooks from RUNBOOKS_PATH into SQLite.

    Invalid files are reported but do not prevent the API from starting.
    """
    directory = Path(settings.runbooks_path)
    directory.mkdir(parents=True, exist_ok=True)
    loaded = 0
    errors: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not data.get("name"):
                raise ValueError("name is required")
            data.setdefault("description", "")
            data.setdefault("match_labels", {})
            data.setdefault("steps", [])
            data.setdefault("severity", "warning")
            data.setdefault("owner", "")
            db.upsert_runbook(data)
            loaded += 1
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            errors.append(f"{path.name}: {exc}")
    return {"path": str(directory), "loaded": loaded, "errors": errors}
