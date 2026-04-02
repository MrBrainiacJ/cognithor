## v0.70.0 -- Intelligent Memory Preprocessing Pipeline

### Das Problem

Cognithor's Identity Memory (sein kognitives Gedaechtnis) enthielt 3172 Eintraege, von denen:
- **76% bei exakt 1000 Zeichen abgeschnitten** waren (mitten im Satz)
- **15% roher PDF-Muell** waren (Binaer-Streams, `/Rect`, `endobj`)
- **~17% Duplikate** waren (gleiche ersten 80 Zeichen)
- **100% hardcoded `confidence=0.5`** und `memory_type=semantic` hatten
- **0% sinnvolle Tags** oder Quellen-Differenzierung hatten

**Ursache:** `MemoryManager._sync_to_identity()` hat rohe Textfragmente mit `content[:1000]` abgeschnitten und ohne jede Verarbeitung als "Memory" gespeichert.

### Die Loesung: Intelligente Preprocessing-Pipeline

Statt roher Truncation verarbeitet der KnowledgeBuilder jetzt jedes Dokument intelligent bevor es in die Identity Memory gelangt:

```
Web-Fetch -> Quality Gate -> LLM-Zusammenfassung -> Typ-Klassifizierung -> Confidence-Scoring -> Dedup -> Identity Store
```

#### 1. Content Quality Gate (bereits vorhanden, jetzt durchgehend verdrahtet)
- Lehnt PDF-Artefakte ab (>30% Garbage-Zeilen)
- Lehnt zu kurze Texte ab (<200 Zeichen, <100 fuer ATL-Synthesen)

#### 2. LLM-Zusammenfassung statt Truncation
- Ein LLM-Call pro Dokument erzeugt eine praegnante Zusammenfassung (3-8 Saetze)
- Prompt fragt nach: `summary`, `memory_type`, `tags`, `is_useful`
- `is_useful=false` -> Memory wird uebersprungen (irrelevanter Content)
- 4-stufiger JSON-Parsing-Fallback: `json.loads` -> Markdown-Block -> Regex -> Fallback-Defaults

#### 3. Source-basierte Confidence (nicht LLM-geraten)
- `.gov.de`, `.bund.de`, `europa.eu`, `bafin.de` -> **0.9** (offizielle Quellen)
- `wikipedia.org`, `arxiv.org`, `heise.de` -> **0.7** (Fachquellen)
- `owasp.org` -> **0.8** (Security-Standard)
- Unbekannte Domains -> **0.5** (neutral)
- Blog, Medium, Reddit, Forum -> **0.3** (niedrig)

#### 4. Memory-Type-Klassifizierung
- `semantic` = Fakten, Wissen, Definitionen
- `procedural` = Anleitungen, Prozesse, How-To
- `episodic` = Ereignisse, Nachrichten, zeitgebunden

#### 5. Dedup vor Insert
- SHA-256 Hash pro Zusammenfassung
- In-Memory-Cache pro KnowledgeBuilder-Instanz verhindert Session-Duplikate
- Cross-Session-Dedup weiterhin durch ConsolidationPipeline

#### 6. ATL-Synthese-Optimierung
- `already_summarized=True` Flag fuer bereits LLM-verarbeitete ATL-Inhalte
- Kein doppelter LLM-Call -- Synthese geht direkt in die Identity
- Synthese-Limit von 1000 auf 3000 Zeichen erhoeht

### Identity Memory Reset

Die 3214 alten Muell-Memories wurden entfernt. Nur die 7 Genesis-Memories (absolute Kern-Identitaet) blieben erhalten. Cognithor baut sein Wissen jetzt automatisch mit der neuen Pipeline neu auf.

**Reset-Script:** `scripts/reset_identity_memories.py` (Dry-Run als Default, `--execute` fuer echten Reset)

### Kritische Bugfixes (seit v0.69.0)

- **CORE.md 24 GB Wachstum**: `_sync_core_inventory()` umging die Verschluesselung und haengte bei jedem Start Plaintext an den verschluesselten Blob an. Behoben durch Routing ueber CoreMemory API + 1 MB Guard.
- **8-Minuten Antwortverzoegerung**: `notify_activity()` wurde am Ende statt am Anfang von `handle_message()` aufgerufen -> Evolution blockierte die GPU. Behoben mit Early Notify + Coding-Classification-Skip + Background-Reflection.
- **Windows ProactorEventLoop Buffer-Crash**: `BaseHTTPMiddleware` pufferte komplette Responses -> `WSASend` 64KB Limit ueberschritten. Behoben durch pure ASGI Middleware.
- **ATL "Initialisierung"-Schleife**: Prompt hatte keine Zyklus-Kontinuitaet. Behoben mit Cycle-Number + mehr Journal-Eintraegen.
- **ATL Timeout bei search_and_read**: Leere Query-Parameter verursachten TypeError. Behoben mit Default-Wert + Early Validation.
- **ConnectionResetError-Noise**: Windows ProactorEventLoop Rauschen unterdrueckt mit Custom Exception Handler.

### Geaenderte Dateien

| Datei | Aenderung |
|---|---|
| `src/jarvis/evolution/knowledge_builder.py` | `_summarize_for_identity()`, `_score_source_confidence()`, `_parse_llm_json()`, `memory_manager` Param, Dedup |
| `src/jarvis/memory/manager.py` | `sync_document_to_identity()` API, `content[:1000]` Truncation entfernt |
| `src/jarvis/identity/adapter.py` | `tags` Parameter fuer `store_from_cognithor()` |
| `src/jarvis/evolution/loop.py` | `synthesis[:3000]`, `memory_manager` Verdrahtung, `already_summarized` Flag |
| `src/jarvis/evolution/deep_learner.py` | `memory_manager` an KnowledgeBuilder durchgereicht |
| `src/jarvis/memory/core_memory.py` | 1 MB Wachstums-Guard |
| `src/jarvis/gateway/gateway.py` | Early `notify_activity()`, Coding-Fast-Path, Background-Reflection |
| `src/jarvis/__main__.py` | Pure ASGI Middleware statt BaseHTTPMiddleware |
| `scripts/reset_identity_memories.py` | Einmaliges Reset-Script |

### Ergebnis

Vorher: **3172 Fragmente** -- 76% abgeschnitten, 15% PDF-Muell, alles `confidence=0.5`
Nachher: Nach 1 ATL-Zyklus bereits **9 hochwertige Memories** mit korrekter Klassifizierung, differenzierter Confidence, und thematischen Tags.

### Tests

2598 Tests bestanden. 123 neue Tests fuer die Memory Preprocessing Pipeline.
