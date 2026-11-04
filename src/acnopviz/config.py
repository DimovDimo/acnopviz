from __future__ import annotations

import os
from dataclasses import dataclass
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
