from __future__ import annotations

import pytest

from control_plane.audit import AuditLog
from control_plane.service import ControlPlaneService
from control_plane.store import TaskStore


@pytest.fixture
def service(tmp_path):
    database = str(tmp_path / "control-plane.sqlite3")
    return ControlPlaneService(TaskStore(database), AuditLog(database), execution_enabled=False)
