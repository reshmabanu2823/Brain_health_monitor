from dataclasses import dataclass, field
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]

@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv('CORTIA_DATA_DIR', ROOT/'data')))
    model_dir: Path = field(default_factory=lambda: Path(os.getenv('CORTIA_MODEL_DIR', ROOT/'models/mri')))
    database_url: str | None = field(default_factory=lambda: os.getenv('CORTIA_DATABASE_URL'))
    secure_cookie: bool = field(default_factory=lambda: os.getenv('CORTIA_SECURE_COOKIE') == '1')
    allowed_origins: tuple = ('http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:8010', 'http://127.0.0.1:8010')
    testing: bool = False
    max_upload_bytes: int = 10 * 1024 * 1024
    ai_endpoint: str = field(default_factory=lambda: os.getenv('CORTIA_AI_ENDPOINT', ''))
    ai_key: str = field(default_factory=lambda: os.getenv('CORTIA_AI_KEY', ''))
    ai_model: str = field(default_factory=lambda: os.getenv('CORTIA_AI_MODEL', ''))
