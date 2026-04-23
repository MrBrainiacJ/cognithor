# Video Input via vLLM — Design Spec

**Status:** Brainstorming approved 2026-04-23, ready for implementation plan.

**Goal:** Let Cognithor users attach or paste videos in the chat, have them analyzed end-to-end by Qwen3.6-27B (or any vLLM-served VLM with video support), and receive a response referring to visual content across time. No frame-extraction workarounds — this rides on vLLM's native `video_url` content-item, which Qwen3.6-27B's modelcard explicitly supports.

**Non-goal:** Video generation. Video output. Frame-extraction fallbacks when vLLM is unavailable (Ollama has no vision, let alone video — video requests on a non-vLLM backend hard-error). YouTube URL support (Qwen's examples use direct `.mp4` URLs; YouTube needs `yt-dlp` and cookie-handling which is out of scope).

---

## Approved Decisions (Brainstorming Outcomes)

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Scope:** URL paste + local file upload (Option B) | URL-only is too limiting — the important video use-cases (screencasts, meetings, drones) are local files |
| 2 | **Transport for local uploads:** local HTTP file-server (Option B2) | Stable, no reliance on vLLM `file://` support. Matches how external URLs already work — vLLM fetches via HTTP |
| 3 | **Frame sampling:** adaptive buckets via `ffprobe` duration detection (Option Z) | Fixed count (X) wastes detail on short clips, fixed fps (Y) blows context on long videos. Adaptive is the only option that gives sensible behavior across the full 5 s – 60 min range |
| 4 | **Flutter attach UX:** Paperclip menu with explicit "Video hochladen" entry (Option A) | Discoverability without disruption. Dedicated video button (B) is too intrusive for the 95 % who never use it; automatic MIME-detection (C) hides the capability |
| 5 | **Fail-flow:** Hybrid pre-flight gate + post-send error (Option Z) | Cheap local pre-flight (is vLLM the active backend?) prevents wasted uploads; runtime breaker state checked on send for DEGRADED. Videos never silent-fallback to Ollama |
| 6 | **Cleanup policy:** Session-lifetime + 24 h hard cap (Option Y) | Follow-up questions about the same video work during the session; nothing accumulates forever |

---

## Architecture

Video input rides on the existing `VLLMBackend` from PR #137 — no new backend, no architectural shift. Three new modules:

- **`MediaUploadServer`** (`src/cognithor/channels/media_server.py`) — minimal FastAPI app with a static-mount on `/media/<uuid>.ext`, running on its own localhost port (not the main Cognithor API port). vLLM inside the Docker container fetches uploaded videos via `http://host.docker.internal:<media-port>/media/<uuid>.mp4`.
- **`VideoSamplingResolver`** (`src/cognithor/core/video_sampling.py`) — pure function wrapping `ffprobe` for duration detection, with a bucket table that maps duration → `{"fps": N}` or `{"num_frames": N}`. Graceful fallback to `{"num_frames": 32}` on any probe failure.
- **`VideoCleanupWorker`** (`src/cognithor/gateway/video_cleanup.py`) — async task in the Gateway that tracks per-session uploads, deletes on session close, runs a GC sweep on app start, and enforces a 5 GB quota via LRU eviction. 24 h hard TTL as an ultimate safety net.

Existing code changed:

- `VLLMBackend.chat()` — new `videos: list[str]` kwarg alongside the existing `images`. A sibling helper `_attach_videos_to_last_user()` produces OpenAI `video_url` content items instead of `image_url`.
- `VLLMOrchestrator.start_container()` — `docker run` command gains `--media-io-kwargs '{"video": {"num_frames": -1}}'` so per-request sampling via `extra_body.mm_processor_kwargs` actually takes effect. Also adds `--add-host host.docker.internal:host-gateway` for the Docker-in-Linux case.
- `WorkingMemory` — new `video_attachments: list[str]` field. `Planner.formulate_response()` routes to `config.vision_model_detail` when **either** `image_attachments` or `video_attachments` is non-empty.
- Gateway — at the start of each chat turn, extracts video-extension attachments from the incoming message into `WorkingMemory.video_attachments`, and registers them with the `VideoCleanupWorker` under the current `session_id`.
- Flutter `chat_input.dart` — Paperclip becomes a `PopupMenuButton` with entries for Image / Video / File / URL.

Video requests never fall back to Ollama — if vLLM is DEGRADED, the `chat()` path raises `VLLMNotReadyError` and the Flutter Gateway renders a red error bubble. This matches the existing image-request fail-flow from PR #137.

---

## Components

### Media Layer

**`src/cognithor/channels/media_server.py` — ~120 LOC, new**

```python
class MediaUploadServer:
    """Serves uploaded media to the vLLM Docker container over localhost.

    Separate FastAPI app on its own port so the main Cognithor API retains
    its auth/CORS policy, while vLLM can fetch without auth.
    """
    def __init__(self, config: CognithorConfig) -> None: ...
    async def start(self) -> int: ...       # returns bound port
    async def stop(self) -> None: ...
    def save_upload(self, data: bytes, ext: str) -> str:
        """Store `data` in `~/.cognithor/media/vllm-uploads/<uuid>.<ext>`,
        return the uuid. Raises if the 500 MB per-file cap is exceeded."""
    def public_url(self, uuid: str) -> str:
        """Return `http://host.docker.internal:<port>/media/<uuid>.<ext>`"""
    def delete(self, uuid: str) -> None: ...
```

- Binds to `127.0.0.1:0` (ephemeral port). The orchestrator receives the port at container-start time and includes it in the `docker run` command as `--env COGNITHOR_MEDIA_URL=http://host.docker.internal:<port>`.
- `save_upload` checks the 500 MB hard cap AND the 5 GB quota. Over quota → LRU-evict the oldest file until space is free, log the eviction.
- Allowed extensions: `.mp4`, `.webm`, `.mov`, `.mkv`, `.avi`. Anything else raises `LLMBadRequestError`.
- Authentication: **none**. The server only binds on `127.0.0.1`, so only processes on the host machine can reach it — and the only intended process is the Cognithor-managed Docker container on the same machine. Documented explicitly so security reviewers don't flag it.

### Video Sampling

**`src/cognithor/core/video_sampling.py` — ~80 LOC, new**

```python
@dataclass(frozen=True)
class VideoSampling:
    """Resolved per-video sampling spec, ready to drop into `extra_body.mm_processor_kwargs.video`."""
    fps: float | None = None
    num_frames: int | None = None
    duration_sec: float | None = None  # for logging/UI, not sent to vLLM

    def as_mm_kwargs(self) -> dict:
        """Returns the payload vLLM expects, e.g. {"fps": 2.0} or {"num_frames": 32}."""


def resolve_sampling(
    source: str,  # local path OR http(s) URL
    *,
    ffprobe_path: str = "ffprobe",
    timeout_seconds: int = 5,
    override: Literal["adaptive","fixed_32","fixed_64","fps_1"] = "adaptive",
) -> VideoSampling:
    """Run ffprobe for duration, apply bucket rules, return a VideoSampling."""
```

**Bucket rules (for `override="adaptive"`):**

| Duration | Sampling | Max frames | Approx. tokens |
|----------|----------|------------|----------------|
| < 10 s | `fps=3` | ~30 | ~9 K |
| 10 s – 30 s | `fps=2` | ~60 | ~18 K |
| 30 s – 2 min | `fps=1` | up to 120 | ~36 K |
| 2 min – 5 min | `num_frames=64` | 64 fix | ~19 K |
| 5 min – 15 min | `num_frames=32` | 32 fix | ~10 K |
| > 15 min | `num_frames=32` + UI banner recommending splitting | 32 fix | ~10 K |

For `override="fixed_32"` / `"fixed_64"` / `"fps_1"` → skip ffprobe, return constant.

**Fallback chain:**
1. `ffprobe` not found in `$PATH` (and not bundled) → `VideoSampling(num_frames=32)`
2. `ffprobe` timeout (5 s) → `VideoSampling(num_frames=32)`, log `video_duration_detection_timeout`
3. `ffprobe` succeeds but returns negative / > 86400 / non-parseable duration → `VideoSampling(num_frames=32)`

### Video Cleanup

**`src/cognithor/gateway/video_cleanup.py` — ~150 LOC, new**

State in an in-memory dict + SQLite mirror at `~/.cognithor/db/video_uploads.db` so we recover on crash:

```python
@dataclass
class VideoUploadRecord:
    uuid: str
    filename: str
    session_id: str
    uploaded_at: datetime
    bytes: int


class VideoCleanupWorker:
    async def start(self) -> None:
        """Run GC on app-start, start the 60-second periodic 24h-TTL sweep."""
    async def stop(self) -> None: ...

    async def register_upload(self, uuid: str, filename: str, session_id: str, bytes_: int) -> None: ...
    async def on_session_close(self, session_id: str) -> None:
        """Delete all uploads linked to this session."""
    async def on_app_start_gc(self) -> None:
        """Scan the uploads dir, delete files not in the SQLite registry
        (crashed-mid-upload recovery), and delete any file older than 24h."""
    async def periodic_sweep(self) -> None:
        """Hard TTL enforcement: delete files older than 24h regardless of session."""
```

Quota enforcement is **not** in the cleanup worker — it lives in `MediaUploadServer.save_upload` (LRU-evict when adding a new file would exceed 5 GB).

### Backend Layer — `VLLMBackend.chat()` Extension

Add `videos: list[str] | None = None` parameter. Implementation mirrors `_attach_images_to_last_user` from PR #137:

```python
def _attach_videos_to_last_user(
    messages: list[dict[str, Any]],
    videos: list[dict[str, str]],  # [{"url": "...", "sampling": {"fps": 2}}]
) -> tuple[list[dict[str, Any]], list[dict]]:
    """Returns (new_messages, extra_body_mm_kwargs) — both non-empty only when videos present.

    Messages get {"type":"video_url","video_url":{"url":"..."}} content items.
    extra_body_mm_kwargs is the per-request sampling payload for vLLM.
    """
```

`VLLMBackend.chat()` callers pass videos as `list[dict]` with pre-resolved sampling (Gateway resolves via `VideoSamplingResolver` before the call). Why pre-resolved? Separation — the backend shouldn't know about `ffprobe`, it just formats payloads.

### Config Layer

Additions to `VLLMConfig`:

```python
class VLLMConfig(BaseModel):
    # ... existing fields ...
    video_sampling_mode: Literal["adaptive", "fixed_32", "fixed_64", "fps_1"] = "adaptive"
    video_ffprobe_path: str = "ffprobe"  # override to absolute path on Windows
    video_ffprobe_timeout_seconds: int = Field(default=5, ge=1, le=30)
    video_max_upload_mb: int = Field(default=500, ge=1, le=5000)
    video_quota_gb: int = Field(default=5, ge=1, le=100)
    video_upload_ttl_hours: int = Field(default=24, ge=1, le=168)
```

### Flutter Layer

- `flutter_app/lib/widgets/chat_input.dart` — `IconButton` for paperclip becomes `PopupMenuButton<String>` with entries: `Bild hochladen / Video hochladen / Datei hochladen / URL einfügen`. The "Video" entry is `enabled: activeBackend == 'vllm'`, tooltip explains the gating when disabled.
- `flutter_app/lib/widgets/chat_bubble.dart` — new branch for `metadata['kind'] == 'video'`: renders a 96×54 thumbnail (first frame extracted by ffmpeg on upload, stored as sidecar `<uuid>.jpg`), filename, `duration + sampling-mode`.
- `flutter_app/lib/providers/chat_provider.dart` — `sendVideo(path)` uploads bytes to the new `/api/media/upload` endpoint, receives back `{uuid, url, duration_sec, sampling}`, adds to message metadata, sends chat request.
- Banner widget at top of `_ModelCard`-style column when the latest video is > 15 min: "Video 32 min — nur 32 Frames werden gesampled. Zerlege in 5-Min-Clips für mehr Detail."

### Dependency: ffmpeg / ffprobe

- **Windows**: bundle ffmpeg + ffprobe in the installer under `%LOCALAPPDATA%\Cognithor\ffmpeg\`. **Use an LGPL-build** (BtbN "ffmpeg-master-latest-win64-lgpl" or Gyan's LGPL variant) — a GPL build would contaminate Cognithor's Apache-2.0 license. Adds ~80 MB to the Windows installer (acceptable relative to the existing 1.5 GB). CI builds the installer with a verification step that greps the included ffmpeg binary metadata for "LGPL" and fails if "GPL" is present.
- **Linux**: expect `ffmpeg` in `$PATH`. Document `apt install ffmpeg` in the user guide. If absent, `VideoSamplingResolver` falls back to `num_frames=32` — functional but sub-optimal.
- **macOS**: same as Linux. `brew install ffmpeg`.

### vLLM Container Launch Flag

`VLLMOrchestrator.start_container()` adds two flags:

```bash
docker run -d \
    --gpus all \
    --add-host host.docker.internal:host-gateway \
    -v cognithor-hf-cache:/root/.cache/huggingface \
    -e HF_TOKEN=$token \
    -p $port:8000 \
    --label cognithor.managed=true \
    $image \
    --model $model \
    --media-io-kwargs '{"video": {"num_frames": -1}}'
```

- `--add-host host.docker.internal:host-gateway` — makes the Docker container able to reach the host's MediaUploadServer port via `http://host.docker.internal:$media_port/...`. On Docker Desktop Windows/macOS it's already provided, but on Linux Docker CE it isn't — this flag makes behavior uniform.
- `--media-io-kwargs '{"video": {"num_frames": -1}}'` — tells vLLM "use no server-side default for video sampling; let each request specify via `extra_body.mm_processor_kwargs.video`". Without this, vLLM falls back to model-default sampling which can't be overridden per request.

---

## Data Flows

### Flow A — Local Video Upload and Send

1. User clicks paperclip → popup menu → "Video hochladen". Popup is only enabled if `provider.activeBackend == 'vllm'` (pre-flight gate, Decision 5).
2. OS file picker opens filtered to `.mp4, .webm, .mov, .mkv, .avi`. Client-side: `file_picker` package.
3. Flutter sends a `POST /api/media/upload` (multipart) to Cognithor. On a separate Cognithor endpoint (not the MediaUploadServer itself — users never hit the media server directly).
4. Cognithor backend `/api/media/upload` handler:
   - Writes bytes to `MediaUploadServer.save_upload(...)` → returns `uuid`
   - Runs `ffmpeg` to extract first frame as `<uuid>.jpg` sidecar (sync, ~100 ms)
   - Runs `VideoSamplingResolver.resolve_sampling(<path>)` → `VideoSampling(fps=1.0, duration_sec=93.5)` (or similar)
   - Returns `{"uuid": "...", "url": "http://host.docker.internal:<p>/media/<uuid>.mp4", "duration_sec": 93.5, "sampling": {"fps": 1.0}, "thumb_url": "/api/media/thumb/<uuid>.jpg"}`
5. Flutter adds a message-metadata entry: `{"kind": "video", "uuid": "...", "filename": "drone.mp4", "duration_sec": 93.5, "sampling": {"fps": 1.0}, "thumb_url": "..."}`. Renders the video bubble preview (thumbnail + meta).
6. User types prompt, hits send. `chat_provider.sendMessage` includes the video metadata in the WebSocket message.
7. Gateway pulls video attachment(s) out, stuffs them into `WorkingMemory.video_attachments` as `[{"url": "...", "sampling": {"fps": 1.0}}]`. Registers the upload with `VideoCleanupWorker` under the current `session_id`.
8. Planner sees non-empty `video_attachments` → selects `config.vision_model_detail` → calls `unified_llm.chat(..., videos=working_memory.video_attachments)`.
9. `VLLMBackend.chat()` wraps with circuit breaker, `_attach_videos_to_last_user` builds the OpenAI payload:
   ```json
   {
     "model": "Qwen/Qwen3.6-27B-FP8",
     "messages": [
       {"role": "system", "content": "..."},
       {"role": "user", "content": [
         {"type": "video_url", "video_url": {"url": "http://host.docker.internal:4711/media/abc.mp4"}},
         {"type": "text", "text": "Was siehst du in diesem Video?"}
       ]}
     ],
     "extra_body": {
       "mm_processor_kwargs": {"video": {"fps": 1.0}}
     }
   }
   ```
10. vLLM inside the container `GET`s `http://host.docker.internal:4711/media/abc.mp4`, which resolves to the Cognithor host's MediaUploadServer → streams the file → vLLM samples per `fps=1`, feeds frames into Qwen3.6-27B's vision encoder.
11. vLLM responds via HTTP stream → Gateway → Flutter renders tokens as they arrive.

### Flow B — URL Paste

1. User pastes `https://example.com/clip.mp4` as plain text in the chat input.
2. On send, Flutter's `chat_provider` detects the URL via regex (allow-list of video extensions), treats it as a video reference (no upload needed).
3. Cognithor backend receives the chat request with `working_memory.video_attachments = [{"url": "https://example.com/clip.mp4", "sampling": null}]`.
4. `VideoSamplingResolver.resolve_sampling("https://...")` — `ffprobe` accepts HTTP URLs directly — returns the adaptive bucket sampling.
5. From step 8 onwards, identical to Flow A. The URL is just passed through; vLLM fetches from the remote origin instead of `host.docker.internal`.

### Flow C — Fail Flow (vLLM DEGRADED Mid-Session)

1. User has attached a video and clicks send. Pre-flight passed (vLLM was active when Paperclip was opened).
2. `VLLMBackend.chat()` inside `CircuitBreaker.call(...)` — breaker may be `CLOSED`, `OPEN`, or `HALF_OPEN`.
3. If `OPEN` (or raises `VLLMNotReadyError` on actual send): `UnifiedLLMClient` catches, inspects the request kind.
4. Because `video_attachments` is non-empty, **no silent fallback** to Ollama. The error propagates as a red bubble in chat:
   ```
   ⚠ vLLM offline — Video kann nicht verarbeitet werden.
   Versuch's in ~X s erneut oder starte vLLM neu unter Settings → LLM Backends.
   ```
5. The user can retry. After `recovery_timeout` (60 s), the next send probes vLLM; success → back to normal.

### Flow D — Session Close / Cleanup

1. User closes the chat tab, or closes Cognithor entirely, or the session times out (default 24 h).
2. Gateway calls `video_cleanup_worker.on_session_close(session_id)`.
3. Worker looks up all `VideoUploadRecord` rows for that `session_id` in SQLite, deletes the files (and sidecar thumbnails), deletes the rows.
4. Separate periodic sweep (60 s interval) enforces the hard 24 h TTL regardless of session state.
5. App start: `on_app_start_gc` scans `~/.cognithor/media/vllm-uploads/`, deletes orphan files (files-without-registry-row, which means Cognithor crashed mid-upload). Then runs the TTL sweep once.

---

## Error Handling

### Error Hierarchy Additions

- `MediaUploadError(LLMBackendError)` — base for upload issues.
  - `MediaUploadTooLargeError(MediaUploadError)` — over `video_max_upload_mb`.
  - `MediaUploadUnsupportedFormatError(MediaUploadError)` — extension not in allow-list.
  - `MediaUploadQuotaExceededError(MediaUploadError)` — would exceed `video_quota_gb` even after LRU eviction (never happens unless the single upload itself is larger than the quota).

### Setup-Time Errors

- `MediaUploadServer.start()` port bind fails → logged, server disabled, video uploads return `503 Service Unavailable`. vLLM still works for images.
- `ffprobe` missing at resolver call time → fallback to `num_frames=32`, log once per Cognithor session.
- `ffmpeg` missing at upload thumbnail generation → skip thumbnail, bubble shows a generic 🎬 icon instead. Not a fatal error.

### Runtime Errors

- vLLM returns HTTP 400 "context length exceeded" because a video exploded the token budget (e.g., custom model with different token-per-frame ratio than we expected) → propagates as `LLMBadRequestError` → red bubble with recovery hint: "Try a shorter video clip or set `vllm.video_sampling_mode: fixed_32` in config."
- `docker pull` during first-time `start_container` fetches an image without `host.docker.internal` support → `add-host` flag kicks in, vLLM can reach media server.
- URL paste but the remote server returns 404 / 5xx when vLLM tries to fetch → vLLM raises its own error → we pass through as `VLLMNotReadyError` with a hint about checking the URL.

### Circuit Breaker (reuses existing `cognithor.utils.circuit_breaker.CircuitBreaker`)

No changes to the breaker itself. `MediaUploadError` subclasses are added to `excluded_exceptions` on the vLLM breaker (upload errors are our problem, not vLLM's fault), alongside `LLMBadRequestError`.

### Privacy / Security

- `MediaUploadServer` binds `127.0.0.1` only. Never exposed on a non-loopback interface. Documented explicitly.
- Sidecar thumbnails are deleted alongside the video on cleanup.
- Uploaded files live under `~/.cognithor/media/vllm-uploads/` with 600 permissions (user-only read).

---

## Testing Strategy

### Unit Layer (GitHub Actions, free runners)

- **`tests/test_core/test_video_sampling.py`** — `VideoSamplingResolver` against a mocked `subprocess.run` for ffprobe
  - Real ffprobe JSON output → correct bucket
  - ffprobe missing → fallback to `num_frames=32`
  - ffprobe timeout → fallback
  - ffprobe returns negative / absurd duration → fallback
  - `override="fixed_32"` skips ffprobe entirely
  - All 6 bucket boundaries (< 10 s, 10–30 s, 30 s – 2 min, 2–5 min, 5–15 min, > 15 min) have a dedicated test
- **`tests/test_core/test_vllm_backend_videos.py`** — `VLLMBackend.chat(videos=...)` against `pytest-httpx`
  - Single video → correct `video_url` content item + `extra_body.mm_processor_kwargs.video`
  - Video + image mixed → both content items present, video's `extra_body` dominates
  - Video only, no text → synthetic text part added or prompt stays as-is (verify which vLLM accepts)
- **`tests/test_channels/test_media_server.py`** — `MediaUploadServer` against a `TestClient`
  - Upload within size cap → success, file on disk
  - Upload over 500 MB → 413 Payload Too Large
  - Upload unsupported extension → 400
  - Quota exceeded → oldest file LRU-evicted, log message, new file saved
  - `public_url()` returns the expected `host.docker.internal` URL
- **`tests/test_gateway/test_video_cleanup.py`** — worker
  - `register_upload` → row appears in SQLite + file exists
  - `on_session_close` deletes all session files
  - `on_app_start_gc` removes orphans (file on disk, no DB row)
  - 24 h hard TTL fires even if session is still "active"

### Integration Layer

- **`tests/test_integration/test_vllm_video_fake_server.py`** — extends the fake vLLM server from PR #137 to return a stubbed video response. Verifies that `VLLMBackend.chat(videos=[...])` produces a wire-shape that the fake server can parse and respond to.

### Flutter Layer

- **`test/widgets/chat_input_video_menu_test.dart`** — paperclip opens popup menu, "Video hochladen" disabled when `activeBackend != 'vllm'`.
- **`test/widgets/chat_bubble_video_test.dart`** — video-kind metadata renders thumbnail + filename + duration.
- Manual-only: actual file upload dialog flow (integration-tests via `flutter_driver` are out of scope).

### Cross-Repo Guard

- **`tests/test_ffmpeg_bundled.py`** — at CI build time (Windows installer only), verify the bundled `ffmpeg.exe` and `ffprobe.exe` report `LGPL` in their `-version` output. Fail the build if `GPL` appears. Prevents a copyleft-contaminated Cognithor release.

### Manual Smoke Tests

Added to `docs/vllm-manual-test.md` (from PR #137) as a new section:

- **Upload flow**: drone_clip.mp4 (42 s) → upload → bubble shows thumbnail + `0:42 · fps=2` → "What happens at 0:30?" → Qwen responds correctly
- **URL paste**: paste `https://qianwen-res.oss-accelerate.aliyuncs.com/...mp4` → no upload step → correct response
- **Long video**: upload 32-min video → banner appears → Qwen responds to rough timeline questions
- **Fail flow**: `docker stop $(docker ps -q --filter label=cognithor.managed=true)` mid-chat → video request → red error bubble, no Ollama fallback
- **Cleanup**: close Cognithor, verify `~/.cognithor/media/vllm-uploads/` is empty

### Coverage Target

≥ 90 % on `video_sampling.py`, `media_server.py`, `video_cleanup.py`, and the video paths in `vllm_backend.py`. Flutter ~70 % analogous to existing screens.

---

## Dependencies & Prerequisites

**Python (in-repo):**
- No new pip packages. Uses existing `httpx`, `fastapi`, `pydantic`, `structlog`, stdlib `subprocess` / `asyncio` / `sqlite3` / `uuid`.

**User environment:**
- `ffmpeg` + `ffprobe` — **bundled on Windows** (LGPL build in installer), expected in `$PATH` on Linux/macOS (documented in the user guide). Graceful degradation when absent: videos still work, just with fixed `num_frames=32` sampling and no thumbnails.
- Docker Desktop + vLLM (already prerequisites from PR #137).
- A vLLM-served model with video capability. Currently confirmed: `Qwen/Qwen3.6-27B` variants, `Qwen/Qwen2.5-VL-7B-Instruct`, `Qwen/Qwen3.6-35B-A3B` variants. Models without video support return HTTP 400 on video requests — handled via `LLMBadRequestError`.

**CI:** unchanged — no GPU, no real video processing, all tests mock `ffprobe` and vLLM.

---

## Scope Boundaries

**In scope:**
- `MediaUploadServer` + cleanup worker + sampling resolver
- `VLLMBackend.chat(videos=...)` extension + per-request `extra_body.mm_processor_kwargs.video`
- Flutter paperclip popup-menu + video bubble + URL detection on paste
- `docker run` flag additions (`--media-io-kwargs`, `--add-host host.docker.internal:host-gateway`)
- Session-lifetime + 24 h cleanup
- Bundled LGPL ffmpeg on Windows installer
- User-facing documentation in `docs/vllm-user-guide.md` (video section) and `docs/vllm-manual-test.md` (video smoke tests)

**Out of scope:**
- YouTube URL support (needs `yt-dlp`, separate auth/cookie handling, rate-limit concerns).
- Video generation or editing.
- Audio-only tracks (Qwen3.6-27B is vision-centric; audio is not parsed).
- Per-session quota (5 GB is global across all sessions).
- WebM VP9 and AV1 specifically — should work because they're in LGPL ffmpeg, but not explicitly listed in manual test matrix.
- Streaming video input (live feed): vLLM accepts only complete-file URLs, not rtmp/hls/webrtc streams.
- Multiple videos per single chat turn: technically supported by the spec (`videos: list[str]`), but manual-test matrix covers single-video cases only in v1.

---

## Estimate

**~1.5 calendar weeks (7–8 working days), single engineer.**

- `VideoSamplingResolver` + unit tests: 1 day
- `MediaUploadServer` + unit tests + integration wiring: 1 day
- `VideoCleanupWorker` + unit tests + session hooks: 1 day
- `VLLMBackend.chat(videos=...)` + `_attach_videos_to_last_user` + integration test against the fake server: 1 day
- Config extension (`VLLMConfig` additions) + `VLLMOrchestrator` `docker run` flag changes: 0.5 day
- Flutter paperclip popup-menu + video bubble + URL-paste detection + widget tests: 1.5 days
- Windows installer ffmpeg bundling + CI verification step: 0.5 day
- Docs (user-guide section + manual-test matrix entries) + CHANGELOG: 0.5 day
- Manual smoke test on real NVIDIA hardware + fixes: 0.5 day
- Buffer / polish / PR cycle / spec-reviewer loops: 0.5 day

Total ≈ 7.5 days = **1.5 weeks** calendar, assuming PR #137's vLLM backend lands cleanly and no vLLM-side surprises.

---

## Open Questions Deferred to Plan

- **`extra_body.mm_processor_kwargs.video` exact shape**: I extrapolated this from the Qwen3.5 vLLM recipe. The first implementation task must run against the fake server with known-good shapes (captured from vLLM upstream docs at implementation time) and adjust if the nesting differs. Plan includes a spike task to verify on day 1.
- **ffmpeg LGPL-build source**: will pick between BtbN's and Gyan's LGPL builds based on which has smaller size + broader codec support at implementation time.
- **Session-ID propagation into `MediaUploadServer`**: the media server itself shouldn't know about sessions (single responsibility), so the upload endpoint in `channels/api.py` is where `session_id` is captured from the WebSocket context and passed to `VideoCleanupWorker.register_upload`. The exact wiring is a plan-level detail.
