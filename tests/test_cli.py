import json
import sys

from control_plane.cli import main


def test_cli_init_and_verify(tmp_path, monkeypatch, capsys):
    database = str(tmp_path / "cli.db")
    monkeypatch.setattr(sys, "argv", ["ds3-control-plane", "init-db", "--database", database])
    main()
    assert json.loads(capsys.readouterr().out)["initialized"] is True
    monkeypatch.setattr(sys, "argv", ["ds3-control-plane", "verify-audit", "--database", database])
    main()
    assert json.loads(capsys.readouterr().out) == {"valid": True, "events_checked": 0}
