import sqlite3

from control_plane.audit import AuditLog


def test_hash_chain_verifies(tmp_path):
    audit = AuditLog(str(tmp_path / "audit.db"))
    audit.append(event_id="event-1", actor="alice", event_type="task.created", subject_id="task-1", payload={"ok": True})
    audit.append(event_id="event-2", actor="bob", event_type="approval.denied", subject_id="approval-1", payload={"why": "no"})
    assert audit.verify_chain() == (True, 2)


def test_audit_rows_reject_update_and_delete(tmp_path):
    path = str(tmp_path / "audit.db")
    audit = AuditLog(path)
    audit.append(event_id="event-1", actor="alice", event_type="test", subject_id="x", payload={})
    db = sqlite3.connect(path)
    try:
        try:
            db.execute("UPDATE audit_events SET actor='mallory' WHERE event_id='event-1'")
            assert False, "update should be rejected"
        except sqlite3.IntegrityError:
            pass
        try:
            db.execute("DELETE FROM audit_events WHERE event_id='event-1'")
            assert False, "delete should be rejected"
        except sqlite3.IntegrityError:
            pass
    finally:
        db.close()
    assert audit.verify_chain() == (True, 1)
