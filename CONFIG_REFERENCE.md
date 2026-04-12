# Configuration Reference

Cognithor uses a YAML configuration file at `~/.jarvis/config.yaml`. Settings cascade in three layers:

1. **Defaults** (defined in `src/jarvis/config.py`)
2. **config.yaml** (overrides defaults)
3. **Environment variables** `COGNITHOR_*` (overrides everything)

> Legacy `JARVIS_*` environment variables are still supported for backward compatibility but `COGNITHOR_*` is preferred and takes precedence.

The configuration file is automatically created on first start.

---

## General

| Key | Type | Default | Env Var | Description |
|-----|------|---------|---------|-------------|
| `language` | string | `"de"` | `COGNITHOR_LANGUAGE` | UI language for error messages, greetings, status texts. Supports any installed i18n pack (en, de, zh, ar). |
| `owner_name` | string | `"User"` | `COGNITHOR_OWNER_NAME` | Owner name used in prompts and CORE.md personalization. |
| `operation_mode` | string | `"auto"` | `COGNITHOR_OPERATION_MODE` | Operation mode: `offline`, `online`, `hybrid`, `auto`. Auto-detects from API keys. |
| `jarvis_home` | path | `~/.jarvis` | `COGNITHOR_HOME` | Base directory for all Cognithor data. |
| `version` | string | *(from package)* | -- | Read-only. Current package version. |

---

## LLM Backend

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `llm_backend_type` | string | `"ollama"` | Backend provider. One of: `ollama`, `openai`, `anthropic`, `gemini`, `groq`, `deepseek`, `mistral`, `together`, `openrouter`, `xai`, `cerebras`, `github`, `bedrock`, `huggingface`, `moonshot`, `lmstudio`. Auto-detected from API keys if left as `ollama`. |
| `openai_api_key` | string | `""` | OpenAI API key. Also used for OpenAI-compatible providers. |
| `openai_base_url` | string | `"https://api.openai.com/v1"` | Base URL for OpenAI-compatible backend (also for Together, Groq, vLLM). |
| `anthropic_api_key` | string | `""` | Anthropic Claude API key. |
| `anthropic_max_tokens` | int | `4096` | Maximum output tokens for Claude (1--1,000,000). |
| `gemini_api_key` | string | `""` | Google Gemini API key. |
| `groq_api_key` | string | `""` | Groq API key. |
| `deepseek_api_key` | string | `""` | DeepSeek API key. |
| `mistral_api_key` | string | `""` | Mistral AI API key. |
| `together_api_key` | string | `""` | Together AI API key. |
| `openrouter_api_key` | string | `""` | OpenRouter API key. |
| `xai_api_key` | string | `""` | xAI (Grok) API key. |
| `cerebras_api_key` | string | `""` | Cerebras API key. |
| `github_api_key` | string | `""` | GitHub Models API key/token. |
| `bedrock_api_key` | string | `""` | AWS Bedrock API key (OpenAI-compatible via gateway). |
| `huggingface_api_key` | string | `""` | Hugging Face Inference API key. |
| `moonshot_api_key` | string | `""` | Moonshot/Kimi API key. |
| `lmstudio_api_key` | string | `"lm-studio"` | LM Studio API key (arbitrary value since local). |
| `lmstudio_base_url` | string | `"http://localhost:1234/v1"` | LM Studio API base URL. |
| `vision_model` | string | `"openbmb/minicpm-v4.5"` | Default vision model (fast). |
| `vision_model_detail` | string | `"qwen3-vl:32b"` | Detail vision model (highest quality). |

### Backend Auto-Detection

If `llm_backend_type` is `"ollama"` but an API key is set, the backend is auto-detected. Priority order: Anthropic > OpenAI > Gemini > Groq > DeepSeek > Mistral > Together > OpenRouter > xAI > Cerebras > GitHub > Bedrock > Hugging Face > Moonshot.

---

## Ollama

Section key: `ollama`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `base_url` | string | `"http://localhost:11434"` | Ollama server URL. Falls back to `OLLAMA_HOST` env var. |
| `timeout_seconds` | int | `120` | Request timeout (10--600). |
| `keep_alive` | string | `"30m"` | How long models stay loaded in VRAM. |

---

## Models

Section key: `models`

Each model role has the same fields: `name`, `context_window`, `vram_gb`, `strengths`, `speed`.

