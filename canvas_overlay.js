// ==========================================
// VLM SHOWCASE: AUTO-DETECTING CANVAS OVERLAY
// ==========================================

const videoElement = document.getElementById('webcamVideo') || document.querySelector('video');
const canvas = document.getElementById('overlayCanvas');
let ctx = null;
let isInferencing = false;

// 1. Core Drawing Logic
function processVlmResponse(vlmTextResponse) {
    if (!canvas || !videoElement) return;
    if (!ctx) ctx = canvas.getContext('2d');

    try {
        // Match canvas size to the video element's display size
        canvas.width = videoElement.clientWidth;
        canvas.height = videoElement.clientHeight;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Regex for Qwen Native JSON format: {"bbox_2d": [xmin, ymin, xmax, ymax], "label": "..."}
        const regex = /{"bbox_2d":\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\],\s*"label":\s*"([^"]+)"}/g;
        let match;
        let foundDetection = false;

        while ((match = regex.exec(vlmTextResponse)) !== null) {
            foundDetection = true;
            
            // Normalize 0-1000 coordinates to pixel values
            // Now correctly mapped to standard xmin, ymin, xmax, ymax
            const xmin = (parseInt(match[1], 10) / 1000) * canvas.width;
            const ymin = (parseInt(match[2], 10) / 1000) * canvas.height;
            const xmax = (parseInt(match[3], 10) / 1000) * canvas.width;
            const ymax = (parseInt(match[4], 10) / 1000) * canvas.height;
            const label = match[5].trim();

            const width = xmax - xmin;
            const height = ymax - ymin;

            // Styling
            ctx.strokeStyle = label.toLowerCase().includes("hat") ? "#00FF00" : "#FF3333"; 
            ctx.fillStyle = ctx.strokeStyle;
            ctx.lineWidth = 4;

            // Draw Box and Label
            ctx.strokeRect(xmin, ymin, width, height);
            ctx.font = "bold 18px Arial";
            const textWidth = ctx.measureText(label).width;
            ctx.fillRect(xmin, ymin - 28, textWidth + 16, 28);
            ctx.fillStyle = "#000000"; 
            ctx.fillText(label, xmin + 8, ymin - 8);
        }
    } catch (error) {
        console.error("Error drawing VLM boxes:", error);
    } finally {
        isInferencing = false;
    }
}

// 2. The DOM Mutation Observer (The Magic Hook)
const observer = new MutationObserver((mutations) => {
    for (let mutation of mutations) {
        const nodeText = mutation.target.textContent || "";
        // Check for the new JSON key instead of square brackets
        if (nodeText.includes("bbox_2d")) {
            // Quick check for the JSON coordinate pattern
            if (/{"bbox_2d":\s*\[\d+,\s*\d+,\s*\d+,\s*\d+\],\s*"label":\s*"[^"]+"}/.test(nodeText)) {
                processVlmResponse(nodeText);
            }
        }
    }
});

// Start observing
window.addEventListener('load', () => {
    observer.observe(document.body, { 
        childList: true, 
        subtree: true, 
        characterData: true 
    });
    console.log("VLM Showcase Overlay active.");
});
