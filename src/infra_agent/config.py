from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    inventory_dir: Path = ROOT_DIR / "inventory"
    host: str = "127.0.0.1"
    port: int = 8000
    agent_max_steps: int = 8
    agent_timeout_seconds: float = 120.0
    telegram_bot_token: str = ""
    telegram_allowed_chat_ids: str = ""
    nextcloud_url: str = ""
    nextcloud_user: str = ""
    nextcloud_app_password: str = ""
    nextcloud_file_path: str = ""

    def resolved_inventory_dir(self) -> Path:
        path = self.inventory_dir
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path

    def allowed_chat_id_set(self) -> frozenset[int] | None:
        from infra_agent.telegram_policy import parse_allowed_chat_ids

        return parse_allowed_chat_ids(self.telegram_allowed_chat_ids)

    def nextcloud_ready(self) -> bool:
        return bool(
            self.nextcloud_url.strip()
            and self.nextcloud_user.strip()
            and self.nextcloud_app_password.strip()
            and self.nextcloud_file_path.strip()
        )


def get_settings() -> Settings:
    return Settings()
