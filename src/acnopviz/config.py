from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/acnopviz.db")
    seed: int = 20261104
    as_of: str = "2026-10-31"
    host: str = "0.0.0.0"
    port: int = 8000
    bootstrap_paths: int = 2000
    bootstrap_block: int = 3

    def __post_init__(self) -> None:
        date.fromisoformat(self.as_of)
        if not self.host:
            raise ValueError("host must not be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if not 100 <= self.bootstrap_paths <= 20000:
            raise ValueError("bootstrap_paths must be between 100 and 20000")
        if not 1 <= self.bootstrap_block <= 24:
            raise ValueError("bootstrap_block must be between 1 and 24")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            db_path=Path(os.getenv("ACNOPVIZ_DB", "data/acnopviz.db")),
            seed=int(os.getenv("ACNOPVIZ_SEED", "20261104")),
            as_of=os.getenv("ACNOPVIZ_AS_OF", "2026-10-31"),
            host=os.getenv("ACNOPVIZ_HOST", "0.0.0.0"),
            port=int(os.getenv("ACNOPVIZ_PORT", "8000")),
            bootstrap_paths=int(os.getenv("ACNOPVIZ_BOOTSTRAP_PATHS", "2000")),
            bootstrap_block=int(os.getenv("ACNOPVIZ_BOOTSTRAP_BLOCK", "3")),
        )
