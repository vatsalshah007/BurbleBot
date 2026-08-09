# app package
# pyrefly: ignore [missing-import]
from app.config import Config
def __init__(self, config: Config) -> None:
    self._config = config  # ← the Config instance is already here