# GDPR Compliance Layer — Design Spec

> **For agentic workers:** Use superpowers:writing-plans to create the implementation plan from this spec.

**Goal:** Make Cognithor GDPR-compliant without breaking existing functionality. Additive changes only — nothing gets removed.

**Date:** 2026-03-28
**Status:** Approved

---

## 1. Consent Manager

**File:** `src/jarvis/security/consent.py`
**DB:** `~/.jarvis/index/consent.db` (SQLCipher encrypted)

### Schema
```sql
CREATE TABLE consent (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel TEXT NOT NULL,        -- telegram, webui, cli, discord, etc.
    consent_type TEXT NOT NULL,   -- data_processing, cloud_llm, osint
    status TEXT NOT NULL,         -- pending, accepted, rejected, withdrawn
    privacy_version TEXT,         -- version of privacy notice shown
    granted_at TEXT,
    withdrawn_at TEXT,
    ip_or_context TEXT,           -- e.g. telegram chat_id, session_id
    created_at TEXT NOT NULL
);
CREATE INDEX idx_consent_user ON consent(user_id, channel, consent_type);
```

### ConsentManager API
```python
class ConsentManager:
    def has_consent(self, user_id: str, channel: str, consent_type: str = "data_processing") -> bool
    def grant_consent(self, user_id: str, channel: str, consent_type: str, context: str = "") -> None
    def withdraw_consent(self, user_id: str, channel: str, consent_type: str = "data_processing") -> None
    def get_user_consents(self, user_id: str) -> list[dict]
    def requires_consent(self, user_id: str, channel: str) -> bool
```

### Channel Integration
- **Telegram** (`channels/telegram.py`): Before processing any message, check `consent_manager.has_consent(user_id, "telegram")`. If not, send privacy notice with InlineKeyboard buttons "Akzeptieren" / "Ablehnen". Store result. If rejected, respond with "Ich kann deine Nachrichten ohne Datenschutz-Einwilligung nicht verarbeiten."
- **WebUI** (`channels/webui.py`): WS message type `consent_check` on connection. Frontend shows banner. Backend waits for `consent_response` before processing.
- **CLI** (`__main__.py`): On first run (no consent in DB for cli channel), show privacy notice text and prompt "Einverstanden? (ja/nein)".
- **Other channels**: Same pattern — check before first message processing.

### Privacy Notice
- Stored in `data/legal/privacy_notice_de.md` and `data/legal/privacy_notice_en.md`
- Versioned (e.g. "1.0") — if version changes, re-consent required
- Content: What data is collected, how it's used, retention periods, user rights, contact info

---

## 2. Data Erasure (Right to be Forgotten)

**File:** Extend `src/jarvis/security/gdpr.py` ErasureManager

### Full Erasure Method
```python
async def erase_all(self, user_id: str, mcp_client: Any = None) -> dict:
    """Delete ALL personal data for user_id across every tier.

    Returns dict with counts per tier.
    """
```

### Tiers to erase (in order):
1. **Processing Logs** — `DataProcessingLog.delete_user_records(user_id)` (exists)
2. **Model Usage Logs** — `ModelUsageLog.delete_user_records(user_id)` (exists)
3. **Consent Records** — `ConsentManager.delete_user(user_id)`
4. **Chat Sessions** — Delete from sessions.db where user matches
5. **Episodic Memory** — Delete files matching user context
6. **Semantic Memory** — Delete indexed chunks by source_user
7. **Entities/Relations** — Delete entities where attributes contain user_id
8. **Vault Notes** — Delete notes tagged with user_id or in user folder
9. **HIM Reports** — Delete reports where target matches
10. **Audit Logs** — Anonymize (replace user_id with hash)

### REST API
- `DELETE /api/v1/user/data` — requires authentication, triggers `erase_all()`
- Returns: `{"erased": {"memories": 12, "entities": 5, "vault_notes": 3, ...}}`

### MCP Tool
- `erase_user_data(user_id, justification)` — RED classification in gatekeeper

---

## 3. Missing Delete Tools

### vault_delete
**File:** `src/jarvis/mcp/vault.py` — add method + register handler

```python
async def vault_delete(self, path: str) -> str:
    """Delete a vault note by path. Returns confirmation or error."""
```

- Validates path (no traversal)
- Deletes the .md file
- Removes from search index
- Gatekeeper: RED

### delete_entity / delete_relation
**File:** `src/jarvis/mcp/memory_server.py` — add methods + register handlers

```python
async def delete_entity(self, name: str) -> str:
    """Delete an entity and all its relations by name."""

async def delete_relation(self, source: str, target: str, relation: str = "") -> str:
    """Delete a specific relation between two entities."""
```

- Gatekeeper: RED for both

---

## 4. TTL Enforcement

### Cron Job
Register in gateway during cron engine setup:
- Job name: `retention_enforcer`
- Schedule: `0 3 * * *` (daily at 03:00)
- Handler: calls `RetentionEnforcer.enforce()` + HIM cleanup + episodic cleanup

### Default Retention Periods
Add to config with defaults:
```python
class RetentionConfig(BaseModel):
    episodic_days: int = 90
    processing_log_days: int = 90
    model_usage_log_days: int = 180
    him_report_days: int = 30
    session_days: int = 180
    vault_osint_days: int = 30
```

### HIM Report Cleanup
- Vault notes in `recherchen/osint/` older than `him_report_days` get deleted
- Uses `vault_delete()` internally

### Episodic Memory Cleanup
- Set `episodic_retention_days` default to 90 in MemoryManager config
- `prune_old()` already exists, just needs the default set