### Planner

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `models.planner.name` | string | `"qwen3:32b"` | Planner model (the "brain"). |
| `models.planner.context_window` | int | `32768` | Context window size (tokens). |
| `models.planner.vram_gb` | float | `20.0` | VRAM usage estimate (GB). |

### Executor

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `models.executor.name` | string | `"qwen3:8b"` | Executor model (fast tool execution). |
| `models.executor.context_window` | int | `32768` | Context window size (tokens). |
| `models.executor.vram_gb` | float | `6.0` | VRAM usage estimate (GB). |

### Coder

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `models.coder.name` | string | `"qwen3-coder:30b"` | Code specialist model. |
| `models.coder.context_window` | int | `32768` | Context window size (tokens). |
| `models.coder.vram_gb` | float | `20.0` | VRAM usage estimate (GB). |

### Coder Fast

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `models.coder_fast.name` | string | `"qwen2.5-coder:7b"` | Fast code model for real-time coding. |
| `models.coder_fast.context_window` | int | `32768` | Context window size (tokens). |
| `models.coder_fast.vram_gb` | float | `5.0` | VRAM usage estimate (GB). |

### Embedding

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `models.embedding.name` | string | `"qwen3-embedding:0.6b"` | Embedding model for semantic search. |
| `models.embedding.context_window` | int | `8192` | Context window size (tokens). |
| `models.embedding.vram_gb` | float | `0.5` | VRAM usage estimate (GB). |
| `models.embedding.embedding_dimensions` | int | `1024` | Embedding vector dimensions. |

### Provider-Specific Model Defaults

When switching backends, Ollama model names are automatically replaced with provider-appropriate models. Supported providers and their default planner models:

| Provider | Planner | Executor | Coder | Embedding |
|----------|---------|----------|-------|-----------|
| OpenAI | gpt-5.2 | gpt-5-mini | o3 | text-embedding-3-large |
| Anthropic | claude-opus-4-6 | claude-haiku-4-5 | claude-sonnet-4-6 | *(Ollama fallback)* |
| Gemini | gemini-2.5-pro | gemini-2.5-flash | gemini-2.5-pro | gemini-embedding-001 |
| Groq | llama-4-maverick-17b | llama-3.1-8b-instant | llama-3.3-70b | *(Ollama fallback)* |
| DeepSeek | deepseek-chat | deepseek-chat | deepseek-chat | *(Ollama fallback)* |
| Mistral | mistral-large-latest | mistral-small-latest | codestral-latest | mistral-embed |
| Together | Llama-4-Maverick-17B | Llama-4-Scout-17B | Llama-4-Maverick-17B | *(Ollama fallback)* |
| OpenRouter | claude-opus-4.6 | gemini-2.5-flash | claude-sonnet-4.6 | *(Ollama fallback)* |
| xAI | grok-4-1-fast-reasoning | grok-4-1-fast-non-reasoning | grok-code-fast-1 | *(Ollama fallback)* |
| Cerebras | gpt-oss-120b | llama3.1-8b | gpt-oss-120b | *(Ollama fallback)* |
| GitHub | gpt-4.1 | gpt-4.1-mini | gpt-4.1 | text-embedding-3-large |
| Bedrock | claude-opus-4-6-v1 | claude-haiku-4-5-v1 | claude-sonnet-4-6-v1 | titan-embed-text-v2 |
| Hugging Face | Llama-3.3-70B | Llama-3.1-8B | Qwen2.5-Coder-32B | *(Ollama fallback)* |
| Moonshot | kimi-k2.5 | kimi-k2-turbo-preview | kimi-k2.5 | *(Ollama fallback)* |

---

## Planner

Section key: `planner`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `max_iterations` | int | `25` | 1--50 | Maximum planning steps per request. |
| `escalation_after` | int | `3` | 1--10 | Escalate to user after N failed steps. |
| `temperature` | float | `0.7` | 0.0--2.0 | LLM temperature for planning. |
| `response_token_budget` | int | `4000` | 500--8000 | Token budget for response generation. |

---

## Gatekeeper

Section key: `gatekeeper`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `policies_dir` | string | `"policies"` | -- | Policies directory (relative to jarvis_home). |
| `default_risk_level` | string | `"yellow"` | green/yellow/orange/red | Default risk level for unknown tools. |
| `max_blocked_retries` | int | `3` | 1--10 | Max retries when gatekeeper blocks an action. |

