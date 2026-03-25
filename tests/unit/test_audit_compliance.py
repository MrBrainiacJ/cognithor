"""Tests for audit compliance features: HMAC, blockchain, export, breach."""

import hashlib
import hmac
import json
import tempfile
from pathlib import Path

import pytest


class TestHMACSignatures:
    """HMAC-SHA256 signatures on audit trail entries."""

    @pytest.fixture
    def audit_trail(self, tmp_path):
        from jarvis.security.audit import AuditTrail

        return AuditTrail(
            log_path=tmp_path / "test_audit.jsonl",
            hmac_key=b"test-secret-key-32bytes-long!!!!",
        )

    def test_record_includes_hmac_field(self, audit_trail):
        from jarvis.models import AuditEntry as GateAuditEntry, GateStatus, RiskLevel

        entry = GateAuditEntry(
            session_id="test-session",
            action_tool="test_tool",
            action_params_hash="abc123",
            decision_status=GateStatus.ALLOW,
            decision_reason="test",
            risk_level=RiskLevel.GREEN,
            policy_name="default",
        )
        audit_trail.record(entry)
        # Read the JSONL and verify hmac field exists
        lines = audit_trail._log_path.read_text(encoding="utf-8").strip().split("\n")
        record = json.loads(lines[-1])
        assert "hmac" in record
        assert len(record["hmac"]) == 64  # SHA-256 hex digest

    def test_hmac_is_deterministic(self, audit_trail):
        from jarvis.models import AuditEntry as GateAuditEntry, GateStatus, RiskLevel

        entry = GateAuditEntry(
            session_id="s1",
            action_tool="tool1",
            action_params_hash="h1",
            decision_status=GateStatus.ALLOW,
            decision_reason="r1",
            risk_level=RiskLevel.GREEN,
            policy_name="p1",
        )
        h1 = audit_trail.record(entry)

        # Recompute HMAC manually
        lines = audit_trail._log_path.read_text(encoding="utf-8").strip().split("\n")
        record = json.loads(lines[-1])
        data_for_hmac = record["hash"]
        expected = hmac.new(
            b"test-secret-key-32bytes-long!!!!",
            data_for_hmac.encode(),
            hashlib.sha256,
        ).hexdigest()
        assert record["hmac"] == expected

    def test_no_hmac_when_key_is_none(self, tmp_path):
        from jarvis.security.audit import AuditTrail
        from jarvis.models import AuditEntry as GateAuditEntry, GateStatus, RiskLevel

        trail = AuditTrail(log_path=tmp_path / "no_hmac.jsonl", hmac_key=None)
        entry = GateAuditEntry(
            session_id="s1",
            action_tool="tool1",
            action_params_hash="h1",
            decision_status=GateStatus.ALLOW,
            decision_reason="r1",
            risk_level=RiskLevel.GREEN,
            policy_name="p1",
        )
        trail.record(entry)
        lines = trail._log_path.read_text(encoding="utf-8").strip().split("\n")
        record = json.loads(lines[-1])
        assert "hmac" not in record

    def test_verify_chain_with_hmac(self, audit_trail):
        from jarvis.models import AuditEntry as GateAuditEntry, GateStatus, RiskLevel

        for i in range(5):
            entry = GateAuditEntry(
                session_id=f"s{i}",
                action_tool=f"tool{i}",
                action_params_hash=f"h{i}",
                decision_status=GateStatus.ALLOW,
                decision_reason=f"r{i}",
                risk_level=RiskLevel.GREEN,
                policy_name="p",
            )
            audit_trail.record(entry)

        valid, total, broken = audit_trail.verify_chain()
        assert valid is True
        assert total == 5
        assert broken == -1


class TestBlockchainAnchoring:
    """Periodic hash anchoring to external store."""

    @pytest.fixture
    def audit_trail(self, tmp_path):
        from jarvis.security.audit import AuditTrail
        return AuditTrail(log_path=tmp_path / "bc_audit.jsonl")

    def test_get_anchor_returns_hash_and_count(self, audit_trail):
        from jarvis.models import AuditEntry as GateAuditEntry, GateStatus, RiskLevel
        for i in range(3):
            entry = GateAuditEntry(
                session_id=f"s{i}", action_tool=f"tool{i}", action_params_hash=f"h{i}",
                decision_status=GateStatus.ALLOW, decision_reason=f"r{i}",
                risk_level=RiskLevel.GREEN, policy_name="p",
            )
            audit_trail.record(entry)
        anchor = audit_trail.get_anchor()
        assert "hash" in anchor
        assert anchor["entry_count"] == 3
        assert len(anchor["hash"]) == 64
        assert "timestamp" in anchor

    def test_anchor_changes_after_new_entry(self, audit_trail):
        from jarvis.models import AuditEntry as GateAuditEntry, GateStatus, RiskLevel
        entry = GateAuditEntry(
            session_id="s1", action_tool="t1", action_params_hash="h1",
            decision_status=GateStatus.ALLOW, decision_reason="r1",
            risk_level=RiskLevel.GREEN, policy_name="p",
        )
        audit_trail.record(entry)
        anchor1 = audit_trail.get_anchor()
        entry2 = GateAuditEntry(
            session_id="s2", action_tool="t2", action_params_hash="h2",
            decision_status=GateStatus.ALLOW, decision_reason="r2",
            risk_level=RiskLevel.GREEN, policy_name="p",
        )
        audit_trail.record(entry2)
        anchor2 = audit_trail.get_anchor()
        assert anchor1["hash"] != anchor2["hash"]
        assert anchor2["entry_count"] == 2
