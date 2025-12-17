# Minimal devcontainer image for Plex-Organizer
# Ubuntu base + ffmpeg for faster-whisper.

FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python-is-python3 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
