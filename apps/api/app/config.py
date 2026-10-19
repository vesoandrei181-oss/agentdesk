"""全局配置。所有可调参数集中在这里，通过环境变量覆盖。

命名约定：环境变量名与字段名大小写不敏感（LLM_API_KEY -> llm_api_key）。
仓库里只留 .env.example，真实密钥走环境变量或平台 secret 管理。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> app -> api -> apps -> 仓库根
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AgentDesk"
    secret_key: str = "agentdesk-dev-secret"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # 模型
    llm_provider: str = "auto"          # auto | deepseek | openai | ollama | mock
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model_fast: str = "deepseek-flash"
    llm_model_quality: str = "deepseek-v4-pro"

    # 存储
    database_url: str = "sqlite:///./data/agentdesk.db"
    upload_dir: str = "./data/uploads"

    # 行为开关
    demo_replay: int = 1
    fast_thinking: int = 1              # 抽取类 Agent 关闭思维链，降低延迟与成本
    semantic_cache_threshold: float = 0.95
    token_budget: int = 12000
    pii_mask: int = 1

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_url(self) -> str:
        """把相对路径的 SQLite 固定到仓库根，避免启动目录不同导致两套库。"""
        url = self.database_url
        if url.startswith("sqlite:///./"):
            path = (ROOT_DIR / url.removeprefix("sqlite:///./")).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{path.as_posix()}"
        return url

    @property
    def upload_path(self) -> Path:
        p = (ROOT_DIR / self.upload_dir.lstrip("./")).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def provider_name(self) -> str:
        """auto 档：有密钥走真实模型，没密钥自动降级到内置 Mock，保证界面永远可用。"""
        name = (self.llm_provider or "auto").strip().lower()
        if name in {"", "auto"}:
            return "deepseek" if self.llm_api_key else "mock"
        return name

    @property
    def is_mock(self) -> bool:
        return self.provider_name == "mock" or not self.llm_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
