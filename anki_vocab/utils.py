"""Utility functions for file I/O, CSV helpers, and database operations."""

import csv
import sqlite3
import uuid
from pathlib import Path
from typing import List, Optional
import aiohttp
import structlog

from .config import HISTORY_DB, TEMP_DIR, OUTPUT_CSV, COPY_SCRIPT
from .models import WordEntry, StageStatus

log = structlog.get_logger()


def load_words_from_file(file_path: Path) -> List[str]:
    """Load words from a text file, one word per line."""
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    
    words = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            word = line.strip()
            if word and not word.startswith('#'):
                words.append(word)
    
    log.info("Loaded words from file", count=len(words), file=str(file_path))
    return words


def init_database():
    """Initialize the SQLite database for tracking processed words."""
    db_exists = HISTORY_DB.exists()
    
    conn = sqlite3.connect(HISTORY_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words(
            canonical_form TEXT PRIMARY KEY,
            stage_status TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    
    if db_exists:
        log.info("Database connected", db_path=str(HISTORY_DB))
    else:
        log.info("Database created", db_path=str(HISTORY_DB))


def get_word_status(canonical_form: str) -> Optional[StageStatus]:
    """Get the processing status of a word from the database."""
    conn = sqlite3.connect(HISTORY_DB)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT stage_status FROM words WHERE canonical_form = ?",
        (canonical_form,)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return StageStatus.model_validate_json(result[0])
    return None


def update_word_status(canonical_form: str, stage_status: StageStatus):
    """Update the processing status of a word in the database."""
    conn = sqlite3.connect(HISTORY_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO words (canonical_form, stage_status, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    """, (canonical_form, stage_status.model_dump_json()))
    
    conn.commit()
    conn.close()


async def download_image(url: str, filename: str) -> str:
    """Download an image from URL and save it locally."""
    file_path = TEMP_DIR / filename
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                content = await response.read()
                with open(file_path, 'wb') as f:
                    f.write(content)
                log.info("Image downloaded", filename=filename, size=len(content))
                return str(file_path)
            else:
                raise Exception(f"Failed to download image: {response.status}")


def generate_image_filename(canonical_form: str, index: int = 0) -> str:
    """Generate a unique filename for an image."""
    unique_id = str(uuid.uuid4())[:8]
    return f"{unique_id}_{canonical_form}_{index}.jpg"


def write_anki_csv(words: List[WordEntry]):
    """Write Anki cards to CSV format."""
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        
        # Write Anki CSV header
        writer.writerow(['#separator:;'])
        writer.writerow(['#html:true'])
        writer.writerow(['#notetype column:0'])
        writer.writerow(['type', '2', '3'])
        
        for word in words:
            if not word.canonical_form:
                continue
                
            # Definition cards (Cloze)
            if word.definition:
                writer.writerow([
                    'Cloze',
                    word.definition,
                    ''  # Extra field
                ])
            
            # Example sentence cards (Cloze)
            if word.example_sentences:
                for sentence in word.example_sentences:
                    writer.writerow([
                        'Cloze',
                        sentence,
                        ''  # Extra field
                    ])
            
            # Image ↔ word cards (Basic)
            if word.image_files:
                for image_file in word.image_files:
                    # Word → Image card
                    writer.writerow([
                        'Basic',
                        word.canonical_form,
                        f'<img src="{Path(image_file).name}">'
                    ])
                    
                    # Image → Word card
                    writer.writerow([
                        'Basic',
                        f'<img src="{Path(image_file).name}">',
                        word.canonical_form
                    ])
    
    log.info("Anki CSV written", file=str(OUTPUT_CSV), word_count=len(words))


def generate_copy_script():
    """Generate the script to copy images to Anki collection media folder."""
    script_content = f'''#!/usr/bin/env bash
# Copy generated images to Anki collection media folder
DEST="${{ANKI_COLLECTION_FILE_PATH:-$HOME/Anki/User 1/collection.media/}}"
rsync -av {TEMP_DIR}/ "$DEST"
echo "Images copied to Anki collection media folder: $DEST"
'''
    
    with open(COPY_SCRIPT, 'w') as f:
        f.write(script_content)
    
    # Make script executable
    COPY_SCRIPT.chmod(0o755)
    log.info("Copy script generated", script=str(COPY_SCRIPT)) 