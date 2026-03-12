import os
import re

# --- PATH DETECTION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_HTML = os.path.join(BASE_DIR, "live-vlm-webui", "src", "live_vlm_webui", "static", "index.html")

# YOUR CUSTOM PROMPT (Updated to request JSON and remove the 1000 normalization limit)
HAT_PROMPT = 'Analyze the image. Locate every person and check if they are wearing a hat. Return ONLY a list of JSON objects in this exact format: {"bbox_2d": [xmin, ymin, xmax, ymax], "label": "Person (Hat)"} or {"bbox_2d": [xmin, ymin, xmax, ymax], "label": "Person"}. Do not include any other text.'

# JavaScript payload with standard brackets
JS_PAYLOAD = r"""
<script id="blackwell-overlay">
(function() {
    console.log("🎮 SHOWCASE READY: Hat Prompt Injected | S, M, R Tuners Active");
    
    const CUSTOM_PROMPT = `__PROMPT_PLACEHOLDER__`;

    function injectPrompt() {
        const promptSelect = document.getElementById('prompt-select') || document.querySelector('select');
        const promptInput = document.getElementById('prompt-input') || document.querySelector('textarea');
        
        if (promptSelect) {
            if (!document.getElementById('hat-showcase-opt')) {
                const opt = document.createElement('option');
                opt.id = 'hat-showcase-opt';
                opt.value = CUSTOM_PROMPT;
                opt.textContent = "🎩 Hat Showcase (Ottawa Demo)";
                promptSelect.prepend(opt);
                promptSelect.selectedIndex = 0;
                
                if (promptInput) {
                    promptInput.value = opt.value;
                    promptInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
        }
    }

    let lastCoords = [];
    let swapXY = false;
    let mirrorX = false;
    let rotationAngle = 0; 

    function setupCanvas() {
        const video = document.querySelector('video');
        if (!video) return null;
        let canvas = document.getElementById('edgeCanvas');
        if (!canvas) {
            const wrapper = document.createElement('div');
            wrapper.id = 'v-wrapper';
            wrapper.style.cssText = "position:relative; display:inline-block; line-height:0;";
            video.parentNode.insertBefore(wrapper, video);
            wrapper.appendChild(video);
            canvas = document.createElement('canvas');
            canvas.id = 'edgeCanvas';
            canvas.style.cssText = "position:absolute; top:0; left:0; pointer-events:none; z-index:10;";
            wrapper.appendChild(canvas);
        }
        return canvas;
    }

    const observer = new MutationObserver((mutations) => {
        injectPrompt(); 
        mutations.forEach(m => {
            const txt = m.target.textContent;
            // Now checking for the JSON key instead of square brackets
            if (txt && txt.includes('bbox_2d')) {
                const regex = /{"bbox_2d":\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\s*,\s*"label":\s*"([^"]+)"}/g;
                let match;
                const found = [];
                regex.lastIndex = 0;
                while ((match = regex.exec(txt)) !== null) { found.push(match); }
                if (found.length > 0) lastCoords = found;
            }
        });
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });

    function render() {
        const video = document.querySelector('video');
        const canvas = setupCanvas();
        if (video && canvas && lastCoords.length > 0) {
            if (canvas.width !== video.clientWidth || canvas.height !== video.clientHeight) {
                canvas.width = video.clientWidth;
                canvas.height = video.clientHeight;
            }
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            lastCoords.forEach(match => {
                // Updated variable mapping to match the JSON Regex capture groups
                const label = match[5].trim();
                
                // Fetch the intrinsic resolution of the webcam frame (fallback to 640x480)
                const vidW = video.videoWidth || 640;
                const vidH = video.videoHeight || 480;

                // Divide by the actual video dimensions instead of 1000
                let x1 = parseInt(match[1], 10) / vidW;
                let y1 = parseInt(match[2], 10) / vidH;
                let x2 = parseInt(match[3], 10) / vidW;
                let y2 = parseInt(match[4], 10) / vidH;

                if (rotationAngle === 90) {
                    let ox1 = x1, oy1 = y1, ox2 = x2, oy2 = y2;
                    x1 = 1 - oy2; y1 = ox1; x2 = 1 - oy1; y2 = ox2;
                } else if (rotationAngle === 180) {
                    x1 = 1 - x1; y1 = 1 - y1; x2 = 1 - x2; y2 = 1 - y2;
                } else if (rotationAngle === 270) {
                    let ox1 = x1, oy1 = y1, ox2 = x2, oy2 = y2;
                    x1 = oy1; y1 = 1 - ox2; x2 = oy2; y2 = 1 - ox1;
                }

                if (swapXY) { let tmpX1 = x1, tmpX2 = x2; x1 = y1; y1 = tmpX1; x2 = y2; y2 = tmpX2; }
                if (mirrorX) { x1 = 1 - x1; x2 = 1 - x2; }

                const fx = Math.min(x1, x2) * canvas.width;
                const fy = Math.min(y1, y2) * canvas.height;
                const fw = Math.abs(x2 - x1) * canvas.width;
                const fh = Math.abs(y2 - y1) * canvas.height;

                ctx.strokeStyle = label.includes('Hat') ? "#00FF00" : "#00CCFF";
                ctx.lineWidth = 4;
                ctx.strokeRect(fx, fy, fw, fh);
                
                ctx.fillStyle = ctx.strokeStyle;
                ctx.fillRect(fx, fy - 25, label.length * 10 + 20, 25);
                ctx.fillStyle = "black";
                ctx.font = "bold 14px sans-serif";
                ctx.fillText(label.toUpperCase(), fx + 5, fy - 7);
            });
            
            ctx.fillStyle = "rgba(255,255,255,0.7)";
            ctx.font = "12px monospace";
            ctx.fillText(`R:${rotationAngle} S:${swapXY} M:${mirrorX}`, 10, canvas.height - 10);
        }
        requestAnimationFrame(render);
    }
    requestAnimationFrame(render);

    window.addEventListener('keydown', (e) => {
        const key = e.key.toLowerCase();
        if (key === 's') swapXY = !swapXY;
        if (key === 'm') mirrorX = !mirrorX;
        if (key === 'r') rotationAngle = (rotationAngle + 90) % 360;
    });
})();
</script>
"""

# Inject the prompt into the placeholder
FINAL_JS = JS_PAYLOAD.replace("__PROMPT_PLACEHOLDER__", HAT_PROMPT)

if os.path.exists(TARGET_HTML):
    with open(TARGET_HTML, 'r') as f:
        content = f.read()
    # Clean old scripts
    content = re.sub(r'<script id="blackwell-overlay">.*?</script>', '', content, flags=re.DOTALL)
    # Inject new script
    content = content.replace('</body>', FINAL_JS + '</body>')
    with open(TARGET_HTML, 'w') as f:
        f.write(content)
    print("✅ Success: Prompt injected and tuner active. No Syntax Errors.")
