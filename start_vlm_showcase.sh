#!/bin/bash
# --- UNIVERSAL DELL GB10 VLM SHOWCASE ---

# 1. ENVIRONMENT — set critical variables explicitly so the script works
#    correctly whether called directly, via sudo, or via passwordless visudo.
#    sudo strips the environment by default; relying on inherited vars is fragile.

# Resolve the real user's home directory.
# When called via sudo, $SUDO_USER holds the original username; fall back to $USER.
REAL_USER="${SUDO_USER:-$USER}"
export HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"

# Ollama tuning is applied to the Ollama *service* (a systemd drop-in), not here.
# Ollama runs as its own daemon, so variables exported in this script never reach
# it — run ./setup-ollama-tuning.sh once to install the drop-in. Below we only
# verify the key settings actually reached the running daemon, and warn if not.
if command -v systemctl >/dev/null 2>&1; then
    OLLAMA_ENV="$(systemctl show ollama -p Environment 2>/dev/null || true)"
    for v in OLLAMA_CONTEXT_LENGTH GGML_CUDA_NO_VMM OLLAMA_MAX_LOADED_MODELS; do
        case "$OLLAMA_ENV" in
            *"$v"*) ;;
            *) echo "⚠️  $v is not set on the Ollama service — run ./setup-ollama-tuning.sh for stable Blackwell operation." ;;
        esac
    done
fi

# 2. FREE OLLAMA MEMORY (pre-flight reset)
# Unload every model Ollama currently has resident, so the showcase model gets a
# clean, fast load instead of stalling while Ollama evicts a large model that
# another service (e.g. Hermes) left loaded.
#
# This replaces the old `pkill ollama_llama_server` reset, which silently stopped
# working after the Ollama upgrade: the runner is now named `llama-server`, and
# killing it would need root anyway. `ollama stop` unloads gracefully via the API
# (no sudo) and only frees memory -- your models stay on disk. The showcase
# model is (re)loaded by the pre-load step below.
# (Hard reset, only if a runner ever wedges: sudo systemctl restart ollama)
echo "Freeing Ollama memory (unloading any resident models)..."
if command -v ollama >/dev/null 2>&1; then
    for m in $(ollama ps 2>/dev/null | awk 'NR>1 {print $1}'); do
        echo "   unloading $m"
        ollama stop "$m" >/dev/null 2>&1 || true
    done
fi

# 3. DYNAMIC PATHS
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"
REPO_DIR="$PROJECT_ROOT/live-vlm-webui"
VENV_PATH="$REPO_DIR/venv"

# 4. CHOOSE YOUR ENGINE
# Set this to "qwen2.5vl:7b" for near real-time (recommended)
# Set this to "qwen-72b-slim" for high-accuracy flex
MODEL="qwen2.5vl:7b"

# Auto-pull model if not already present locally
if ! ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$MODEL"; then
    echo "📥 Model $MODEL not found locally — pulling from Ollama..."
    ollama pull "$MODEL" || { echo "❌ ollama pull failed — is Ollama installed and running?"; exit 1; }
fi

echo "Pre-loading $MODEL into Blackwell memory..."
curl -s -X POST http://127.0.0.1:11434/api/generate -d "{\"model\": \"$MODEL\", \"keep_alive\": \"1h\"}" > /dev/null

# 5. LAUNCH WEBUI
if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR"

    # Auto-create venv on first run
    if [ ! -d "$VENV_PATH" ]; then
        echo "📦 Creating Python virtual environment at $VENV_PATH ..."
        python3 -m venv "$VENV_PATH" || {
            echo "❌ Failed to create venv. Install python3-venv first:"
            echo "   sudo apt install python3-venv"
            exit 1
        }
    fi

    # Activate venv
    [[ -n "$VIRTUAL_ENV" ]] || source "$VENV_PATH/bin/activate"

    # Ensure setuptools is pinned below 82 — torch 2.11 requires setuptools<82
    # and a higher version breaks the editable-install path finder at import time.
    SETUPTOOLS_VER=$(python -c "import setuptools; print(setuptools.__version__)" 2>/dev/null || echo "0")
    SETUPTOOLS_MAJOR=$(echo "$SETUPTOOLS_VER" | cut -d. -f1)
    if [ "$SETUPTOOLS_MAJOR" -ge 82 ] 2>/dev/null; then
        echo "📦 Pinning setuptools<82 (torch compatibility)..."
        pip install "setuptools<82" --quiet
    fi

    # Auto-install package if missing (e.g. after fresh venv or git clone).
    if ! python -c "import live_vlm_webui" 2>/dev/null; then
        echo "📦 Package not installed — running pip install -e . ..."
        pip install -e . || { echo "❌ pip install failed — see errors above"; exit 1; }
        # Verify the install actually worked before handing off to start_server.sh
        if ! python -c "import live_vlm_webui" 2>/dev/null; then
            echo "❌ Package installed but import still fails. Check errors above."
            exit 1
        fi
    fi

    LOCAL_IP=$(hostname -I | awk '{print $1}')

    echo "====================================================="
    echo "  🚀 DELL GB10 VLM SHOWCASE IS LIVE"
    echo "  Model: $MODEL"
    echo "  URL:   https://$LOCAL_IP:8090"
    echo "====================================================="
    echo "  Windows Tunnel: ssh -L 8090:localhost:8090 $USER@$LOCAL_IP"
    echo "====================================================="
    
    ./scripts/start_server.sh --port 8090 --model "$MODEL"
else
    echo "❌ Error: Could not find repo at $REPO_DIR"
    exit 1
fi
