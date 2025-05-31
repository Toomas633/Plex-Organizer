#!/bin/bash
SCRIPT_DIR="$(dirname "$0")"

torrent_hash="$2"
start_dir="$1"

if [ -z "$start_dir" ]; then
    echo "Usage: $0 <start_dir> <optional_torrent_hash>"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    echo "Virtual environment not found in $SCRIPT_DIR/venv"
    exit 1
fi

source $SCRIPT_DIR/venv/bin/activate

python3 $SCRIPT_DIR/qb_organizer.py $start_dir $torrent_hash