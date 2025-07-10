#!/usr/bin/env bash
# Copy generated images to Anki collection media folder

# Expand tilde in ANKI_COLLECTION_FILE_PATH if it starts with ~
if [ -n "$ANKI_COLLECTION_FILE_PATH" ]; then
    DEST="${ANKI_COLLECTION_FILE_PATH/#\~/$HOME}"
else
    DEST="$HOME/Anki/User 1/collection.media"
fi

echo "Copying images to: $DEST"
rsync -av /Users/sasamilic/PROGRAMMING/ankigen-bcs2/tmp/images/ "$DEST"
echo "Images copied to Anki collection media folder: $DEST"
