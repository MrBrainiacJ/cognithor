# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.78.2+ | Yes       |
| 0.71–0.78.1 | Upgrade recommended (GHSA-cognithor-001) |
| < 0.71  | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in Cognithor, please report it responsibly:

1. **Do NOT open a public issue.** Security vulnerabilities must be reported privately.
2. **Email:** Send a detailed report to the repository owner via GitHub's private vulnerability reporting feature (Security tab → "Report a vulnerability").
3. **Include:**
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We aim to acknowledge reports within 48 hours and provide a fix within 7 days for critical issues.

## Security Architecture

Cognithor implements defense-in-depth with multiple security layers (supporting Ollama and LM Studio as local backends):

- **Gatekeeper** — Deterministic policy engine (no LLM). Every tool call is validated against security policies with 4 risk levels: GREEN (auto-approve) → YELLOW (inform) → ORANGE (require approval) → RED (block).
- **Sandbox** — Multi-level execution isolation: Process-level → Linux Namespaces (nsjail) → Docker containers → Windows Job Objects.
- **Audit Trail** — Append-only JSONL log with SHA-256 hash chain. Tamper-evident. Credentials are masked before logging.
- **Credential Vault** — Fernet-encrypted (AES-256) per-agent secret storage. Keys never appear in logs or API responses.
- **Input Sanitization** — Protection against shell injection, path traversal, and prompt injection attacks.
- **Path Sandbox** — File operations restricted to explicitly allowed directories.
- **Red-Teaming** — Automated offensive security test suite (1,425 LOC).

## Runtime Token Protection (v0.26.0+)

All channel tokens (Telegram, Discord, Slack, Teams, WhatsApp, API, WebUI, Matrix, Mattermost) are encrypted in memory using ephemeral Fernet keys (AES-256). Tokens are never stored as plaintext in RAM after initialization.

- **Encryption**: `SecureTokenStore` generates a random Fernet key at startup. All tokens are encrypted immediately upon channel construction.
- **Access**: Tokens are decrypted on-demand via `@property` accessors. External callers see plaintext — internal storage is always ciphertext.
- **Fallback**: Without the `cryptography` package, Base64 obfuscation is used with a logged warning.
- **Scope**: Runtime protection against memory dumps. Does not replace disk-level encryption for config files.

## TLS Support (v0.26.0+)

Webhook servers (Teams, WhatsApp) and HTTP servers (API, WebUI) support optional TLS:

- Configure `ssl_certfile` and `ssl_keyfile` in `security` section of `config.yaml`
- Minimum TLS 1.2 enforced (`ssl.TLSVersion.TLSv1_2`)
- Non-localhost servers without TLS log a `WARNING` at startup

## File-Size Limits (v0.26.0+)

All upload and processing paths enforce size limits to prevent resource exhaustion:

| Path | Limit | Constant |
|------|-------|----------|
| Document extraction (`media.py`) | 50 MB | `MAX_EXTRACT_FILE_SIZE` |
| Audio transcription (`media.py`) | 100 MB | `MAX_AUDIO_FILE_SIZE` |
| Code execution (`code_tools.py`) | 1 MB | `MAX_CODE_SIZE` |
| WebUI file upload (`webui.py`) | 50 MB | `MAX_UPLOAD_SIZE` |
| Telegram document download (`telegram.py`) | 50 MB | `MAX_DOCUMENT_SIZE` |

## Credential Handling

- API keys in configuration are masked (`***`) in all API responses by default.
- The `.env` file (`~/.jarvis/.env`) is excluded from version control via `.gitignore`.
- The Control Center API never writes masked placeholder values (`***`) back to configuration files.

## Past Advisories

### GHSA-cognithor-001 — Unauthenticated Master Token Disclosure (CRITICAL)

- **CVSS**: 9.8 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H)
- **Affected**: <= 0.78.1
- **Fixed in**: 0.78.2
- **CWE**: CWE-306 (Missing Authentication for Critical Function), CWE-200 (Exposure of Sensitive Information)
- **Description**: The `/api/v1/bootstrap` endpoint returned the master bearer token without authentication. Combined with the default `0.0.0.0` bind, any network-reachable host could steal the token and access all protected API endpoints.
- **Fix**: Bootstrap endpoint restricted to loopback addresses only; default API bind changed from `0.0.0.0` to `127.0.0.1`.
- **Reported by**: [Offgrid Security](https://www.offgridsec.com/) — responsible disclosure

## Acknowledgments

We thank the following researchers for responsibly disclosing security issues:

- **[Offgrid Security](https://www.offgridsec.com/)** — GHSA-cognithor-001 (April 2026)

## Dependencies

We regularly review dependencies for known vulnerabilities. If you find a vulnerable dependency, please report it using the process above.
