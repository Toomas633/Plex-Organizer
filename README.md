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

Add this command to qBittorrent options under "Run external program on torrent finished":

```bash
sudo plex-organizer <start_directory> <torrent_hash>
```

Arguments:

- `<start_directory>`: The base directory containing the tv and movies subdirectories or %D in qBittorrent ui.
- `<torrent_hash>`: **Optional:** The hash of the torrent to be removed (omit for testing purposes or to ignore torrent automatic removal). Argument %I in qBittorrent ui.

**Be sure to put arguments between "%D" to avoid whitespace cuttofs**

Example:

![Example config image](.github/images/image.png)

For performance reasons it is recommended that **%D** is used instead of entire directory like `/mnt/share`. This way only the specific folder will be organized not entire library on each call. Putting your root directory like `/mnt/share` will remove the torrent with the given hash and process the directories `/mnt/media/tv` and `/mnt/media/movies`.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

## Issues and Feature Requests

If you encounter any issues or have feature requests, please use the GitHub Issues page.

---

Happy organizing!
