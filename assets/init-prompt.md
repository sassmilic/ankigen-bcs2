## 0 · Goal

Develop a Python project that takes a plain-text list of Bosnian-Croatian-Serbian (BCS) words and produces **three Anki card types**:

1. **Definition cards** – cloze deletion on the target word.
2. **Example-sentence cards** – cloze deletion on the target word.
3. **Image ↔ target-word cards** – bidirectional Basic pair.

Leverage the OpenAI API for text and image generation and fetch supplemental images from Pexels.

---

## 1 · Proposed Directory Structure

```
anki_vocab/
├── README.md
├── pyproject.toml          # poetry or hatch; default python = "^3.12"
├── .gitignore              # ignores tmp/images/**
├── .env.example            # OPENAI_API_KEY=
├── config.py               # runtime constants
├── prompts.py              # all LLM prompt templates
├── models.py               # pydantic WordEntry, StageStatus
├── pipeline.py             # DAG orchestration (asyncio)
├── openai_client.py        # retry/back-off wrapper
├── utils.py                # file I/O, CSV helpers
├── data/
│   ├── input_words.txt
│   └── history.sqlite      # processed-words ledger
└── tmp/
    └── images/             # generated / fetched images (🗄 .gitignored)
```

---

## 2 · Data Model (`models.py`)

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class WordEntry(BaseModel):
    original: str
    canonical_form: Optional[str] = None
    part_of_speech: Optional[str] = None   # imenica, glagol, …
    word_type: Optional[str] = None        # SIMPLE | COMPLEX
    translation: Optional[str] = None
    definition: Optional[str] = None
    example_sentences: Optional[List[str]] = None
    image_prompt: Optional[str] = None
    image_files: Optional[List[str]] = None

class StageStatus(BaseModel):
    metadata: bool = False
    definition: bool = False
    examples: bool = False
    image_prompt: bool = False
    image_generation: bool = False
    completed_at: Optional[datetime] = None
```

_For words of type **SIMPLE**, lower-stage flags remain `False`; this is intentional and drives skip-logic._

---

## 3 · Prompts (`prompts.py`)

`prompts.py` will be supplied by me and will export these module-level constants:

```python
PROMPT_WORD_METADATA          # Stage 1
PROMPT_WORD_DEFINITION        # Stage 2
PROMPT_EXAMPLE_SENTENCES      # Stage 3
PROMPT_IMAGE_PROMPT_GENERATOR # Stage 4
```

---

## 4 · Pipeline Specification (`pipeline.py`)

| Stage               | Purpose                                | Depends on                | SIMPLE branch                                               | Concurrency           | Output field(s)     |
| ------------------- | -------------------------------------- | ------------------------- | ----------------------------------------------------------- | --------------------- | ------------------- |
| 1 Metadata          | canonical form, POS, type, translation | —                         | run                                                         | `asyncio.gather`      | `canonical_form` …  |
| 2 Definition        | concise learner definition             | 1                         | **skip**                                                    | gather                | `definition`        |
| 3 Example sentences | three vivid cloze sentences            | 1                         | **skip**                                                    | gather                | `example_sentences` |
| 4 Image prompt      | text prompt for image model            | 1 + 2                     | **skip**                                                    | gather (≤ 3 parallel) | `image_prompt`      |
| 5 Image fetch/gen   | create / fetch image files             | 4 (COMPLEX) or 1 (SIMPLE) | run →<br>• SIMPLE → Pexels fetch<br>• COMPLEX → DALL·E call | sequential / limited  | `image_files`       |

`asyncio.gather(*coros)` batches tasks (default `BATCH_SIZE = 20`) under `asyncio.Semaphore(MAX_PARALLEL_REQUESTS)`.

---

## 5 · Rate Limiting & Retry (`openai_client.py`)

```python
import openai
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=32, jitter=1),
    retry=lambda exc: isinstance(exc, openai.RateLimitError) or "502" in str(exc),
)
async def call_chat(model: str, messages: list[dict]) -> str:
    resp = await openai.ChatCompletion.acreate(
        model=model,
        messages=messages,
        timeout=60,
    )
    return resp.choices[0].message.content
```

_Token budget heuristic: `≈ 60 tokens × batch ≤ context_window − margin`._

---

## 6 · Logging (`structlog`)

```python
import structlog, time
log = structlog.get_logger()

async def run_metadata(entry: WordEntry):
    t0 = time.perf_counter()
    log.bind(word=entry.original, stage="metadata").info("start")
    # …LLM call…
    log.bind(elapsed_ms=1000 * (time.perf_counter() - t0)).info("done")