---

## Executor

Section key: `executor`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `default_timeout_seconds` | int | `30` | 5--600 | Default timeout for tool execution. |
| `max_output_chars` | int | `10000` | 1000--100000 | Max tool output length (characters). |
| `max_retries` | int | `3` | 0--10 | Max retries on transient errors. |
| `backoff_base_delay_seconds` | float | `1.0` | 0.1--30.0 | Base delay for exponential backoff. |
| `max_parallel_tools` | int | `4` | 1--16 | Max parallel tools in DAG execution. |
| `media_analyze_image_timeout` | int | `180` | 30--600 | Image analysis timeout (seconds). |
| `media_transcribe_audio_timeout` | int | `120` | 30--600 | Audio transcription timeout (seconds). |
| `media_extract_text_timeout` | int | `120` | 30--600 | Text extraction timeout (seconds). |
| `media_tts_timeout` | int | `120` | 30--600 | Text-to-speech timeout (seconds). |
| `run_python_timeout` | int | `120` | 30--600 | Python code execution timeout (seconds). |

---

## Memory

Section key: `memory`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `chunk_size_tokens` | int | `400` | 100--2000 | Chunk size for memory indexing. |
| `chunk_overlap_tokens` | int | `80` | 0--500 | Overlap between chunks. |
| `search_top_k` | int | `6` | 1--20 | Number of memory search results. |
| `weight_vector` | float | `0.50` | 0.0--1.0 | Hybrid search weight for vector similarity. |
| `weight_bm25` | float | `0.30` | 0.0--1.0 | Hybrid search weight for BM25 (lexical). |
| `weight_graph` | float | `0.20` | 0.0--1.0 | Hybrid search weight for knowledge graph. |
| `recency_half_life_days` | int | `30` | 1--365 | Half-life for recency decay scoring. |
| `compaction_threshold` | float | `0.80` | 0.5--0.95 | Working memory compaction trigger threshold. |
| `compaction_keep_last_n` | int | `8` | 2--20 | Messages to keep after compaction. |
| `budget_core_memory` | int | `500` | 100--5000 | Token budget for CORE.md. |
| `budget_system_prompt` | int | `800` | 200--5000 | Token budget for system prompt. |
| `budget_procedures` | int | `600` | 100--5000 | Token budget for procedures. |
| `budget_injected_memories` | int | `2500` | 200--10000 | Token budget for injected memories. |
| `budget_tool_descriptions` | int | `1200` | 200--10000 | Token budget for tool descriptions. |
| `budget_response_reserve` | int | `3000` | 500--15000 | Token budget reserved for response. |
| `episodic_retention_days` | int | `365` | 1--3650 | Days to retain episodic memory logs. |
| `dynamic_weighting` | bool | `false` | -- | Enable dynamic hybrid search weighting based on query properties. |

Note: If `weight_vector + weight_bm25 + weight_graph > 1.0`, all weights are automatically normalized to sum to 1.0.

---

## Context Pipeline

Section key: `context_pipeline`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `enabled` | bool | `true` | -- | Enable pre-planner context enrichment. |
| `memory_top_k` | int | `8` | -- | Number of memory results (BM25-only, ~5-20ms). |
| `vault_top_k` | int | `5` | -- | Number of vault search results (~10-50ms). |
| `episode_days` | int | `2` | -- | Days of episodic context (today + yesterday). |
| `min_query_length` | int | `8` | -- | Minimum user message length for context search. |
| `max_context_chars` | int | `8000` | -- | Maximum character count of injected context. |
| `smalltalk_patterns` | list | *(see below)* | -- | Patterns classified as small talk (no context search). |

Default smalltalk patterns: `hallo`, `hi`, `hey`, `guten morgen`, `guten tag`, `guten abend`, `danke`, `tschüss`, `bye`, `ok`, `ja`, `nein`, `alles klar`.

---

## Web

Section key: `web`

