// --- 1. CONFIGURATION & SETUP ---
const TARGET_FPS = 3; // Throttles capture to 3 frames per second for the 72B model
let lastFrameTime = 0;

const videoElement = document.getElementById('webcamVideo'); 
const canvas = document.getElementById('overlayCanvas');
const ctx = canvas.getContext('2d');

// --- 2. THROTTLE LOGIC (Inject this where the repo captures the frame) ---
function shouldSendFrame() {
    const now = Date.now();
    if (now - lastFrameTime < (1000 / TARGET_FPS)) {
        return false; // Skip this frame to let the GB10 catch up
    }
    lastFrameTime = now;
    return true;
}

// --- 3. DRAWING LOGIC (Call this when the WebSocket/API returns the text) ---
function processVlmResponse(vlmTextResponse) {
    // Sync canvas dimensions to the actual displayed video size
    canvas.width = videoElement.clientWidth;
    canvas.height = videoElement.clientHeight;

    // Clear previous boxes
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Regex to extract Qwen's format: [Label, ymin, xmin, ymax, xmax]
    const regex = /\[([^,\]]+?),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]/g;
    let match;

    while ((match = regex.exec(vlmTextResponse)) !== null) {
        const label = match[1].trim();
        
        // Qwen returns 0-1000 normalized coordinates. Convert to pixels.
        const ymin = (parseInt(match[2], 10) / 1000) * canvas.height;
        const xmin = (parseInt(match[3], 10) / 1000) * canvas.width;
        const ymax = (parseInt(match[4], 10) / 1000) * canvas.height;
        const xmax = (parseInt(match[5], 10) / 1000) * canvas.width;

        const width = xmax - xmin;
        const height = ymax - ymin;

        // Color coding: Green for Hats, Red for standard Persons
        if (label.includes("Hat")) {
            ctx.strokeStyle = "#00FF00"; 
            ctx.fillStyle = "#00FF00";
        } else {
            ctx.strokeStyle = "#FF3333"; 
            ctx.fillStyle = "#FF3333";
        }

        // Draw Box
        ctx.lineWidth = 4;
        ctx.strokeRect(xmin, ymin, width, height);

        // Draw Label Tag
        ctx.font = "bold 18px Arial";
        const textWidth = ctx.measureText(label).width;
        ctx.fillRect(xmin, ymin - 28, textWidth + 16, 28);

        // Draw Text
        ctx.fillStyle = "#000000"; 
        ctx.fillText(label, xmin + 8, ymin - 8);
    }
}