```

---

## 7 · CSV & Anki Media Output

1. Write `output/anki_cards.csv` **exactly**:

   ```
   #separator:;
   #html:true
   #notetype column:0
   type;2;3
   ```

2. Populate rows per Anki’s _Basic_ and _Cloze_ formats (see functional spec).

3. Images referenced as `<img src="uuid_canonical.jpg">`.

4. Auto-generate `COPY_ME_TO_COLLECTION_MEDIA.sh`:

   ```bash
   #!/usr/bin/env bash
   rsync -av tmp/images/ "$HOME/Anki/User 1/collection.media/"
   ```

---

## 8 · Persistency & Idempotency

```sql
CREATE TABLE IF NOT EXISTS words(
    canonical_form TEXT PRIMARY KEY,
    stage_status   JSON,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

_Skip previously processed words unless `--force`; update row after each stage._

---

## 9 · Configuration (`config.py`)

```python
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY       = os.environ["OPENAI_API_KEY"]
MODEL_NAME           = "gpt-4o-mini"
BATCH_SIZE           = 20
MAX_PARALLEL_REQUESTS = 5
TEMP_DIR             = Path("tmp") / "images"
PEXELS_API_KEY       = os.getenv("PEXELS_API_KEY")
IMAGE_PROVIDER       = "dalle"  # or "pexels"
```

Command-line overrides:

```bash
python -m anki_vocab.cli --model gpt-4o --batch 10
```

---

## 10 · Testing & Validation

### 10.1 Modes

| Mode            | Trigger                                                        | Network | Purpose                                                         |
| --------------- | -------------------------------------------------------------- | ------- | --------------------------------------------------------------- |
| **Mock-CI**     | `pytest` (no env vars)                                         | none    | Fast, deterministic checks using VCR cassettes                  |
| **Live-Prompt** | `export ANKI_VOCAB_LIVE=1` + `pytest -k live_llm --record=all` | real    | Refresh cassettes after `prompts.py` edits; manual verification |

### 10.2 Cassette Invalidation

- Hash `prompts.py` (`SHA-256`, first 8 chars).
- Cassette filenames: `fixtures/metadata_<hash>.yaml`.
- Hash mismatch + no `ANKI_VOCAB_LIVE` → skip test with instructive message.

### 10.3 Human-in-the-Loop Gate (live only)

```
=== MANUAL CHECK =====================================
canonical   : jabuka
translation : apple
image file  : tmp/images/…
Open the image; confirm it depicts an apple.
Type Y to accept, anything else to fail: _
```

`input()` captures the verdict; failure aborts the test.

### 10.4 `tests/conftest.py` Skeleton

```python
import hashlib, os, pathlib, pytest, vcr

PROMPTS_HASH = hashlib.sha256(
    pathlib.Path("prompts.py").read_bytes()
).hexdigest()[:8]

def cassette(name: str) -> str:
    return f"fixtures/{name}_{PROMPTS_HASH}.yaml"

@pytest.fixture
def my_vcr():
    return vcr.VCR(
        cassette_library_dir="tests/fixtures",
        filter_headers=[("authorization", "DUMMY")],
    )

def live_guard():
    if not os.getenv("ANKI_VOCAB_LIVE"):
        pytest.skip("Live LLM disabled (set ANKI_VOCAB_LIVE=1)")
```

### 10.5 Sample Live Test (`tests/live/test_roundtrip.py`)

```python
import pytest, asyncio
from anki_vocab.pipeline import process
from anki_vocab.models import WordEntry
from tests.conftest import my_vcr, cassette, live_guard

@pytest.mark.live_llm
def test_roundtrip_live(my_vcr):
    live_guard()
    entry = WordEntry(original="jabuka")
    with my_vcr.use_cassette(cassette("roundtrip")):
        asyncio.run(process([entry]))
    print("\n=== MANUAL CHECK =====================================")
    print("canonical :", entry.canonical_form)
    print("translation :", entry.translation)
    print("image file :", entry.image_files[0] if entry.image_files else "NONE")
    assert input("Type Y to accept, anything else to fail: ").strip().lower() == "y"
```

### 10.6 CLI Smoke Test

```python
from subprocess import run, PIPE

def test_cli_dry_run(tmp_path):
    (tmp_path / "words.txt").write_text("jabuka\n")
    r = run(["anki-vocab", "--dry-run", "-i", tmp_path / "words.txt"], stdout=PIPE)
    assert r.returncode == 0
```
