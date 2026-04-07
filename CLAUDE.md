# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a standalone VLM WebUI project with real-time hat detection and bounding box overlays for the Dell GB10 platform. It is based on NVIDIA's [live-vlm-webui](https://github.com/nvidia-ai-iot/live-vlm-webui) but is now a single consolidated project - no external patching required.

**Key features:**
- Real-time webcam streaming via WebRTC
- Hat detection with color-coded bounding boxes (green=hat, blue=no hat)
- Keyboard controls: `r` (rotate), `s` (swap axes), `m` (mirror), `b` (spin box)
- System monitoring: GPU, VRAM, CPU, RAM
- Multi-session support

## Key Commands

### Running the Showcase (Dell GB10)
```bash
./start_vlm_showcase.sh
```

This script:
- Resets the Blackwell GPU memory (kills ollama_llama_server)
- Pre-loads the Qwen2.5-VL 7B model into VRAM
- Starts the WebUI server on port 8090
- Prints the local IP URL for browser access

### Development
```bash
# Install dependencies
pip install -e live-vlm-webui

# Start server with HTTPS
live-vlm-webui/scripts/start_server.sh

# Run tests
live-vlm-webui/scripts/run_tests.sh -u     # unit tests
live-vlm-webui/scripts/run_tests.sh -i     # integration tests
live-vlm-webui/scripts/run_tests.sh -e     # e2e tests
live-vlm-webui/scripts/run_tests.sh -c     # with coverage
```

## Architecture

### Core Components

**Python Backend (`live-vlm-webui/src/live_vlm_webui/`):**
- `server.py` - WebRTC server with WebSocket support for multi-session handling
- `video_processor.py` - Video frame processing with VLM integration and text overlays
- `vlm_service.py` - OpenAI-compatible API client for VLM backends (Ollama, vLLM, NIM, etc.)
- `gpu_monitor.py` - Cross-platform GPU/system monitoring (NVML, jetson-stats)
- `rtsp_track.py` - RTSP camera stream support

**Frontend:**
- `static/index.html` - Web UI with embedded hat detection JavaScript (see `#blackwell-overlay` script)

### Test Structure (`live-vlm-webui/tests/`)
- `unit/` - Unit tests for individual components
- `integration/` - Integration tests (server, WebSocket)
- `e2e/` - End-to-end workflow tests
- `performance/` - Performance regression tests

### Multi-Session Support (v0.4.0)
The server manages multiple concurrent sessions via session IDs, with per-session VLM services and WebSocket connections.

## Hat Detection System Prompt

When the "Hat Check Demo" prompt is selected, the VLM must output in this exact format:

> "Analyze the image, this image is of a room, normally with at least 1 person in it. Step 1: Look closely at the person. Are they wearing a hat? (State Yes or No). Step 2: Use the label "Person (Hat)" if Yes, and "Person" if No. Step 3: Return a bounding box for the person regardless of step 1 in this exact array format: [[ymin, xmin, ymax, xmax, "Label"]]. Coordinates must be scaled 0 to 1000. Step 4: If no person is found, return []."

**Output parsing:**
- `[[ymin, xmin, ymax, xmax, "Person (Hat)"]]` → Green box
- `[[ymin, xmin, ymax, xmax, "Person"]]` → Blue box
- `[]` → No box

## GPU Backend Integration

The system auto-detects local VLM services:
- **Ollama**: `http://localhost:11434/v1/models`
- **vLLM**: `http://localhost:8000/v1/models`

## Platform Support

- **PC**: x86_64 (NVIDIA GPU)
- **DGX Spark**: ARM64
- **Jetson**: Orin, Thor (requires Docker or special setup)
- **macOS**: Apple Silicon (via pip install)

## Testing

- Unit tests: `pytest live-vlm-webui/tests/unit`
- Integration tests: `pytest live-vlm-webui/tests/integration`
- Run with coverage: `pytest live-vlm-webui/tests --cov=live_vlm_webui --cov-report=html`
