#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"
cd "$SCRIPT_DIR"

REPO_URL_DEFAULT="https://github.com/Toomas633/Plex-Organizer.git"
REPO_URL="${REPO_URL:-$REPO_URL_DEFAULT}"

if ! command -v git >/dev/null 2>&1; then
	echo "git is required but was not found on PATH." >&2
	exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
	echo "No git metadata found; initializing repository..."
	git init
	git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
fi

git fetch --all --prune

current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
update_branch="main"

if ! git show-ref --quiet "refs/remotes/origin/$update_branch"; then
	echo "Remote branch origin/$update_branch not found." >&2
	echo "Available remote branches:" >&2
	git branch -r >&2 || true
	exit 1
fi

git checkout -B "$update_branch" "origin/$update_branch"
git reset --hard "origin/$update_branch"
git clean -fd

echo "Running install.sh to (re)create venv and install dependencies..."
bash ./install.sh