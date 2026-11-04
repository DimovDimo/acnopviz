from __future__ import annotations


def test_recommendation_detail_and_review_accept_analysis_parameters(client):
    # Find a horizon-specific recommendation that is absent from the default horizon.
    default_ids = {r["id"] for r in client.get("/api/recommendations").json()["items"]}
    target = None
    for horizon in range(1, 13):
        for rec in client.get(f"/api/recommendations?horizon={horizon}").json()["items"]:
            if rec["id"] not in default_ids:
                target = (horizon, rec["id"])
                break
        if target:
            break
    assert target is not None
    horizon, rec_id = target
    assert client.get(f"/api/recommendations/{rec_id}?horizon={horizon}").status_code == 200
    r = client.patch(
        f"/api/recommendations/{rec_id}/review?horizon={horizon}",
        json={"status": "accepted", "note": "horizon-specific"},
    )
    assert r.status_code == 200
    assert (
        client.get(f"/api/recommendations/{rec_id}?horizon={horizon}").json()["review_status"]
        == "accepted"
    )


def test_invalid_settings_fail_fast(tmp_path):
    from acnopviz.api import create_app
    from acnopviz.config import Settings

    try:
        create_app(Settings(db_path=tmp_path / "x.db", bootstrap_block=0))
    except ValueError:
        return
    raise AssertionError("invalid bootstrap_block should fail fast")


def test_import_template_version_matches_package(client):
    from acnopviz import __version__

    template = client.get("/api/import/template").json()
    assert template["manifest"]["version"] == __version__
