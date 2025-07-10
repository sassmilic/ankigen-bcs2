# AnkiGen BCS2

Auto-generate Anki cards for Bosnian-Croatian-Serbian (BCS) language learning using OpenAI and Pexels APIs.

> **Note**: This project was initially generated from the specification in `assets/init-prompt.md`.

## What it does

Takes a list of BCS words as input and produces an Anki import-ready CSV file[^1] containing three types of cards:

1. **Definition cards** – cloze deletion on the target word.
2. **Example-sentence cards** – cloze deletion on the target word.
3. **Image ↔ target-word cards** – bidirectional Basic pair.

## Quick Start

1. **Install dependencies**:

   ```bash
   pip install -e .
   ```

2. **Set up environment**:

   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

3. **Add words** to `data/input_words.txt` (one per line)

4. **Generate cards**:

   ```bash
   anki-vocab
   ```

5. **Import to Anki**:
   - Import `output/anki_cards.csv` into Anki
   - Run `output/COPY_ME_TO_COLLECTION_MEDIA.sh` to copy images

## Configuration

### Required Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key
- `PEXELS_API_KEY`: For fetching images from Pexels

## Word Classification

Words are automatically classified as either **SIMPLE** or **COMPLEX**:

- **SIMPLE words** are concrete, visible objects (like "jabuka" = apple, "kuća" = house) that work well with stock photos. These get basic metadata and images fetched from Pexels.

- **COMPLEX words** are abstract concepts, actions, or emotions (like "ljubav" = love, "misliti" = to think) that need more creative imagery. These get full processing including definitions, example sentences, and AI-generated images via DALL-E.

## Usage

### Basic Usage

```bash
# Process default input file
anki-vocab

# Process custom input file
anki-vocab -i path/to/words.txt

# Force reprocess all words
anki-vocab --force

# Dry run (show what would be processed)
anki-vocab --dry-run
```

### Advanced Options

```bash
# Custom model and batch settings
anki-vocab --model gpt-4o --batch-size 10 --max-parallel 3

# Adjust image generation temperature
anki-vocab --temperature 0.5

# Verbose logging
anki-vocab -v
```

## Pipeline Stages

1. **Metadata**: Extract canonical form, part of speech, word type, translation
2. **Definition**: Generate learner-friendly definitions (COMPLEX words only)
3. **Examples**: Create cloze example sentences (COMPLEX words only)
4. **Image Prompt**: Generate image prompts (COMPLEX words only)
5. **Images**: Fetch from Pexels (SIMPLE) or generate with AI (COMPLEX)

## Output Files

- `output/anki_cards.csv`: Anki-compatible CSV with all card types
- `output/COPY_ME_TO_COLLECTION_MEDIA.sh`: Script to copy images to Anki folder
- `tmp/images/`: Generated and downloaded images
- `data/history.sqlite`: Processing status database

## Development

### Testing

```bash
# Run tests
pytest

# Live testing with real API calls
ANKI_VOCAB_LIVE=1 pytest -k live_llm
```

### Project Structure

```
anki_vocab/
├── cli.py              # Command-line interface
├── config.py           # Configuration and constants
├── models.py           # Pydantic data models
├── pipeline.py         # Main processing pipeline
├── prompts.py          # LLM prompt templates
├── openai_client.py    # OpenAI API wrapper
├── pexels_client.py    # Pexels API wrapper
└── utils.py            # File I/O and utilities
```

[^1]: [Anki Import Documentation](https://docs.ankiweb.net/importing/text-files.html) - Special CSV formatting requirements
