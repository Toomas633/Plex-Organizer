#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

usage() {
  cat <<'EOF'
Usage: ./install.sh [--upgrade]

Creates ./venv (if missing) and installs Python dependencies from requirements.txt.

Options:
  --upgrade   Pass --upgrade to pip when installing requirements
EOF
  return 0
}

PIP_UPGRADE_ARGS=()

case "${1:-}" in
  "")
    ;;
  --upgrade)
    PIP_UPGRADE_ARGS=(--upgrade)
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    echo "Unknown option: ${1}" >&2
    usage >&2
    exit 2
    ;;
esac

PYTHON=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  echo "Python not found. Install Python 3 first." >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment at: $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
else
  echo "Virtual environment already exists: $VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
  echo "Missing requirements file: $REQUIREMENTS_FILE" >&2
  exit 1
fi

echo "Installing dependencies from: $REQUIREMENTS_FILE"
python -m pip install ${PIP_UPGRADE_ARGS[@]:+"${PIP_UPGRADE_ARGS[@]}"} -r "$REQUIREMENTS_FILE"

echo "Initializing config.ini (if needed)"
python -c "import config; config.ensure_config_exists()"

if [[ -t 0 ]] && [[ -t 1 ]] && [[ -f "$SCRIPT_DIR/generate_indexes.py" ]]; then
  echo
  read -r -p "Run index generation now? [y/N] " run_indexing
  if [[ "${run_indexing,,}" == "y" || "${run_indexing,,}" == "yes" ]]; then
    while true; do
      echo "Accepted roots: <root with tv+movies>, <tv>, <tv/<Show>>, <movies>"
      read -r -p "Enter folder to index (or 'q' to cancel): " media_root

      if [[ -z "$media_root" ]]; then
        echo "Please enter a folder path or 'q' to cancel."
        continue
      fi

      if [[ "${media_root,,}" == "q" ]]; then
        echo "Index generation cancelled."
        break
      fi

      if python "$SCRIPT_DIR/generate_indexes.py" "$media_root"; then
        break
      fi

      status=$?
      if [[ $status -eq 2 ]]; then
        echo "Invalid folder. Try again or enter 'q' to cancel."
        continue
      fi

      echo "Index generation failed (exit code $status). Try again or enter 'q' to cancel."
    done
  fi
fi

echo "Done. Activate with: source venv/bin/activate"