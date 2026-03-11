---
description: Rules for using ffmpeg and ffprobe in the project
globs: plex_organizer/**/*.py
---

# FFmpeg usage rules

- Always obtain ffmpeg/ffprobe paths through `ffmpeg_utils.get_ffmpeg()` and `ffmpeg_utils.get_ffprobe()`. These resolve binaries from the `static-ffmpeg` package. Never call bare `ffmpeg` or `ffprobe` directly.
- Use `ffmpeg_utils.run_ffprobe_json()` for probing — it returns parsed JSON and handles errors consistently.
- Use `ffmpeg_utils.COPY_STREAM_ARGS` when remuxing (copy all streams without re-encoding). Always include `-map_metadata 0` and `-map_chapters 0` to preserve metadata.
- Remuxing should be done to a temp file first, then atomically replaced via `os.replace()`. Use `ffmpeg_utils.remux_to_temp_and_replace()` when possible.
- WAV extraction for Whisper inference should use `ffmpeg_utils.WAV_OUTPUT_ARGS` for consistent sample format (mono, 16 kHz).
- All ffmpeg/ffprobe failures should be caught and logged via `log.log_error()` — never let them crash the pipeline.
- Use `ffmpeg_utils.probe_video_quality()` for quality fallback during renaming — it probes the first video stream height and maps it to a standard label (`2160p`, `1440p`, `1080p`, `720p`, `480p`). Returns `None` on failure so rename logic can gracefully omit quality.
