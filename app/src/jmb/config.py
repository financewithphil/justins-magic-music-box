from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JMB_", env_file=".env", extra="ignore")

    app_name: str = "Justin's Magic Music Box"
    host: str = "127.0.0.1"
    port: int = 8768

    # Storage roots — macOS conventions
    data_dir: Path = Path.home() / "Library" / "Application Support" / "JustinsMagicMusicBox"
    exports_dir: Path = Path.home() / "Music" / "Justin's Magic Music Box"

    # ML defaults
    demucs_default_model: str = "htdemucs"        # 4-stem
    demucs_guitar_model: str = "htdemucs_6s"      # adds guitar + piano stems
    device: str = "mps"                            # mps | cpu

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.sqlite"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.exports_dir, self.jobs_dir, self.models_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
