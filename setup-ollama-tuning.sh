#!/bin/bash
# Installs the Dell GB10 Ollama tuning drop-in and restarts the Ollama service.
# Run this once after installing Ollama, before ./start_vlm_showcase.sh.
#
# Requires sudo (writes to /etc/systemd/system and restarts a service).
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC="$SCRIPT_DIR/ollama-override.conf"
DEST="/etc/systemd/system/ollama.service.d/override.conf"

if [ ! -f "$SRC" ]; then
    echo "❌ Could not find $SRC"
    exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
    echo "❌ Ollama is not installed. Install it first:"
    echo "   curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

echo "📋 Installing Ollama tuning drop-in to:"
echo "   $DEST"
echo "   (requires sudo)"
sudo install -D -m 0644 "$SRC" "$DEST"
sudo systemctl daemon-reload
sudo systemctl restart ollama

echo "⏳ Waiting for Ollama to come back up..."
for _ in $(seq 1 15); do
    if curl -fsS http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "✅ Tuning applied. Effective Ollama environment:"
systemctl show ollama -p Environment | tr ' ' '\n' | grep -iE "OLLAMA|GGML" || true
