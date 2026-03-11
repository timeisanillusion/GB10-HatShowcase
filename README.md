# Dell GB10 Live VLM Showcase: Hat Detection Overlay

This repository contains frontend patches and launch scripts to expand the [NVIDIA Live VLM WebUI](https://github.com/nvidia-ai-iot/live-vlm-webui) with real-time object detection and custom bounding box overlays. 

It is designed specifically to showcase the massive memory bandwidth and inference power of the **Dell GB10** by running the **Qwen2.5-VL 72B** parameter model entirely in unified memory.

## 🏗️ Architecture

* **Backend (Dell GB10):** Runs Ollama, the Qwen2.5-VL 72B model, and the Python WebUI server.
* **Frontend (Laptop):** Connects to the GB10 via a local network browser, captures the local laptop webcam via WebRTC, and renders the custom HTML5 canvas bounding boxes based on the VLM's coordinate output.

## 📂 Repository Contents

* `start_vlm_showcase.sh`: Bash script to load the 72B model into VRAM, start the server, and print the local connection IP.
* `VLM_Showcase.desktop`: Clickable Linux desktop launcher for Spark OS/Ubuntu.
* `canvas_overlay.js`: JavaScript logic to parse VLM coordinate strings, throttle WebRTC frame rates, and draw color-coded bounding boxes.
* `index_patch.html`: HTML snippet containing the transparent `<canvas>` element needed for drawing over the video feed.

## ⚙️ The Critical System Prompt

For the JavaScript regular expressions to parse the bounding boxes correctly, the vision model **must** be constrained to a specific output format. 

In the WebUI settings (or your `.env` configuration), you must set the System Prompt to exactly this:

> "Analyze the image. Locate every person and check if they are wearing a hat. Return ONLY a list of bounding boxes in this exact format: `[label, ymin, xmin, ymax, xmax]`. Use the label 'Person (Hat)' if they have a hat, and 'Person' if they do not. Coordinates must be normalized between 0 and 1000. Do not include any other text."

## 🚀 Setup & Installation

**1. Prepare the Base Environment (On the GB10)**
Ensure Ollama is installed
```bash
curl -fsSL https://ollama.com/install.sh | sh
```
and pull the required model:
```bash
ollama pull qwen2.5-vl:72b

```

**2. Clone the Base NVIDIA Repository**

```bash
git clone [https://github.com/nvidia-ai-iot/live-vlm-webui.git](https://github.com/nvidia-ai-iot/live-vlm-webui.git)
cd live-vlm-webui
python3 -m venv venv
source venv/bin/activate
pip install -e .

```


**3. Apply the Patches**
Instead of manually editing the NVIDIA repository, run the included Python patcher to automatically inject the HTML canvas and JavaScript drawing logic.

Ensure you are in the directory containing `apply_patches.py` and run:
```bash
python3 apply_patches.py
```

**4. Install the Launchers**

* Move `start_vlm_showcase.sh` to your home directory (`~`) and make it executable (`chmod +x ~/start_vlm_showcase.sh`).
* Move `VLM_Showcase.desktop` to your `~/Desktop` and allow execution permissions.

## 🎮 Running the Showcase

1. Double-click the **VLM 72B Showcase** icon on the GB10 desktop.
2. A terminal will open, pre-load the model into memory, and print a URL (e.g., `http://192.168.x.x:8090`).
3. Open that URL on your laptop's browser.
4. Accept the camera permissions, put on a hat, and step into the frame!

```