---

## 5. SQLCipher Encryption at Rest

### New Dependency
Add to `pyproject.toml`: `pysqlcipher3>=1.2.0` under `[security]` extra

### Encrypted Connection Wrapper
**File:** `src/jarvis/security/encrypted_db.py`

```python
def encrypted_connect(db_path: str, key: str | None = None) -> sqlite3.Connection:
    """Open a SQLCipher-encrypted SQLite database.

    If key is None, reads from JARVIS_DB_KEY env var.
    If env var is empty, auto-generates and stores in credential store.
    Falls back to unencrypted sqlite3 if pysqlcipher3 is not installed.
    """
```

### Migration Strategy
- On startup, check if each DB is encrypted (try opening with key)
- If unencrypted: create new encrypted DB, copy all data, replace original
- One-time migration, logged clearly
- Fallback: if `pysqlcipher3` not installed, warn and use unencrypted (graceful degradation)

### Affected Databases
- `~/.jarvis/index/memory_traces.db`
- `~/.jarvis/index/memory_proposals.db`
- `~/.jarvis/index/memory_governance.db`
- `~/.jarvis/index/memory_runs.db`
- `~/.jarvis/index/knowledge_claims.db`
- `~/.jarvis/index/consent.db` (new)
- `~/.jarvis/memory/sessions/sessions.db`
- `~/.jarvis/memory/knowledge_qa.db`
- `~/.jarvis/memory/knowledge_lineage.db`
- Evolution goal-scoped indexes

### Key Management
- Primary: `JARVIS_DB_KEY` environment variable
- Fallback: Auto-generated 32-byte key stored in credential store (`~/.jarvis/credentials/db_key.enc`)
- The credential store itself uses `JARVIS_CREDENTIAL_KEY` (already exists)

---

## 6. Cloud LLM Consent Flow

### Integration Point
**File:** `src/jarvis/core/model_router.py` — wrap the `_call_api()` method

Before any cloud API call:
1. Check `consent_manager.has_consent(user_id, "cloud_llm_" + provider)`
2. If not consented: raise `CloudConsentRequired(provider)`
3. Gateway catches this and prompts user: "Deine Anfrage wird an {provider} gesendet. Erlaubst du das? (ja/nein/immer)"
4. "immer" stores permanent consent for that provider

### Processing Log
Every cloud call logged:
```python
processing_log.record(
    user_id=user_id,
    category="llm_inference",
    purpose="query_processing",
    data_types=["user_query", "memory_context"],
    recipient=provider_name,
    legal_basis="consent",
)
```

### Config
```python
class CloudPrivacyConfig(BaseModel):
    consent_required: bool = True
    log_cloud_calls: bool = True
    allowed_providers: list[str] = Field(default_factory=list)  # empty = all with consent
```

---

## 7. Data Access / Export API

### REST Endpoint
`GET /api/v1/user/data?format=json` — authenticated

Returns structured JSON:
```json
{
    "user_id": "...",
    "exported_at": "...",
    "memories": [...],
    "entities": [...],
    "vault_notes": [...],
    "sessions": [...],
    "processing_log": [...],
    "consents": [...],
    "him_reports": [...]
}
```

### MCP Tool
`export_user_data(user_id)` — GREEN classification (read-only)

---

## 8. Legal Documents

### Privacy Notice (`data/legal/privacy_notice_de.md`)
German DSGVO-compliant notice covering:
- Identity of data controller (configurable)
- What data is collected and why
- Legal basis (consent)
- Retention periods
- User rights (access, erasure, portability, objection)
- Third-party recipients (cloud LLM providers)
- Contact information

### DPIA Template (`data/legal/dpia_template.md`)
Data Protection Impact Assessment template for:
- HIM/OSINT investigations
- Cloud LLM usage
- Memory/knowledge graph storage

---

## Integration Summary

| Existing File | Change |
|--------------|--------|
| `config.py` | Add RetentionConfig, CloudPrivacyConfig |
| `gatekeeper.py` | Add vault_delete, delete_entity, delete_relation, erase_user_data to RED |
| `gateway/gateway.py` | Wire ConsentManager, add retention cron |
| `channels/telegram.py` | Add consent check before message processing |
| `mcp/vault.py` | Add vault_delete method + handler |
| `mcp/memory_server.py` | Add delete_entity, delete_relation handlers |
| `security/gdpr.py` | Extend ErasureManager with erase_all() |
| `core/model_router.py` | Add cloud consent check before API calls |
| `config_routes.py` | Add /api/v1/user/data endpoints |

| New File | Purpose |
|----------|---------|
| `security/consent.py` | ConsentManager |
| `security/encrypted_db.py` | SQLCipher wrapper + migration |
| `data/legal/privacy_notice_de.md` | German privacy notice |
| `data/legal/privacy_notice_en.md` | English privacy notice |
| `data/legal/dpia_template.md` | DPIA template |

---

## Non-Breaking Guarantees

1. **Graceful degradation**: If `pysqlcipher3` not installed, falls back to unencrypted SQLite with WARNING
2. **Consent opt-out**: If `consent_required: false` in config, consent checks are skipped (for development/testing)
3. **Existing data preserved**: Migration copies data, does not delete originals until verified
4. **No API changes**: All existing MCP tools work exactly as before
5. **Performance**: SQLCipher adds ~10-15% overhead on DB operations; acceptable for background agent

---

*GDPR Compliance Layer Spec v1.0 | Apache 2.0*