Search backends are tried in priority order: SearXNG > Brave > Google CSE > DuckDuckGo.

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `searxng_url` | string | `""` | -- | SearXNG instance URL (e.g., `http://localhost:8888`). |
| `brave_api_key` | string | `""` | -- | Brave Search API key (2000 queries/month free). |
| `google_cse_api_key` | string | `""` | -- | Google Custom Search Engine API key. |
| `google_cse_cx` | string | `""` | -- | Google CSE engine ID (cx parameter). |
| `jina_api_key` | string | `""` | -- | Jina AI Reader API key (optional, free tier works without). |
| `duckduckgo_enabled` | bool | `true` | -- | DuckDuckGo as free fallback when no other backend configured. |
| `domain_blocklist` | list | `[]` | -- | Blocked domains (fetch refused). |
| `domain_allowlist` | list | `[]` | -- | If non-empty, only these domains are allowed (whitelist mode). |
| `max_fetch_bytes` | int | `500000` | 10K--10M | Max response size for URL fetch (bytes). |
| `max_text_chars` | int | `20000` | 1K--200K | Max characters of extracted text. |
| `fetch_timeout_seconds` | int | `15` | 5--120 | HTTP timeout for URL fetch. |
| `search_timeout_seconds` | int | `10` | 5--60 | Timeout for search engine queries. |
| `max_search_results` | int | `10` | 1--50 | Max number of search results. |
| `ddg_min_delay_seconds` | float | `2.0` | 0.5--10.0 | Minimum delay between DuckDuckGo searches. |
| `ddg_ratelimit_wait_seconds` | int | `30` | 5--120 | Wait time on DuckDuckGo rate limiting. |
| `ddg_cache_ttl_seconds` | int | `3600` | 60--86400 | Cache TTL for DuckDuckGo results. |
| `search_and_read_max_chars` | int | `5000` | 1K--50K | Max characters per page in search_and_read. |
| `http_request_max_body_bytes` | int | `1048576` | 1K--10M | Max body size for http_request tool (bytes). |
| `http_request_timeout_seconds` | int | `30` | 1--120 | Default timeout for http_request. |
| `http_request_rate_limit_seconds` | float | `1.0` | 0.0--30.0 | Min delay between http_request calls (0 = no limit). |

---

## Browser

Section key: `browser`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `max_text_length` | int | `8000` | 1K--100K | Max text length returned to LLM. |
| `max_js_length` | int | `50000` | 1K--500K | Max JavaScript script length (characters). |
| `default_timeout_ms` | int | `30000` | 5K--120K | Default browser timeout (milliseconds). |
| `default_viewport_width` | int | `1280` | 320--3840 | Default viewport width (pixels). |
| `default_viewport_height` | int | `720` | 240--2160 | Default viewport height (pixels). |

---

## Filesystem

Section key: `filesystem`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `max_tree_entries` | int | `200` | 10--10000 | Max entries in directory tree listing. |

---

## Shell

Section key: `shell`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `default_timeout_seconds` | int | `30` | 5--600 | Default timeout for shell commands. |
| `max_log_command_length` | int | `200` | 50--2000 | Max command length in logs. |
| `max_redacted_log_prefix` | int | `50` | 10--500 | Max prefix length for redacted log entries. |

---

## Media

Section key: `media`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `max_extract_length` | int | `15000` | 1K--100K | Max text length for LLM context on extraction. |
| `max_image_file_size` | int | `10485760` | 1M--100M | Max image file size for base64 encoding (bytes). |
| `max_extract_file_size` | int | `52428800` | 1M--500M | Max file size for document extraction (bytes). |
| `max_audio_file_size` | int | `104857600` | 1M--1G | Max audio file size (bytes). |
| `max_image_dimension` | int | `8192` | 256--16384 | Max image dimension (pixels). |
| `default_max_width` | int | `1024` | 64--8192 | Default max width for image resize. |
| `default_max_height` | int | `1024` | 64--8192 | Default max height for image resize. |

---

## Synthesis

Section key: `synthesis`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `max_source_chars` | int | `4000` | 500--50K | Max characters per source for LLM context. |
| `max_context_chars` | int | `25000` | 5K--200K | Max total context size for LLM. |

---

## Code

Section key: `code`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `max_code_size` | int | `1048576` | 1K--10M | Max code size (bytes). |
| `default_timeout_seconds` | int | `60` | 5--600 | Default timeout for Python execution. |

---

## Email

