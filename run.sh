#!/bin/bash
HOST="http://localhost:8081"
SCRIPT_DIR="$(dirname "$0")"

torrent_hash="$1"
start_dir="$2"

python3 "$SCRIPT_DIR/qb_organizer.py" "$torrent_hash" "$start_dir"