#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="testData"
TARGET_DIR="testEnv"
PYTHON_SCRIPT="qb_organizer.py"
VENV_DIR="venv"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FULL_TARGET_DIR="$ROOT_DIR/$TARGET_DIR"
FULL_SCRIPT_PATH="$ROOT_DIR/$PYTHON_SCRIPT"
FULL_VENV_PATH="$ROOT_DIR/$VENV_DIR"

copy_test_data() {
  local source_path="$1"
  local target_path="$2"

  mkdir -p "$target_path"

  if command -v rsync >/dev/null 2>&1; then
    if rsync -a --delete "$source_path/." "$target_path/"; then
      return 0
    fi

    echo "rsync failed; falling back to full copy..." >&2
    rm -rf "$target_path"
    mkdir -p "$target_path"
    rsync -a "$source_path/." "$target_path/"
    return 0
  fi

  rm -rf "$target_path"
  mkdir -p "$target_path"
  cp -a "$source_path/." "$target_path/"
}

if [[ -d "$ROOT_DIR/$SOURCE_DIR" ]]; then
  echo "Copying $SOURCE_DIR to $TARGET_DIR..."
  copy_test_data "$ROOT_DIR/$SOURCE_DIR" "$FULL_TARGET_DIR"
  echo "Done."
else
  echo "Source folder $SOURCE_DIR not found!"
  exit 1
fi

if [[ ! -d "$FULL_VENV_PATH" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$FULL_VENV_PATH"
else
  echo "Virtual environment already exists."
fi

if [[ -f "$FULL_VENV_PATH/bin/activate" ]]; then
  echo "Activating virtual environment..."
  # shellcheck disable=SC1091
  source "$FULL_VENV_PATH/bin/activate"
  echo "Installing requirements..."
  python -m pip install -r "$ROOT_DIR/requirements.txt"
else
  echo "Virtual environment not found! Please create it first."
  exit 1
fi

if [[ -f "$FULL_SCRIPT_PATH" ]]; then
  echo "Running $PYTHON_SCRIPT..."
  python "$FULL_SCRIPT_PATH" "$FULL_TARGET_DIR"
else
  echo "Python script $PYTHON_SCRIPT not found!"
  exit 1
fi

echo "Test script completed."
