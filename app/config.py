import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_path: str = os.getenv("DATABASE_PATH", "./sre-alert-brain.db")
    webhook_shared_secret: str = os.getenv("WEBHOOK_SHARED_SECRET", "")
    clickup_api_token: str = os.getenv("CLICKUP_API_TOKEN", "")
    clickup_list_id: str = os.getenv("CLICKUP_LIST_ID", "")
    clickup_team_id: str = os.getenv("CLICKUP_TEAM_ID", "")
    clickup_dry_run: bool = os.getenv("CLICKUP_DRY_RUN", "false").lower() == "true"
    ollama_enabled: bool = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    ollama_timeout_seconds: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))


settings = Settings()
