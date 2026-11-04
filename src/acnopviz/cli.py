from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from .analysis.engine import build_recommendations, data_quality, overview
from .config import Settings
from .storage import Storage
from .synthetic import generate_dataset, write_csv_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acnopviz", description="Accounting optimization suggestions (synthetic demo)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed", help="Generate deterministic synthetic CSVs and SQLite database")
    seed.add_argument("--seed", type=int, default=20261104)
    seed.add_argument("--as-of", default="2026-10-31")
    seed.add_argument("--db", type=Path, default=Path("data/acnopviz.db"))
    seed.add_argument("--csv-dir", type=Path, default=Path("data/synthetic"))
    seed.add_argument(
        "--replace", action="store_true", help="Replace existing demo data and review state"
    )
    serve = sub.add_parser("serve", help="Run the web application")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    report = sub.add_parser("report", help="Print a JSON analytics report")
    report.add_argument("--db", type=Path, default=Path("data/acnopviz.db"))
    args = parser.parse_args(argv)

    if args.command == "seed":
        dataset = generate_dataset(args.seed, args.as_of)
        manifest = write_csv_dataset(dataset, args.csv_dir)
        storage = Storage(args.db)
        storage.seed(dataset, replace=args.replace or storage.is_empty())
        print(json.dumps({"database": str(args.db), "manifest": manifest}, indent=2))
        return 0
    if args.command == "serve":
        settings = Settings.from_env()
        uvicorn.run(
            "acnopviz.api:app",
            host=args.host or settings.host,
            port=args.port or settings.port,
            reload=False,
        )
        return 0
    if args.command == "report":
        data = Storage(args.db).load()
        print(
            json.dumps(
                {
                    "overview": overview(data),
                    "data_quality": data_quality(data),
                    "recommendations": build_recommendations(data),
                },
                indent=2,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
