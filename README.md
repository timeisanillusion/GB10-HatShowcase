# Dell GB10 VLM Showcase

**A unified VLM WebUI with real-time hat detection and bounding box overlays for the Dell GB10.**

This is a standalone VLM WebUI forked from NVIDIA's [live-vlm-webui](https://github.com/nvidia-ai-iot/live-vlm-webui), enhanced with real-time object detection, custom bounding box overlays, and specialized for the **Dell GB10** platform running the **Qwen2.5-VL 7B** model entirely in unified memory.

---

## 🏗️ Architecture

* **Backend (Dell GB10):** Runs Ollama, the Qwen2.5-VL 7B model, and the Python WebUI server.
* **Frontend:** Connects via browser, captures webcam via WebRTC, and renders custom HTML5 canvas bounding boxes based on the VLM's coordinate output.

---

## ✨ Features

* 🎥 **Real-time video streaming** via WebRTC from webcam
* 🤖 **VLM integration** - Works with Ollama (Qwen2.5-VL 7B recommended)
* 📊 **System monitoring** - GPU, VRAM, CPU, RAM stats
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
```

---

## ⚙️ The Hat Detection System Prompt

The hat detection overlay is built into the WebUI. Just select YOLO from the model dropdown


---

## 🚀 Quick Start

### Prerequisites (On GB10)

1. **Install Ollama:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Pull the Qwen2.5-VL 7B model:**
   ```bash
   ollama pull qwen2.5vl:7b
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r live-vlm-webui/requirements.txt
   ```

### Installation

```bash
git clone https://github.com/timeisanillusion/GB10-HatShowcase
cd GB10-HatShowcase

---

## 🎮 Running the Showcase

```bash
chmod +x start_vlm_showcase.sh
./start_vlm_showcase.sh
```

**OR** from the `live-vlm-webui` directory:

```bash
cd live-vlm-webui
./scripts/start_server.sh --port 8090 --model qwen2.5vl:7b
```

1. Open `https://<GB10-IP>:8090` in your browser
2. Accept the self-signed certificate (Advanced → Proceed)
3. Select **"Hat Check Demo"** from the prompt dropdown
4. Allow camera access
5. Put on a hat and step into the frame!

---


## 🌟 Key Differences from Original

| Feature | Original | This Project |
|---------|----------|--------------|
| Hat detection | External patch | Built into `index.html` |
| Project structure | Separate patch repo | Single consolidated repo |
| Patching step | Required | Not needed |
| Model | Configurable | Pre-configured for Qwen2.5-VL 7B |

---

## 📄 License

Apache 2.0 - See `live-vlm-webui/LICENSE` for details.

---

## 🙏 Acknowledgments

Built on top of [NVIDIA Live VLM WebUI](https://github.com/nvidia-ai-iot/live-vlm-webui) - a universal web interface for real-time Vision Language Model interaction.

## GB10 Specifics
For some models you may need to edit the ollama context lenght:
```bash
sudo systemctl edit ollama
```
In the editor that opens, add:
```bash
[Service]
Environment="OLLAMA_CONTEXT_LENGTH=8192"
```

Save, then:
```bash
bashsudo systemctl daemon-reload
sudo systemctl restart ollama
```
