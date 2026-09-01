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
    ollama_model: str = "gemma4:e4b"
    inventory_dir: Path = ROOT_DIR / "inventory"
    agent_max_steps: int = 8
    agent_timeout_seconds: float = 120.0
    telegram_bot_token: str = ""
    telegram_allowed_chat_ids: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_phone: str = ""
    telegram_index_chats: str = ""
    telegram_session_path: str = "data/telegram-user"
    telegram_index_db: str = "data/telegram-index.sqlite"
    telegram_index_interval_seconds: float = 900.0
    telegram_index_max_messages: int = 0
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

    def index_chat_ids(self) -> list[int]:
        from infra_agent.telegram_policy import parse_id_list

        return parse_id_list(self.telegram_index_chats)

    def resolved_telegram_session_path(self) -> Path:
        path = Path(self.telegram_session_path)
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path

    def resolved_telegram_index_db(self) -> Path:
        path = Path(self.telegram_index_db)
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path

    def telegram_user_ready(self) -> bool:
        return bool(self.telegram_api_id and self.telegram_api_hash.strip())

    def telegram_index_ready(self) -> bool:
        return self.telegram_user_ready() and bool(self.index_chat_ids())

    def nextcloud_ready(self) -> bool:
        return bool(
            self.nextcloud_url.strip()
            and self.nextcloud_user.strip()
            and self.nextcloud_app_password.strip()
            and self.nextcloud_file_path.strip()
        )


def get_settings() -> Settings:
    return Settings()
