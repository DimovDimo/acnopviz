import json

from acnopviz.cli import main


def test_seed_and_report_cli(tmp_path, capsys):
    db = tmp_path / "cli.db"
    csv_dir = tmp_path / "csv"
    assert main(["seed", "--db", str(db), "--csv-dir", str(csv_dir), "--seed", "7"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["manifest"]["seed"] == 7
    assert (csv_dir / "manifest.json").exists()
    assert main(["report", "--db", str(db)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["overview"]["cash"] > 0
    assert report["data_quality"]["failed"] == 0
    assert len(report["recommendations"]) > 0


def test_seed_replace_cli(tmp_path, capsys):
    db = tmp_path / "cli.db"
    main(["seed", "--db", str(db), "--csv-dir", str(tmp_path / "c1"), "--seed", "1"])
    capsys.readouterr()
    main(["seed", "--db", str(db), "--csv-dir", str(tmp_path / "c2"), "--seed", "2", "--replace"])
    out = json.loads(capsys.readouterr().out)
    assert out["manifest"]["seed"] == 2
