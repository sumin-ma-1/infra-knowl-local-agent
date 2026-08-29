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

    def resolved_inventory_dir(self) -> Path:
        path = self.inventory_dir
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path


def get_settings() -> Settings:
    return Settings()
