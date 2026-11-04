from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .analysis.engine import build_recommendations, data_quality, liquidity_simulation, overview
from .config import Settings
from .money import dollars
from .schemas import ReviewRequest, ScenarioRequest
from .storage import Storage
from .synthetic import generate_dataset

STATIC_DIR = Path(__file__).parent / "static"


def csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def csv_response(rows: list[dict[str, Any]], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows([{k: csv_safe(v) for k, v in row.items()} for row in rows])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    storage = Storage(settings.db_path)
    if storage.is_empty():
        storage.seed(generate_dataset(settings.seed, settings.as_of))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    app = FastAPI(
        title="acnopviz",
        version=__version__,
        description="Explainable accounting optimization suggestions on a synthetic ledger. Human review only; no payment execution.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.storage = storage

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        # No X-Frame-Options: the app is designed to run inside the Arena preview iframe.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def get_storage() -> Iterator[Storage]:
        yield app.state.storage

    Store = Depends(get_storage)

    @app.get("/api/health", tags=["system"])
    def health(store: Storage = Store) -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "database": str(store.path),
            "synthetic": True,
            "as_of": store.load()["meta"]["as_of"],
        }

    @app.get("/api/overview", tags=["analytics"])
    def get_overview(store: Storage = Store) -> dict:
        data = store.load()
        result = overview(data)
        result["recommendation_count"] = len(
            build_recommendations(
                data,
                paths=settings.bootstrap_paths,
                block=settings.bootstrap_block,
                seed=settings.seed,
            )
        )
        result["data_quality"] = data_quality(data)["status"]
        return result

    @app.get("/api/recommendations", tags=["analytics"])
    def get_recommendations(
        financing_rate: float = Query(0.08, ge=0, le=0.5),
        horizon: int = Query(6, ge=1, le=12),
        store: Storage = Store,
    ) -> dict:
        data = store.load()
        recs = build_recommendations(
            data,
            financing_rate,
            horizon,
            settings.bootstrap_paths,
            settings.bootstrap_block,
            settings.seed,
        )
        return {
            "as_of": data["meta"]["as_of"],
            "count": len(recs),
            "items": recs,
            "disclaimer": "Synthetic demo. Suggestions are review prompts, not accounting, tax, legal, or investment advice.",
        }

    @app.get("/api/recommendations/{recommendation_id}", tags=["analytics"])
    def get_recommendation(recommendation_id: str, store: Storage = Store) -> dict:
        recs = build_recommendations(
            store.load(),
            paths=settings.bootstrap_paths,
            block=settings.bootstrap_block,
            seed=settings.seed,
        )
        for rec in recs:
            if rec["id"] == recommendation_id:
                return rec
        raise HTTPException(404, "Recommendation not found")

    @app.patch("/api/recommendations/{recommendation_id}/review", tags=["review"])
    def review_recommendation(
        recommendation_id: str, body: ReviewRequest, store: Storage = Store
    ) -> dict:
        recs = build_recommendations(
            store.load(),
            paths=settings.bootstrap_paths,
            block=settings.bootstrap_block,
            seed=settings.seed,
        )
        if not any(r["id"] == recommendation_id for r in recs):
            raise HTTPException(404, "Recommendation not found")
        return store.set_review(recommendation_id, body.status, body.note.strip())

    @app.post("/api/scenario", tags=["analytics"])
    def run_scenario(body: ScenarioRequest, store: Storage = Store) -> dict:
        return liquidity_simulation(
            store.load(),
            body.horizon,
            settings.bootstrap_paths,
            settings.bootstrap_block,
            settings.seed,
            body.financing_rate,
            body.recovery_uplift,
            body.expense_reduction,
        )

    @app.get("/api/transactions", tags=["data"])
    def get_transactions(
        type: str = Query("all", pattern="^(all|ar|ap|cash)$"),
        search: str = Query("", max_length=100),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        store: Storage = Store,
    ) -> dict:
        data = store.load()
        customers = {c["id"]: c["name"] for c in data["customers"]}
        vendors = {v["id"]: v["name"] for v in data["vendors"]}
        rows = []
        if type in ("all", "ar"):
            rows += [
                {
                    "id": r["id"],
                    "type": "AR",
                    "date": r["issue_date"],
                    "party": customers[r["customer_id"]],
                    "description": f"Due {r['due_date']}",
                    "amount": dollars(r["amount_cents"]),
                    "status": "paid" if r["paid_date"] else "open",
                }
                for r in data["invoices"]
            ]
        if type in ("all", "ap"):
            rows += [
                {
                    "id": r["id"],
                    "type": "AP",
                    "date": r["issue_date"],
                    "party": vendors[r["vendor_id"]],
                    "description": r["invoice_number"],
                    "amount": -dollars(r["amount_cents"]),
                    "status": "paid" if r["paid_date"] else "open",
                }
                for r in data["bills"]
            ]
        if type in ("all", "cash"):
            rows += [
                {
                    "id": r["id"],
                    "type": "Cash",
                    "date": r["txn_date"],
                    "party": "Bank",
                    "description": r["description"],
                    "amount": dollars(r["amount_cents"]),
                    "status": "settled",
                }
                for r in data["cash_transactions"]
            ]
        q = search.lower().strip()
        if q:
            rows = [r for r in rows if q in " ".join(str(v) for v in r.values()).lower()]
        rows.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
        return {
            "total": len(rows),
            "limit": limit,
            "offset": offset,
            "items": rows[offset : offset + limit],
        }

    @app.get("/api/data-quality", tags=["data"])
    def get_data_quality(store: Storage = Store) -> dict:
        return data_quality(store.load())

    @app.get("/api/audit", tags=["review"])
    def get_audit(limit: int = Query(100, ge=1, le=500), store: Storage = Store) -> dict:
        return {"items": store.audit_log(limit)}

    @app.get("/api/dataset/manifest", tags=["data"])
    def get_manifest(store: Storage = Store) -> dict:
        data = store.load()
        return {
            "name": "acnopviz-synthetic-ledger",
            "version": __version__,
            "synthetic": True,
            "seed": int(data["meta"]["seed"]),
            "as_of": data["meta"]["as_of"],
            "currency": data["meta"]["currency"],
            "opening_cash_cents": int(data["meta"]["opening_cash_cents"]),
            "counts": {
                k: len(data[k])
                for k in ("customers", "vendors", "invoices", "bills", "cash_transactions")
            },
        }

    @app.get("/api/export/recommendations.csv", tags=["export"])
    def export_recommendations(store: Storage = Store) -> StreamingResponse:
        recs = build_recommendations(
            store.load(),
            paths=settings.bootstrap_paths,
            block=settings.bootstrap_block,
            seed=settings.seed,
        )
        rows = [
            {
                "id": r["id"],
                "kind": r["kind"],
                "entity": r["entity"],
                "title": r["title"],
                "estimated_value": r["estimated_value"],
                "value_label": r["value_label"],
                "confidence": r["confidence"],
                "review_status": r["review_status"],
                "review_note": r["review_note"],
                "action": r["action"],
            }
            for r in recs
        ]
        return csv_response(rows, "acnopviz-recommendations.csv")

    @app.get("/api/export/transactions.csv", tags=["export"])
    def export_transactions(store: Storage = Store) -> StreamingResponse:
        all_rows = []
        offset = 0
        while True:
            page = get_transactions("all", "", 500, offset, store)
            all_rows.extend(page["items"])
            offset += 500
            if offset >= page["total"]:
                break
        return csv_response(all_rows, "acnopviz-transactions.csv")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
