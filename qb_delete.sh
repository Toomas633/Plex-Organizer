#!/bin/bash
HOST="http://localhost:8081"
TORRENT_HASH="$1"

curl -s -X POST "$HOST/api/v2/torrents/delete" --data "hashes=$TORRENT_HASH&deleteFiles=false"

echo "$(date +'%Y-%m-%d %H:%M:%S') - Torrent '$TORRENT_HASH' deleted." >> /root/scripts/qb_delete.log
/bin/bash /root/scripts/qb_cleanup.sh
