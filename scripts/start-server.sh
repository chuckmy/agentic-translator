#!/usr/bin/env bash
# Start agentic-translator as a long-running server on a Tailscale-joined host.
#
# Usage:
#   scripts/start-server.sh
#
# Loads ~/.config/agentic-translator/server.env for credentials and paths
# (AT_MODELS_DIR, AT_ENGINES_DIR, ANTHROPIC_API_KEY, AT_COMPANY_MODE), then
# runs Streamlit headless on 0.0.0.0:8501 so Tailnet peers can reach it.
#
# See docs/deploy-tailscale.md for the full deployment guide.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$REPO_ROOT/.venv}"
PORT="${PORT:-8501}"
ADDRESS="${ADDRESS:-0.0.0.0}"
ENV_FILE="${ENV_FILE:-$HOME/.config/agentic-translator/server.env}"
LOG_DIR="${LOG_DIR:-$HOME/.config/agentic-translator}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/streamlit.log}"

mkdir -p "$LOG_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "error: $ENV_FILE not found" >&2
    echo "       see docs/deploy-tailscale.md (Part 1, step 3) to create it." >&2
    exit 1
fi

# Load company env (paths, API key, AT_COMPANY_MODE)
# shellcheck disable=SC1090
source "$ENV_FILE"

if [[ ! -d "$VENV" ]]; then
    echo "error: virtualenv $VENV not found." >&2
    echo "       run: python3.11 -m venv $VENV && $VENV/bin/pip install -r $REPO_ROOT/requirements.txt" >&2
    exit 1
fi

cd "$REPO_ROOT"

echo "Starting Streamlit on $ADDRESS:$PORT"
echo "  AT_MODELS_DIR  = ${AT_MODELS_DIR:-(unset)}"
echo "  AT_ENGINES_DIR = ${AT_ENGINES_DIR:-(unset)}"
echo "  AT_COMPANY_MODE= ${AT_COMPANY_MODE:-(unset)}"
echo "  logging to     = $LOG_FILE"

exec "$VENV/bin/streamlit" run app.py \
    --server.address "$ADDRESS" \
    --server.port "$PORT" \
    --server.headless true \
    --browser.gatherUsageStats false \
    >> "$LOG_FILE" 2>&1