Section key: `email`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable/disable email tools. |
| `imap_host` | string | `""` | IMAP server hostname (e.g., `imap.gmail.com`). |
| `imap_port` | int | `993` | IMAP server port (993 for SSL). |
| `smtp_host` | string | `""` | SMTP server hostname (e.g., `smtp.gmail.com`). |
| `smtp_port` | int | `465` | SMTP server port (465 for SSL, 587 for STARTTLS). |
| `username` | string | `""` | Email username (often the email address). |
| `password_env` | string | `"JARVIS_EMAIL_PASSWORD"` | Name of environment variable containing the email password. |

---

## Calendar

Section key: `calendar`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable/disable calendar tools. |
| `ics_path` | string | `""` | Path to local ICS file (default: `~/.jarvis/calendar.ics`). |
| `caldav_url` | string | `""` | CalDAV server URL (optional). |
| `username` | string | `""` | CalDAV username. |
| `password_env` | string | `"JARVIS_CALENDAR_PASSWORD"` | Env var name for CalDAV password. |
| `timezone` | string | `""` | Timezone (e.g., `Europe/Berlin`). Empty = system timezone. |

---

## Vault

Section key: `vault`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable/disable the vault system. |
| `path` | string | `"~/.jarvis/vault"` | Vault directory path. Auto-created on first use. |
| `auto_save_research` | bool | `false` | Automatically save web research results to vault. |
| `default_folders` | dict | *(see below)* | Mapping of logical folder names to directory names. |

Default folders: `research` -> `recherchen`, `meetings` -> `meetings`, `knowledge` -> `wissen`, `projects` -> `projekte`, `daily` -> `daily`.

---

## Personality

Section key: `personality`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `warmth` | float | `0.7` | 0.0--1.0 | Warmth level. 0.0 = neutral/factual, 1.0 = very warm and empathetic. |
| `humor` | float | `0.3` | 0.0--1.0 | Humor level. 0.0 = serious, 1.0 = playful. |
| `follow_up_questions` | bool | `true` | -- | Whether to ask follow-up questions. |
| `success_celebration` | bool | `true` | -- | Positively acknowledge successful actions. |
| `greeting_enabled` | bool | `true` | -- | Use time-of-day greetings. |

---

## Identity

Section key: `identity`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `enabled` | bool | `true` | -- | Enable/disable Identity Layer (Immortal Mind Protocol). |
| `identity_id` | string | `"jarvis"` | -- | Default identity ID. |
| `checkpoint_every_n` | int | `5` | 1--50 | Consolidate every N interactions. |
| `checkpoint_interval_minutes` | int | `10` | 1--120 | Consolidate every N minutes. |
| `narrative_reflect_every_n` | int | `50` | 10--500 | Narrative self-reflection every N interactions. |
| `max_active_memories` | int | `10000` | 100--100000 | Max number of active memories. |
| `reality_check_enabled` | bool | `true` | -- | Enable hallucination protection. |
| `blockchain_enabled` | bool | `false` | -- | Enable blockchain anchoring (opt-in). |
| `blockchain_chain` | string | `"base_sepolia"` | -- | Blockchain network. |
| `arweave_enabled` | bool | `false` | -- | Enable Arweave permanent storage (opt-in). |

---

## Channels

Section key: `channels`

### Core Channels

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cli_enabled` | bool | `true` | Enable CLI REPL. |
| `webui_enabled` | bool | `false` | Enable WebUI channel. |
| `webui_port` | int | `8080` | WebUI port (1024--65535). |
| `voice_enabled` | bool | `false` | Enable voice channel. |

### Telegram

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `telegram_enabled` | bool | `false` | Enable Telegram bot. |
| `telegram_whitelist` | list | `[]` | Allowed Telegram user IDs. |
| `telegram_use_webhook` | bool | `false` | Use webhook instead of polling. |
| `telegram_webhook_url` | string | `""` | External webhook URL. |
| `telegram_webhook_port` | int | `8443` | Local webhook server port. |
| `telegram_webhook_host` | string | `"0.0.0.0"` | Local webhook bind host. |

### Slack

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slack_enabled` | bool | `false` | Enable Slack integration. |
| `slack_default_channel` | string | `""` | Default Slack channel. |

### Discord

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `discord_enabled` | bool | `false` | Enable Discord bot. |
| `discord_channel_id` | string | `""` | Discord channel ID. |

