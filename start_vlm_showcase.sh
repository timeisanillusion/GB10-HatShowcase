#!/bin/bash
echo "Initializing Dell GB10 VLM Showcase..."

# Ensure the Ollama backend is running
sudo systemctl start ollama

# Pre-load the 72B model into VRAM to eliminate cold-start latency
echo "Loading Qwen2.5-VL 72B into unified memory..."
curl -s -X POST http://localhost:11434/api/generate -d '{"model": "qwen2.5-vl:72b", "keep_alive": "1h"}' > /dev/null

# Navigate to the project directory
cd ~/live-vlm-webui

# Activate the virtual Python environment
source venv/bin/activate

# Grab the primary local IP address of the GB10
LOCAL_IP=$(hostname -I | awk '{print $1}')

# Print the exact URL to connect from the laptop
echo "====================================================="
echo "  Starting WebUI Server..."
echo "  Access the showcase from your laptop browser at:"
echo "  http://$LOCAL_IP:8090"
echo "====================================================="

# Start the server
./scripts/start_server.sh