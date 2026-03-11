// ==========================================
// VLM SHOWCASE: STATE-LOCKED CANVAS OVERLAY
// ==========================================

const videoElement = document.getElementById('webcamVideo');
const canvas = document.getElementById('overlayCanvas');
const ctx = canvas.getContext('2d');

// State-lock to prevent frame queuing and lag
let isInferencing = false;

/**
 * Call this function right before you capture and send a WebRTC frame.
 * If it returns false, skip sending the frame.
 */
function shouldSendFrame() {
    if (isInferencing) {
        return false; // The 72B model is still chewing on the last frame
    }
    isInferencing = true; // Lock the state
    return true;
}

/**
 * Call this function the moment the WebSocket/API returns the text response.
 * It handles all the drawing and unlocks the state for the next frame.
 */
function processVlmResponse(vlmTextResponse) {
    try {
        // 1. Sync canvas dimensions to the actual displayed video size
        canvas.width = videoElement.clientWidth;
        canvas.height = videoElement.clientHeight;

        // 2. Clear previous boxes
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 3. Regex to extract Qwen's format: [Label, ymin, xmin, ymax, xmax]
        const regex = /\[([^,\]]+?),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]/g;
        let match;

        // 4. Loop through every detected object and draw
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

            // Draw Label Tag Background
            ctx.font = "bold 18px Arial";
            const textWidth = ctx.measureText(label).width;
            ctx.fillRect(xmin, ymin - 28, textWidth + 16, 28);

            // Draw Label Text
            ctx.fillStyle = "#000000"; 
            ctx.fillText(label, xmin + 8, ymin - 8);
        }
    } catch (error) {
        console.error("Error drawing VLM boxes:", error);
    } finally {
        // 5. UNLOCK THE STATE (Crucial: happens even if there's an error)
        isInferencing = false;
    }
}