#!/usr/bin/env bash
# Copy generated images to Anki collection media folder
DEST="${ANKI_COLLECTION_FILE_PATH:-$HOME/Anki/User 1/collection.media/}"
rsync -av /Users/sasamilic/PROGRAMMING/ankigen-bcs2/tmp/images/ "$DEST"
echo "Images copied to Anki collection media folder: $DEST"
