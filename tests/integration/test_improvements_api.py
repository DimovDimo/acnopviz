from __future__ import annotations

from scripts.generate_improvement_fixtures import invalid_bundle, valid_bundle


def test_cash_calendar_endpoint(client):
    r = client.get("/api/cash-calendar?horizon=3")
    assert r.status_code == 200
    body = r.json()
    assert len(body["months"]) == 3
    assert body["prob_negative"] >= 0
    assert client.get("/api/cash-calendar?horizon=13").status_code == 422


def test_backtest_endpoint(client):
    r = client.get("/api/backtest?horizon=3&min_train=9")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["fold_count"] > 0
    assert client.get("/api/backtest?horizon=7").status_code == 422
    assert client.get("/api/backtest?min_train=5").status_code == 422


def test_import_validate_is_read_only(client):
    before = client.get("/api/dataset/manifest").json()
    bad = invalid_bundle()
    r = client.post("/api/import/validate", json=bad)
    assert r.status_code == 200 and r.json()["ok"] is False
    assert client.get("/api/dataset/manifest").json() == before


def test_import_commit_flow_and_fingerprint(client):
    v = valid_bundle()
    report = client.post("/api/import/validate", json=v).json()
    assert report["ok"]
    # Wrong confirmation / fingerprint.
    assert (
        client.post(
            "/api/import/commit", json={**v, "confirm": "NO", "fingerprint": report["fingerprint"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/import/commit", json={**v, "confirm": "REPLACE", "fingerprint": "0" * 64}
        ).status_code
        == 409
    )
    # Existing review is cleared by replacement.
    rec = client.get("/api/recommendations").json()["items"][0]
    client.patch(
        f"/api/recommendations/{rec['id']}/review", json={"status": "accepted", "note": "old"}
    )
    r = client.post(
        "/api/import/commit", json={**v, "confirm": "REPLACE", "fingerprint": report["fingerprint"]}
    )
    assert r.status_code == 200 and r.json()["ok"]
    manifest = client.get("/api/dataset/manifest").json()
    assert manifest["counts"]["customers"] == 2
    assert manifest["seed"] == 111
    audit = client.get("/api/audit").json()["items"]
    assert audit[0]["event_type"] == "dataset.import"
    assert client.get("/api/recommendations").json()["count"] >= 0


def test_import_template(client):
    t = client.get("/api/import/template").json()
    assert set(t["files"]) == {"customers", "vendors", "invoices", "bills", "cash_transactions"}
    assert t["manifest"]["synthetic"] is True


def test_import_commit_invalid_bundle_400(client):
    before = client.get("/api/dataset/manifest").json()
    bad = invalid_bundle()
    r = client.post(
        "/api/import/commit", json={**bad, "confirm": "REPLACE", "fingerprint": "0" * 64}
    )
    assert r.status_code == 400
    assert client.get("/api/dataset/manifest").json() == before
