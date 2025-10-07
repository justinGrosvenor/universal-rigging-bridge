from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_name: str = Field(default="rig-transformer")
    log_level: str = Field(default="INFO")
    aws_region: str = Field(default="us-east-1")
    input_bucket: Optional[str] = None
    output_bucket: Optional[str] = None
    work_dir: Path = Field(default=Path("/tmp/rig-transformer"))
    blender_python: Path = Field(default=Path("/usr/local/blender/4.5/python/bin/python3.11"))
    blender_executable: Path = Field(default=Path("/usr/local/blender/blender"))

    model_config = {
        "env_file": (".env", ".env.local", str(Path(__file__).parent.parent.parent / ".env")),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached application settings."""

    settings = AppSettings()
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    return settings