### WhatsApp

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `whatsapp_enabled` | bool | `false` | Enable WhatsApp integration. |
| `whatsapp_default_chat` | string | `""` | Default chat ID. |
| `whatsapp_phone_number_id` | string | `""` | Phone number ID from Meta. |
| `whatsapp_webhook_port` | int | `8443` | Webhook server port. |
| `whatsapp_verify_token` | string | `""` | Webhook verification token. |
| `whatsapp_allowed_numbers` | list | `[]` | Allowed phone numbers. |

### Signal

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `signal_enabled` | bool | `false` | Enable Signal integration. |
| `signal_default_user` | string | `""` | Default Signal user. |

### Matrix

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `matrix_enabled` | bool | `false` | Enable Matrix integration. |
| `matrix_homeserver` | string | `""` | Matrix homeserver URL. |
| `matrix_user_id` | string | `""` | Matrix user ID. |

### Microsoft Teams

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `teams_enabled` | bool | `false` | Enable Teams integration. |
| `teams_default_channel` | string | `""` | Default Teams channel. |

### iMessage

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `imessage_enabled` | bool | `false` | Enable iMessage (macOS only). |
| `imessage_device_id` | string | `""` | Device ID. |

### Google Chat

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `google_chat_enabled` | bool | `false` | Enable Google Chat. |
| `google_chat_credentials_path` | string | `""` | Path to service account credentials. |
| `google_chat_allowed_spaces` | list | `[]` | Allowed Google Chat spaces. |

### Mattermost

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `mattermost_enabled` | bool | `false` | Enable Mattermost. |
| `mattermost_url` | string | `""` | Mattermost server URL. |
| `mattermost_token` | string | `""` | Bot token. |
| `mattermost_channel` | string | `""` | Default channel. |

### Feishu/Lark

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `feishu_enabled` | bool | `false` | Enable Feishu/Lark. |
| `feishu_app_id` | string | `""` | App ID. |
| `feishu_app_secret` | string | `""` | App secret. |

### IRC

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `irc_enabled` | bool | `false` | Enable IRC bot. |
| `irc_server` | string | `""` | IRC server hostname. |
| `irc_port` | int | `6667` | IRC server port. |
| `irc_nick` | string | `"JarvisBot"` | IRC nickname. |
| `irc_channels` | list | `[]` | IRC channels to join. |

### Twitch

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `twitch_enabled` | bool | `false` | Enable Twitch integration. |
| `twitch_token` | string | `""` | Twitch OAuth token. |
| `twitch_channel` | string | `""` | Twitch channel name. |
| `twitch_allowed_users` | list | `[]` | Allowed Twitch usernames. |

---

## Voice

