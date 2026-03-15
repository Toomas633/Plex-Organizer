<img align="right" src="https://sonarcloud.io/api/project_badges/quality_gate?project=Toomas633_Plex-Organizer">

# Plex Organizer

- [Plex Organizer](#plex-organizer)
- [Features](#features)
  - [Example Directory Structure](#example-directory-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Update](#update)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Manual running](#manual-running)
  - [Automated running](#automated-running)
- [License](#license)
- [Issues and Feature Requests](#issues-and-feature-requests)

> **[FAQ](FAQ.md)** · **[Development](DEVELOPMENT.md)**

Plex Organizer is a Python-based utility designed to help manage and organize media files for Plex Media Server. It automates tasks such as renaming files, deleting unwanted files, moving directories, and cleaning up empty folders.

**_NB!! Any data loss is not on me but you can still report any bugs or faults you find in issues_**

## Features

- **Torrent Removal**: Removes torrents from the client after processing.
- **File Renaming**: Automatically renames media files based on predefined rules for TV shows and movies.
- **Unwanted File Deletion**: Removes unnecessary files/folders from specified directories.
- **Directory Management**: Moves directories to their appropriate locations and deletes empty directories.
- **Customizable Directories**: Supports separate directories for TV shows and movies.
- **Handle Plex:** Handles plex directories and optimized versions.
- **Audio language tagging (optional)**: If enabled, detects missing audio track languages and writes ISO 639-2 tags into the container metadata (uses `faster-whisper` + bundled `ffmpeg`/`ffprobe`).
- **Subtitle embedding (optional)**: If enabled, embeds external subtitles into the video file and tags subtitle language/type metadata (uses bundled `ffmpeg`/`ffprobe` + `langdetect`).
- **Subtitle fetching (optional)**: If enabled, searches free online subtitle providers (OpenSubtitles, Podnapisi, Gestdown, TVsubtitles) for missing subtitles in configured languages and embeds them into videos that lack those subtitle streams.
- **Subtitle syncing (optional)**: If enabled, synchronizes embedded subtitle timing to the audio track using `ffsubsync`. Only text-based subtitle streams are synced; bitmap formats (PGS, VobSub) are left unchanged.
- **Quality detection fallback**: When `include_quality` is enabled but no quality tag (e.g. `1080p`) is found in the filename, the organizer probes the actual video stream height via `ffprobe` and maps it to the nearest standard label (`2160p`, `1440p`, `1080p`, `720p`, `480p`).
- **Sonarr/Radarr integration (optional)**: If enabled, automatically triggers via Custom Script environment variables, skips rename/move (the \*arr app handles naming), deletes downloaded torrent files, and sends targeted library rescan notifications after processing.
- **Config file:** Ini file for common configuration options that can be set, disabled or enabled

Notes:

- Cleanup is intentionally aggressive: only video files (`.mkv`, `.mp4`), in-progress qBittorrent files (`.!qB`), and the organizer index file (`.plex_organizer.index`) are kept. Subtitle files/folders (e.g. `Subs/`, `Subtitles/`) are removed.
- The organizer keeps a per-library index (`.plex_organizer.index`) so already-processed files can be skipped on future runs.
- If the start directory is not a recognised media folder (does not contain `tv` or `movies` in its path and is not a main folder with `tv/` or `movies/` subfolders), the organizer removes the torrent (if a hash was provided) and exits — no files are deleted, moved, or modified.
- If qBittorrent torrent removal is enabled (by providing a torrent hash), the qBittorrent Web API must be reachable and credentials must be set.

### Example Directory Structure

<div style="display: flex; gap: 10px;">
<div style="flex: 2;">
Example of the directory structure that Plex Organizer processes:
<pre>
<code>
start_directory/
├── movies/
│   ├── Venom.2018.BluRay.x264-[YTS.AM].mp4
│   ├── Warcraft.2016.1080p.BluRay.x264-[YTS.AG].mkv
│   ├── 1917 (2019) [1080p] [BluRay] [5.1] [YTS.MX]/
│   │   └── Subs/
│   │       ├── English.srt
│   │       └── Spanish.srt
│   ├── 2 Fast 2 Furious (2003) [1080p]/
│   │   └── Subs/
│   │       └── French.srt
│   ├── 6 Underground (2019) [WEBRip] [1080p] [YTS.LT]/
│   │   ├── 6 Underground (2019).mp4
│   │   └── Subs/
│   │       ├── Turkish.tur.srt
│   │       ├── Norwegian.nor.srt
│   │       └── Danish.dan.srt
│   └── random_file.txt
└── tv/
    ├── Black Bird/
    │   ├── S01E01.mp4
    │   ├── S01E02.mp4
    │   └── unwanted_file.txt
    ├── Colony/
    │   ├── S01E01.mp4
    │   ├── S01E02.mp4
    │   └── extra_file.txt
    └── Loki/
        ├── S01E01.mp4
        └── S01E02.mp4
</pre>
</code>
</div>
<div style="flex: 1;">
And what it looks like afterwards:
<pre>
<code>
start_directory/
├─ movies/
│  ├── 1917 (2019) 1080p.mp4
│  ├── 2 Fast 2 Furious (2003) 1080p.mp4
│  ├── 6 Underground (2019) 1080p.mp4
│  ├── Venom (2018).mp4
│  └── Warcraft (2016) 1080p.mkv
└─ tv/
   ├── Black Bird/
   │   └─ Season 1/
   │     ├── Black Bird S01E01.mp4
   │     └── Black Bird S01E02.mp4
   ├── Colony/
   │   └─ Season 1/
   │     ├── Colony S01E01.mp4
   │     └── Colony S01E02.mp4
   └── Loki/
      └── Season 1/
         ├── Loki S01E01.mp4
         └── Loki S01E02.mp4
</pre>
</code>
</div>
</div>

## Requirements

- Python 3.10+
- **Root privileges** — the organizer must be run as root (`sudo`)

## Data directory

By default, `config.ini`, log files, and the lock file are stored in `/root/.config/plex-organizer/`.

The location can be overridden with the `PLEX_ORGANIZER_DIR` environment variable, or by running from a directory that already contains a `config.ini`.

## Installation

Install directly from GitHub with [pipx](https://pipx.pypa.io/) (recommended) — no need to clone the repo.

Since the organizer requires root privileges, install as root so the command is available on root's PATH:

```bash
sudo pipx install git+https://github.com/Toomas633/Plex-Organizer.git
sudo pipx ensurepath
```

This gives you the `plex-organizer` command on root's PATH.

> **Making it available for other users:** `pipx` installs the binary to `/root/.local/bin/`, which is only on root's `PATH`. If another user (e.g. a `qbittorrent` service account) needs to call `sudo plex-organizer`, create a symlink into a system-wide directory:
>
> ```bash
> sudo ln -s /root/.local/bin/plex-organizer /usr/local/bin/plex-organizer
> ```

Run the main pipeline:

```bash
sudo plex-organizer <start_dir> [torrent_hash]
```

Launch the interactive management menu (logs, config migration, custom runs):

```bash
plex-organizer --manage
```

## Update

```bash
sudo pipx upgrade plex-organizer
```

## Configuration

All user configuration is handled in `config.ini`.

The file is auto-managed on startup:

- Missing required sections/options are added.
- Unknown options inside known sections are removed.

Key sections:

- `[qBittorrent]`
  - `host`: Base URL for the Web API (default `http://localhost:8081`). Used for torrent removal.
  - `username`: Username for qbittorrent web api
  - `password`: Password to authenticate with
- `[Settings]`
  - `delete_duplicates`: If `true`, deletes source files when the destination already exists.
  - `include_quality`: If `true`, appends quality like `1080p` to renamed files. When the filename lacks a quality tag, the organizer probes the video stream height via `ffprobe` as a fallback.
  - `capitalize`: If `true`, title-cases show/movie names.
  - `cpu_threads`: Limits CPU parallelism for some processing steps.
- `[Logging]`
  - `enable_logging`: If `true`, logs errors to a log file
  - `log_file`: Name of the log file
  - `clear_log`: If `true`, log file is cleared on each run of the script
  - `timestamped_log_files`: If `true`, log files are timestamped and put to logs folder
  - `level`: Either `INFO` by default or `DEBUG` if Debug log rows are needed
- `[Audio]`
  - `enable_audio_tagging`: If `true`, runs audio language tagging after moves.
  - `whisper_model_size`: Whisper model size for `faster-whisper` (default `tiny`).
- `[Subtitles]`
  - `enable_subtitle_embedding`: If `true`, embeds external subtitles and tags metadata before subtitle files/folders are removed.
  - `analyze_embedded_subtitles`: If `true` (default), also analyzes already-embedded subtitle streams for missing/unknown language tags and writes detected language and SDH metadata back into the container. When `false`, only externally embedded subtitles are tagged.
  - `fetch_subtitles`: Comma-separated list of ISO 639-2 language codes to fetch (e.g. `eng` or `eng, est`). Leave empty to disable. Default: `eng`.
  - `subtitle_providers`: Comma-separated list of subtitle providers for fetching (default: `opensubtitles, podnapisi, gestdown, tvsubtitles`).
  - `sync_subtitles`: If `true`, synchronizes embedded subtitle timing to the audio track after all other subtitle operations. Default: `true`.
- `[Sonarr]`
  - `enabled`: If `true`, enables Sonarr integration. Default: `false`.
  - `host`: Base URL for Sonarr's API (default `http://localhost:8989`).
  - `api_key`: Sonarr API key (found in Sonarr → Settings → General).
- `[Radarr]`
  - `enabled`: If `true`, enables Radarr integration. Default: `false`.
  - `host`: Base URL for Radarr's API (default `http://localhost:7878`).
  - `api_key`: Radarr API key (found in Radarr → Settings → General).

**NB!!** Make sure the qBittorrent `host` is correct. Torrent removal is best-effort: failures are logged and processing continues.

## Usage

Start directory should have either...

1. The folders for movies and tv as shown in the example. Show names are taken from the parent folder inside tv folder and only episode, season and quality are taken from the file names.
2. Just the given torrent save path folder (%D option in qBittorrent)

### Manual running

```bash
sudo plex-organizer <start_directory>
```

### Automated running

#### Via qBittorrent (standalone)

Use this method when running Plex Organizer **without** Sonarr/Radarr. Add this command to qBittorrent options under **"Run external program on torrent finished"**:

```bash
sudo plex-organizer "%D" "%I"
```

Arguments:

- `%D` — Torrent save path (the directory where qBittorrent saved the files).
- `%I` — Torrent hash. **Optional:** omit for testing or to skip automatic torrent removal.

> **Important:** Always wrap `%D` in double quotes (`"%D"`) to handle paths with spaces.

**Running as a different user:**

qBittorrent often runs under a non-root service account (e.g. `qbittorrent`, `debian`). Since Plex Organizer requires root, `sudo` must be able to run without a password prompt. Add a sudoers rule:

```bash
# /etc/sudoers.d/plex-organizer
qbittorrent ALL=(root) NOPASSWD: /usr/local/bin/plex-organizer
```

Replace `qbittorrent` with the actual user that qBittorrent runs as. You can verify with:

```bash
ps -o user= -p $(pgrep -f qbittorrent-nox)
```

Adjust the path in the sudoers rule to match your installation (`which plex-organizer`).

**How it works:**

- The organizer renames and moves files into the final Plex layout, then removes the torrent from qBittorrent (files are kept on disk since they have already been moved to their destination).
- Subtitle embedding, fetching, syncing, audio tagging, and cleanup all run as configured.

> **Note:** If you are using Sonarr/Radarr integration (see below), do **not** also configure qBittorrent to run `plex-organizer`. Let the \*arr app trigger it via Custom Script instead — otherwise files will be processed twice.

Example:

![Example config image](.github/images/image.png)

For performance reasons it is recommended that `%D` is used instead of an entire directory like `/mnt/share`. This way only the specific torrent folder is organized, not the entire library on each call. Putting your root directory like `/mnt/share` will remove the torrent with the given hash and process the directories `/mnt/media/tv` and `/mnt/media/movies`.

#### Via Sonarr / Radarr (Custom Script)

When Sonarr or Radarr integration is enabled in `config.ini`, you can set up Plex Organizer as a **Custom Script** connection. Since Sonarr/Radarr typically run as their own service user, the script needs root privileges — use a wrapper script that calls `sudo`:

**1. Create a wrapper script:**

```bash
sudo tee /usr/local/bin/plex-organizer-sudo > /dev/null << 'EOF'
#!/bin/bash
sudo plex-organizer "$@"
EOF
sudo chmod +x /usr/local/bin/plex-organizer-sudo
```

**2. Allow the Sonarr/Radarr user to run it without a password:**

```bash
# /etc/sudoers.d/plex-organizer
sonarr ALL=(root) NOPASSWD: /usr/local/bin/plex-organizer
radarr ALL=(root) NOPASSWD: /usr/local/bin/plex-organizer
```

Replace `sonarr`/`radarr` with the actual users your services run as. Verify with:

```bash
ps -o user= -p $(pgrep -f Sonarr)
ps -o user= -p $(pgrep -f Radarr)
```

> **Note:** If you installed via `pipx` and haven't created the symlink described in the [Installation](#installation) section, use the full path `/root/.local/bin/plex-organizer` in the sudoers rule and wrapper script instead.

**3. Configure the Custom Script in Sonarr/Radarr:**

1. Go to **Settings → Connect → + → Custom Script**.
2. Set **Path** to `/usr/local/bin/plex-organizer-sudo`.
3. Select **On Download** and/or **On Rename** triggers.
4. Click **Test** to verify the connection (the organizer will log "test event — OK" and exit cleanly).

When triggered this way, the organizer automatically detects Sonarr/Radarr environment variables (`sonarr_eventtype`, `sonarr_series_path`, `sonarr_download_id`, etc.) — no CLI arguments are needed.

**How it works:**

- Rename/move is skipped for the media type managed by the \*arr app (Sonarr for TV, Radarr for movies) since it already placed files in their final layout.
- Subtitle embedding, fetching, syncing, audio tagging, and cleanup still run.
- The completed torrent is removed from qBittorrent with `deleteFiles=true` so downloaded source files are cleaned up.
- After processing, a targeted library rescan is sent to the \*arr app. If the specific series/movie is not found, a full library rescan is triggered instead.
- All API calls are best-effort: failures are logged and processing continues.

**Docker / Kubernetes:**

Custom Scripts run _inside_ the Sonarr/Radarr container, so `plex-organizer` must be available there. The Sonarr/Radarr containers typically run as root, so no sudo wrapper is needed.

1. **Install `plex-organizer` inside the container.** The easiest approach is to create a custom image:

   ```dockerfile
   FROM linuxserver/sonarr:latest
   RUN pip install --break-system-packages git+https://github.com/Toomas633/Plex-Organizer.git
   ```

   Alternatively, mount a host-side install into the container and install dependencies at startup via a [custom init script](https://docs.linuxserver.io/general/container-customization/#custom-scripts).

2. **Ensure shared media paths.** The media directories must be mounted into the Sonarr/Radarr container at paths the organizer can access. Use the same mount paths across containers to avoid mismatches (e.g. `/data/tv`, `/data/movies`).

3. **qBittorrent connectivity.** The `[qBittorrent] host` in `config.ini` must be reachable from inside the container (e.g. `http://qbittorrent:8081` if using Docker Compose service names, or the host IP).

4. **Config persistence.** Mount a host directory or volume to the organizer's data path so `config.ini` and logs survive container restarts:

   ```yaml
   volumes:
     - /path/to/plex-organizer-config:/root/.config/plex-organizer
   ```

   Or set the `PLEX_ORGANIZER_DIR` environment variable to a mounted path.

5. **Set the Custom Script path** to `plex-organizer` (or `which plex-organizer` inside the container to find the full path).

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

## Issues and Feature Requests

If you encounter any issues or have feature requests, please use the GitHub Issues page.

---

Happy organizing!
