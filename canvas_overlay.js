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

        // Regex for Qwen format: [Label, ymin, xmin, ymax, xmax]
        const regex = /\[([^,\]]+?),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]/g;
        let match;
        let foundDetection = false;

        while ((match = regex.exec(vlmTextResponse)) !== null) {
            foundDetection = true;
            const label = match[1].trim();
            
            // Normalize 0-1000 coordinates to pixel values
            const ymin = (parseInt(match[2], 10) / 1000) * canvas.height;
            const xmin = (parseInt(match[3], 10) / 1000) * canvas.width;
            const ymax = (parseInt(match[4], 10) / 1000) * canvas.height;
            const xmax = (parseInt(match[5], 10) / 1000) * canvas.width;

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
        if (nodeText.includes("[") && nodeText.includes("]")) {
            // If the text matches the coordinate pattern
            if (/\[.*?,\s*\d+,\s*\d+,\s*\d+,\s*\d+\]/.test(nodeText)) {
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