Section key: `channels.voice_config`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tts_backend` | string | `"piper"` | TTS backend: `piper`, `espeak`, `elevenlabs`. |
| `piper_voice` | string | `"de_DE-thorsten_emotional-medium"` | Piper voice (HuggingFace ID). |
| `piper_length_scale` | float | `1.0` | Speech speed (0.5--2.0). |
| `elevenlabs_api_key` | string | `""` | ElevenLabs API key. |
| `elevenlabs_voice_id` | string | `"hJAaR77ekN23CNyp0byH"` | ElevenLabs voice ID. |
| `elevenlabs_model` | string | `"eleven_multilingual_v2"` | ElevenLabs model. |
| `wake_word_enabled` | bool | `true` | Enable wake word detection. |
| `wake_word` | string | `"jarvis"` | Wake word. |
| `wake_word_backend` | string | `"browser"` | Wake word backend: `browser`, `vosk`, `porcupine`. |
| `talk_mode_enabled` | bool | `false` | Enable continuous talk mode. |
| `talk_mode_auto_listen` | bool | `false` | Auto-listen after TTS finishes. |

---

## Security

Section key: `security`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `max_iterations` | int | `25` | 1--50 | Max agent loop iterations per request. |
| `allowed_paths` | list | `["~/.jarvis/", "<tempdir>/jarvis/"]` | -- | Allowed file access paths (gatekeeper enforced). |
| `allow_project_dir` | bool | `true` | -- | Automatically add project directory to allowed_paths. |
| `blocked_commands` | list | *(destructive patterns)* | -- | Regex patterns for blocked shell commands. |
| `credential_patterns` | list | *(credential patterns)* | -- | Regex patterns for credential detection. |
| `max_sub_agent_depth` | int | `3` | 1--10 | Max recursion depth for sub-agent delegations. |
| `ssl_certfile` | string | `""` | -- | SSL certificate path (PEM). |
| `ssl_keyfile` | string | `""` | -- | SSL private key path (PEM). |
| `channel_dict_ttl_seconds` | int | `86400` | 300--604800 | TTL for channel TTLDict entries. |
| `channel_dict_max_size` | int | `10000` | 100--100000 | Max entries in channel TTLDicts. |
| `dns_cache_ttl_seconds` | int | `300` | 30--3600 | DNS cache TTL. |
| `dns_cache_max_size` | int | `1000` | 100--10000 | DNS cache max entries. |
| `circuit_breaker_failure_threshold` | int | `5` | 2--50 | Circuit breaker failure threshold. |
| `circuit_breaker_recovery_timeout` | int | `60` | 10--600 | Circuit breaker recovery timeout (seconds). |
| `shell_validate_paths` | bool | `true` | -- | Validate paths in shell commands. |

### mTLS

Section key: `security.mtls`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable mutual TLS for WebUI API. |
| `certs_dir` | string | `""` | Certificate directory (default: `~/.jarvis/certs/`). |
| `auto_generate` | bool | `true` | Auto-generate certificates on first start. |

---

## Database

Section key: `database`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `backend` | string | `"sqlite"` | -- | Database backend: `sqlite` or `postgresql`. |
| `pg_host` | string | `"localhost"` | -- | PostgreSQL host. |
| `pg_port` | int | `5432` | 1--65535 | PostgreSQL port. |
| `pg_dbname` | string | `"jarvis"` | -- | PostgreSQL database name. |
| `pg_user` | string | `"jarvis"` | -- | PostgreSQL user. |
| `pg_password` | string | `""` | -- | PostgreSQL password. |
| `pg_pool_min` | int | `2` | 1--50 | Min connection pool size. |
| `pg_pool_max` | int | `10` | 1--100 | Max connection pool size. |
| `encryption_enabled` | bool | `false` | -- | Encrypt SQLite databases with SQLCipher. |
| `encryption_backend` | string | `"keyring"` | -- | Key backend: `keyring` (OS credential store). |
| `sqlite_max_retries` | int | `5` | 0--20 | Max retries on "database is locked". |
| `sqlite_retry_base_delay` | float | `0.1` | 0.01--5.0 | Base delay for retry backoff. |

---

## Queue

Section key: `queue`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `enabled` | bool | `false` | -- | Enable durable message queue. |
| `max_size` | int | `10000` | 100--1M | Max queue size. |
| `ttl_hours` | int | `24` | 1--168 | Message TTL (hours). |
| `max_retries` | int | `3` | 0--10 | Max delivery retries. |
| `priority_boost_channels` | list | `["api", "telegram"]` | -- | Channels with automatic priority boost. |

---

## Logging

Section key: `logging`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `level` | string | `"INFO"` | Log level (DEBUG, INFO, WARNING, ERROR). |
| `json_logs` | bool | `false` | Enable JSON-formatted log output. |
| `console` | bool | `true` | Enable console log output. |

---

## Heartbeat

Section key: `heartbeat`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `enabled` | bool | `false` | -- | Enable periodic heartbeat. |
| `interval_minutes` | int | `30` | 1--1440 | Interval between heartbeats (minutes). |
| `checklist_file` | string | `"HEARTBEAT.md"` | -- | Checklist file in jarvis_home. |
| `channel` | string | `"cli"` | -- | Channel for heartbeat messages. |
| `model` | string | `"qwen3:8b"` | -- | Model for heartbeat communication. |

---

## Plugins

Section key: `plugins`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `skills_dir` | string | `"skills"` | Skills directory (relative to jarvis_home). |
| `auto_update` | bool | `false` | Auto-update installed plugins on startup. |

---

## Marketplace

Section key: `marketplace`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable Skill Marketplace. |
| `db_path` | string | `""` | Marketplace DB path (empty = `~/.jarvis/marketplace.db`). |
| `auto_update` | bool | `false` | Auto-update installed skills. |
| `require_signatures` | bool | `true` | Only install signed skills. |
| `auto_seed` | bool | `true` | Seed marketplace with built-in procedures on first start. |

---

## Community Marketplace

Section key: `community_marketplace`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `enabled` | bool | `true` | -- | Enable Community Marketplace. |
| `registry_url` | string | *(GitHub raw URL)* | -- | Community registry URL. Can point to a fork. |
| `auto_recall_check_interval` | int | `3600` | 300--86400 | Interval for automatic recall checks (seconds). |
| `min_publisher_reputation` | float | `0.0` | 0.0--100.0 | Min publisher reputation score for install. |
| `require_verified_publisher` | bool | `false` | -- | Only install from verified publishers. |
| `max_tool_calls_default` | int | `10` | 1--100 | Default max tool calls per community skill invocation. |
| `auto_sync` | bool | `true` | -- | Sync registry on startup and periodically. |

---

## Improvement Governance

Section key: `improvement`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `enabled` | bool | `true` | -- | Enable self-improvement governance. |
| `auto_domains` | list | `["prompt_tuning", "tool_parameters", "workflow_order"]` | -- | Domains where automatic improvements are allowed. |
| `hitl_domains` | list | `["memory_weights", "model_selection"]` | -- | Domains requiring human-in-the-loop approval. |
| `blocked_domains` | list | `["code_generation"]` | -- | Blocked improvement domains. |
| `cooldown_minutes` | int | `30` | 5--1440 | Cooldown between improvements. |
| `max_changes_per_hour` | int | `5` | 1--50 | Max changes per hour. |

---

## Prompt Evolution

Section key: `prompt_evolution`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `enabled` | bool | `false` | -- | Enable A/B-test-based prompt evolution (opt-in). |
| `min_sessions_per_arm` | int | `20` | 5--200 | Min sessions per test arm. |
| `significance_threshold` | float | `0.05` | 0.01--0.5 | Statistical significance threshold. |
| `evolution_interval_hours` | int | `6` | 1--168 | Interval between evolution cycles. |
| `max_concurrent_tests` | int | `1` | 1--3 | Max concurrent A/B tests. |

---

## GEPA

Section key: `gepa`

Guided Evolution through Pattern Analysis.

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `enabled` | bool | `false` | -- | Enable GEPA (opt-in). |
| `evolution_interval_hours` | int | `6` | 1--168 | Interval between evolution cycles. |
| `min_traces_for_proposal` | int | `10` | 3--100 | Min execution traces before generating proposals. |
| `max_active_optimizations` | int | `1` | 1--3 | Max active optimizations. |
| `auto_rollback_threshold` | float | `0.10` | 0.01--0.5 | Auto-rollback if performance drops by this fraction. |
| `auto_apply` | bool | `false` | -- | Automatically apply proposals without approval. |

---

## Dashboard

Section key: `dashboard`

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `enabled` | bool | `false` | -- | Enable web dashboard. |
| `port` | int | `9090` | 1024--65535 | Dashboard port. |

---

## Model Overrides

Section key: `model_overrides`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `skill_models` | dict | `{}` | Per-skill model overrides. Key = skill name (without extension), value = model name. |

---

## Cost Tracking

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `cost_tracking_enabled` | bool | `true` | -- | Enable LLM cost tracking. |
| `daily_budget_usd` | float | `0.0` | 0.0+ | Daily budget limit in USD (0 = no limit). |
| `monthly_budget_usd` | float | `0.0` | 0.0+ | Monthly budget limit in USD (0 = no limit). |

---

## Multi-Instance / Distributed Locking

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `lock_backend` | string | `"local"` | Lock backend: `local`, `file`, `redis`. |
| `redis_url` | string | `"redis://localhost:6379/0"` | Redis URL for distributed locking and queuing. |

---

## Environment Variable Override Pattern

Any config key can be overridden with a `COGNITHOR_` prefixed environment variable. Nested keys use underscores:

```bash
# Top-level
export COGNITHOR_LANGUAGE=en
export COGNITHOR_OWNER_NAME="John Doe"
export COGNITHOR_LLM_BACKEND_TYPE=openai

# API Keys
export COGNITHOR_OPENAI_API_KEY=sk-...
export COGNITHOR_ANTHROPIC_API_KEY=sk-ant-...

# Nested (use section_key format)
export COGNITHOR_OLLAMA_TIMEOUT_SECONDS=180
export COGNITHOR_PLANNER_MAX_ITERATIONS=15
```

Channel tokens are typically set in `~/.jarvis/.env`:

```bash
COGNITHOR_TELEGRAM_TOKEN=123456:ABC...
COGNITHOR_SLACK_TOKEN=xoxb-...
COGNITHOR_DISCORD_TOKEN=...
```
