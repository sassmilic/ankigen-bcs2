"""Configuration and runtime constants."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Model Configuration
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4-turbo")

# Pipeline Configuration
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))
MAX_PARALLEL_REQUESTS = int(os.getenv("MAX_PARALLEL_REQUESTS", "5"))

# Image Configuration
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "gpt-image-1")  # "gpt-image-1" or "dall-e-3"
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1792x1024")  # "1792x1024" (wide canvas), "1024x1024", "1024x1792"
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))  # Image generation temperature (0.0-1.0)

# Directory Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "tmp" / "images"
OUTPUT_DIR = BASE_DIR / "output"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# File paths
INPUT_WORDS_FILE = DATA_DIR / "input_words.txt"
HISTORY_DB = DATA_DIR / "history.sqlite"
OUTPUT_CSV = OUTPUT_DIR / "anki_cards.csv"
COPY_SCRIPT = OUTPUT_DIR / "COPY_ME_TO_COLLECTION_MEDIA.sh"

# Testing Configuration
LIVE_TESTING = os.getenv("ANKI_VOCAB_LIVE", "0") == "1" 