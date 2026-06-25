# Dell GB10 VLM Showcase

**A unified VLM WebUI with real-time hat detection and bounding box overlays for the Dell GB10.**

This is a standalone VLM WebUI forked from NVIDIA's [live-vlm-webui](https://github.com/nvidia-ai-iot/live-vlm-webui), enhanced with real-time object detection, custom bounding box overlays, and specialized for the **Dell GB10** platform running the **Qwen2.5-VL 7B** model entirely in unified memory.

---

## 🏗️ Architecture

* **Backend (Dell GB10):** Runs Ollama, the Qwen2.5-VL 7B model, and the Python WebUI server.
* **Frontend:** Connects via browser, captures webcam via WebRTC, and renders custom HTML5 canvas bounding boxes based on the VLM's coordinate output.

---

## ✨ Features

* 🎥 **Real-time video streaming** via WebRTC from webcam or RTSP camera
* 🤖 **Multi-model VLM** — run up to 2 LLMs side-by-side via Ollama (Qwen2.5-VL 7B recommended)
* 🎯 **YOLO + Hat Check overlay** — bounding-box detection drawn on the live video feed
* 💰 **Cloud cost estimator** — projects what the same workload would cost on GPT-4o, Claude, Gemini etc.
* 📊 **System monitoring** — GPU utilization, Memory Pool (unified memory), CPU, sparklines
* 🔒 **Fully offline-capable** — no CDN/internet required at runtime
* 🌓 **Light/Dark theme** toggle

---

## 📂 Project Structure

```
GB10-HatShowcase/
├── live-vlm-webui/          # Core WebUI (VLM integration, server, video processing)
│   ├── src/live_vlm_webui/
│   │   ├── server.py        # WebRTC/WebSocket server
│   │   ├── video_processor.py # Frame processing with VLM
│   │   ├── vlm_service.py   # VLM API client
│   │   ├── gpu_monitor.py   # System monitoring
│   │   ├── rtsp_track.py    # RTSP camera support
│   │   └── static/
│   │       └── index.html   # Web UI (includes hat detection)
│   ├── scripts/             # Build and deployment scripts
│   └── tests/               # Unit, integration, e2e tests
├── start_vlm_showcase.sh    # Launch script for the showcase
├── setup-ollama-tuning.sh   # One-time Ollama tuning installer (systemd drop-in)
├── ollama-override.conf     # Ollama tuning values for the GB10 (Blackwell)
```

---

## ⚙️ The Hat Detection System Prompt

The hat detection overlay is built into the WebUI. Just select YOLO from the model dropdown


---

## 🚀 Quick Start

### Prerequisites (On GB10)

You need three things installed on the GB10 before running the launch script:

1. **Python 3.10+ with venv support (plus openssl for self-signed cert):**
   ```bash
   sudo apt install -y python3 python3-venv git curl openssl
   ```

2. **Ollama:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

3. **Ollama tuning for Blackwell.** The GB10 needs a handful of Ollama settings
   for stability (they prevent CUDA VMM assertion failures and flash-attention
   issues) and for the two-model showcase behaviour. Apply them with the bundled
   helper, which installs a systemd drop-in and restarts Ollama:
   ```bash
   ./setup-ollama-tuning.sh
   ```
   Verify it took effect:
   ```bash
   systemctl show ollama -p Environment | tr ' ' '\n' | grep -E 'OLLAMA|GGML'
   ```
   The full list of settings (with per-line notes) lives in `ollama-override.conf`.
   The `OLLAMA_HOST` / `OLLAMA_ORIGINS` entries there are optional — they're only
   needed if you reach the Ollama API from another machine.

That's it — the launch script handles the rest (venv, pip install, model pull, model pre-load).

### Installation

```bash
git clone https://github.com/timeisanillusion/GB10-HatShowcase
cd GB10-HatShowcase
chmod +x start_vlm_showcase.sh
./start_vlm_showcase.sh
```

The first run will automatically:
- Create a Python virtual environment in `live-vlm-webui/venv`
- Install the WebUI package and dependencies
- Pull `qwen2.5vl:7b` from Ollama (~6 GB download, one-time)
- Pre-load the model into GPU memory

Subsequent runs skip all of the above and start immediately.

---

## 🎮 Using the Showcase

After the script starts, you'll see:
```
🚀 DELL GB10 VLM SHOWCASE IS LIVE
URL: https://<GB10-IP>:8090
```

1. Open `https://<GB10-IP>:8090` in your browser
2. Accept the self-signed certificate (Advanced → Proceed)
3. Allow camera access — the Qwen2.5-VL model is pre-selected and ready
4. (Optional) Switch the prompt preset to **"Hat Check Demo"** to enable bounding-box overlays

**Connecting from another machine?** HTTPS is required for webcam access. If your browser blocks the self-signed cert, use an SSH tunnel:
```bash
ssh -L 8090:localhost:8090 user@<GB10-IP>
# then browse to https://localhost:8090
```

---

## 📄 License

Apache 2.0 - See `live-vlm-webui/LICENSE` for details.

---

## 🙏 Acknowledgments

Built on top of [NVIDIA Live VLM WebUI](https://github.com/nvidia-ai-iot/live-vlm-webui) — a universal web interface for real-time Vision Language Model interaction.
