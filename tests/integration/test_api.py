import csv
import io
import time

import pytest


def test_health_and_security_headers(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_overview_and_manifest(client):
    o = client.get("/api/overview").json()
    assert o["cash"] > 0 and o["recommendation_count"] > 0
    m = client.get("/api/dataset/manifest").json()
    assert m["synthetic"] is True and m["counts"]["invoices"] > 200


def test_recommendations_and_detail(client):
    data = client.get("/api/recommendations").json()
    assert data["count"] == len(data["items"])
    rec = data["items"][0]
    detail = client.get(f"/api/recommendations/{rec['id']}").json()
    assert detail["id"] == rec["id"]
    assert client.get("/api/recommendations/does-not-exist").status_code == 404


def test_review_flow_persists(client, settings):
    rec = client.get("/api/recommendations").json()["items"][0]
    payload = {"status": "accepted", "note": "Reviewed with controller"}
    r = client.patch(f"/api/recommendations/{rec['id']}/review", json=payload)
    assert r.status_code == 200
    again = client.get(f"/api/recommendations/{rec['id']}").json()
    assert again["review_status"] == "accepted"
    assert again["review_note"] == "Reviewed with controller"
    audit = client.get("/api/audit").json()["items"]
    assert audit[0]["entity_id"] == rec["id"]
    # New app instance on same DB preserves review state.
    from fastapi.testclient import TestClient

    from acnopviz.api import create_app

    with TestClient(create_app(settings)) as c2:
        assert c2.get(f"/api/recommendations/{rec['id']}").json()["review_status"] == "accepted"


def test_review_validation(client):
    rec = client.get("/api/recommendations").json()["items"][0]
    assert (
        client.patch(
            f"/api/recommendations/{rec['id']}/review", json={"status": "bogus"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/recommendations/{rec['id']}/review", json={"status": "new", "note": "x" * 1001}
        ).status_code
        == 422
    )
    assert (
        client.patch("/api/recommendations/missing/review", json={"status": "new"}).status_code
        == 404
    )


def test_scenario_validation_and_monotonicity(client):
    base = client.post("/api/scenario", json={}).json()
    better = client.post(
        "/api/scenario", json={"expense_reduction": 0.1, "recovery_uplift": 0.2}
    ).json()
    assert better["scenario"]["median_ending_cash"] > base["scenario"]["median_ending_cash"]
    assert better["scenario"]["prob_negative"] <= base["scenario"]["prob_negative"]
    assert client.post("/api/scenario", json={"horizon": 99}).status_code == 422
    assert client.post("/api/scenario", json={"financing_rate": -0.1}).status_code == 422
    assert client.post("/api/scenario", json={"expense_reduction": 0.9}).status_code == 422


def test_transactions_filter_search_pagination(client):
    all_rows = client.get("/api/transactions?limit=500").json()
    ar = client.get("/api/transactions?type=ar&limit=500").json()
    assert all_rows["total"] > ar["total"]
    assert all(r["type"] == "AR" for r in ar["items"])
    page = client.get("/api/transactions?limit=5&offset=5").json()
    assert len(page["items"]) == 5 and page["offset"] == 5
    search = client.get("/api/transactions?search=Northwind&limit=500").json()
    assert search["total"] > 0
    assert client.get("/api/transactions?type=bad").status_code == 422
    assert client.get("/api/transactions?limit=0").status_code == 422


def test_data_quality_endpoint(client):
    q = client.get("/api/data-quality").json()
    assert q["failed"] == 0 and q["warnings"] == 1


def test_csv_exports_and_formula_protection(client):
    rec = client.get("/api/recommendations").json()["items"][0]
    client.patch(
        f"/api/recommendations/{rec['id']}/review",
        json={"status": "new", "note": '=HYPERLINK("http://evil")'},
    )
    r = client.get("/api/export/recommendations.csv")
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert rows[0]["review_note"].startswith("'=")
    tx = client.get("/api/export/transactions.csv")
    tx_rows = list(csv.DictReader(io.StringIO(tx.text)))
    total = client.get("/api/transactions?limit=1").json()["total"]
    assert len(tx_rows) == total


def test_static_dashboard_and_openapi(client):
    r = client.get("/")
    assert r.status_code == 200 and "acnopviz" in r.text
    assert client.get("/static/app.js").status_code == 200
    spec = client.get("/openapi.json").json()
    assert "/api/scenario" in spec["paths"]


@pytest.mark.slow
def test_recommendations_performance(client):
    start = time.perf_counter()
    r = client.get("/api/recommendations")
    elapsed = time.perf_counter() - start
    assert r.status_code == 200
    assert elapsed < 2.0, f"recommendations took {elapsed:.2f}s"


def test_search_is_parameterized_and_safe(client):
    r = client.get("/api/transactions", params={"search": "' OR 1=1 --", "limit": 10})
    assert r.status_code == 200
    assert r.json()["total"] == 0
