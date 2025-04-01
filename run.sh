#!/bin/bash
HOST="http://localhost:8081"
SCRIPT_DIR="$(dirname "$0")"

torrent_hash="$1"
start_dir="$2"

if [ -z "$torrent_hash" ] || [ -z "$start_dir" ]; then
    echo "Usage: $0 <torrent_hash> <start_dir>"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    echo "Virtual environment not found in $SCRIPT_DIR/venv"
    exit 1
fi

source $SCRIPT_DIR/venv/bin/activate

python3 $SCRIPT_DIR/qb_organizer.py $torrent_hash $start_dir