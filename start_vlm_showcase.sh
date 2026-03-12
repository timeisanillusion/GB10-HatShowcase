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
# Set this to "qwen2.5vl:7b" for real-time (recommended)
# Set this to "qwen-72b-slim" for high-accuracy flex
MODEL="qwen2.5vl:7b"

echo "Pre-loading $MODEL into Blackwell memory..."
curl -s -X POST http://127.0.0.1:11434/api/generate -d "{\"model\": \"$MODEL\", \"keep_alive\": \"1h\"}" > /dev/null

# 4. LAUNCH WEBUI
if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR"
    
    # Activate venv
    [[ -n "$VIRTUAL_ENV" ]] || source "$VENV_PATH/bin/activate"

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
