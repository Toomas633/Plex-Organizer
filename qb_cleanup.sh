#!/bin/bash
delete_unwanted_files() {
    local dir="$1"
    local ext_filter="\.mkv$|\.srt$|\.!qB$|\.mp4$"

    cd "$dir" || return

    for file in *; do
        if [ -d "$file" ]; then
                        cd "$file" || continue
            delete_unwanted_files "$PWD"
                        cd ..
       else
            if ! [[ "$file" =~ $ext_filter ]]; then
                echo "$(date +'%Y-%m-%d %H:%M:%S') - Deleting $file" >> /root/scripts/qb_cleanup_files.log
                rm "$file"
            fi
        fi
    done
}

delete_empty_directories() {
    local dir="$1"

    if [ ! "$(ls -A "$dir")" ]; then
        echo "$(date +'%Y-%m-%d %H:%M:%S') - Removing empty directory: $dir" >> /root/scripts/qb_cleanup_directories.log
        rmdir "$dir"
        return
    fi

    for item in "$dir"/*; do
        if [ -d "$item" ]; then
                        cd "$item" || continue
            delete_empty_directories "$PWD"
                        cd ..
        fi
    done
}

move_single_item_directories() {
    local dir="$1"

    local item_count=$(ls -A "$dir" | grep -v "^\." | wc -l)

    if [ "$item_count" -eq 1 ]; then
        local item=$(ls -A "$dir" | grep -v "^\.")
        local item_extension="${item##*.}"
        if [ -f "$dir/$item" ] && [ "$item_extension" != "!qB" ]; then
            echo "$(date +'%Y-%m-%d %H:%M:%S') - Moving contents of $dir up one level" >> /root/scripts/qb_cleanup_directories.log
            mv "$dir/$item" "$dir/../"
        fi
        return
    fi

    for item in "$dir"/*; do
        if [ -d "$item" ]; then
            cd "$item" || continue
            move_single_item_directories "$item"
            cd ..
        fi
    done
}

start_dirs=("/share/tv" "/share/movies")

for start_dir in "${start_dirs[@]}"; do
    delete_unwanted_files "$start_dir"
    move_single_item_directories "$start_dir"
    delete_empty_directories "$start_dir"
done
