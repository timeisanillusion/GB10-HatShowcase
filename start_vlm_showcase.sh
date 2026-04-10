#!/bin/bash
# --- UNIVERSAL DELL GB10 VLM SHOWCASE ---

# 1. ZOMBIE CLEANUP (Blackwell Reset)
echo "Resetting Blackwell GPU memory..."
sudo pkill -9 ollama_llama_server 2>/dev/null
sleep 1

# 2. DYNAMIC PATHS
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"
REPO_DIR="$PROJECT_ROOT/live-vlm-webui"
VENV_PATH="$REPO_DIR/venv"

# 3. CHOOSE YOUR ENGINE
# Set this to "qwen2.5vl:7b" for near real-time (recommended)
# Set this to "qwen-72b-slim" for high-accuracy flex
MODEL="qwen2.5vl:72b"

echo "Pre-loading $MODEL into Blackwell memory..."
curl -s -X POST http://127.0.0.1:11434/api/generate -d "{\"model\": \"$MODEL\", \"keep_alive\": \"1h\"}" > /dev/null

# 4. LAUNCH WEBUI
if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR"
    
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
