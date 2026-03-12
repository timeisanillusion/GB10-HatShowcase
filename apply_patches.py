import os
import re

# --- PATH DETECTION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_HTML = os.path.join(BASE_DIR, "live-vlm-webui", "src", "live_vlm_webui", "static", "index.html")

# YOUR CUSTOM PROMPT (Engineered to defeat First Example Bias and force head-checking)
HAT_PROMPT = 'Analyze the image. Focus on the main person in the foreground and look strictly at their head. Are they wearing a hat? Return ONLY a list of arrays in this exact format: [[xmin, ymin, xmax, ymax, "Person"]] if they do NOT have a hat, or [[xmin, ymin, xmax, ymax, "Person (Hat)"]] if they DO have a hat. Coordinates must be scaled 0 to 1000. If no person is found, return []. Do not include any other text.'

# JavaScript payload
JS_PAYLOAD = r"""
<script id="blackwell-overlay">
(function() {
    console.log("🎮 SHOWCASE READY: Hat Check Demo | S, M, R Tuners Active | Array Parsing | Clamped Coordinates");
    
    const CUSTOM_PROMPT = `__PROMPT_PLACEHOLDER__`;
    let isHatModeActive = true; 
    let wasHatModeActive = true;

    function checkMode(selectedPrompt) {
        if (selectedPrompt === CUSTOM_PROMPT) {
            isHatModeActive = true;
            console.log("Hat Mode: ENABLED");
        } else {
            isHatModeActive = false;
            lastCoords = []; 
            console.log("Hat Mode: DISABLED (Clean up active)");
        }
    }

    function injectPrompt() {
        const promptSelect = document.getElementById('promptPreset');
        const promptInput = document.getElementById('prompt') || document.querySelector('textarea');
        
        if (promptSelect) {
            if (!document.getElementById('hat-showcase-opt')) {
                console.log("Attaching Hat Check Demo to dropdown:", promptSelect.id);
                
                const opt = document.createElement('option');
                opt.id = 'hat-showcase-opt';
                opt.value = CUSTOM_PROMPT;
                opt.textContent = "Hat Check Demo";
                promptSelect.prepend(opt);
                promptSelect.selectedIndex = 0;
                
                if (promptInput) {
                    promptInput.value = opt.value;
                    promptInput.dispatchEvent(new Event('input', { bubbles: true }));
                }

                promptSelect.addEventListener('change', (e) => {
                    checkMode(e.target.value);
                    if (promptInput) {
                        promptInput.value = e.target.value;
                        promptInput.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                });
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
        
        if (!isHatModeActive) return;

        mutations.forEach(m => {
            const txt = m.target.textContent;
            
            // Streaming-safe clear logic
            if (txt && txt.trim() === "[]") {
                lastCoords = [];
            }

            // Regex parsing the clean array: [xmin, ymin, xmax, ymax, "Label"]
            if (txt && txt.includes('[')) {
                const regex = /\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*"([^"]+)"\s*\]/g;
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
        
        if (!isHatModeActive) {
            if (wasHatModeActive && canvas) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                wasHatModeActive = false;
            }
            requestAnimationFrame(render);
            return; 
        }

        wasHatModeActive = true;

        if (video && canvas) {
            if (canvas.width !== video.clientWidth || canvas.height !== video.clientHeight) {
                canvas.width = video.clientWidth;
                canvas.height = video.clientHeight;
            }
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            if (lastCoords.length > 0) {
                lastCoords.forEach(match => {
                    const label = match[5].trim();
                    
                    const vidW = video.videoWidth || 640;
                    const vidH = video.videoHeight || 480;
                    const domW = canvas.width;
                    const domH = canvas.height;

                    const vidRatio = vidW / vidH;
                    const domRatio = domW / domH;

                    let renderW = domW;
                    let renderH = domH;
                    let offsetX = 0;
                    let offsetY = 0;

                    if (vidRatio > domRatio) {
                        renderH = domW / vidRatio;
                        offsetY = (domH - renderH) / 2;
                    } else {
                        renderW = domH * vidRatio;
                        offsetX = (domW - renderW) / 2;
                    }

                    // Map X/Y in correct order, clamp to 1000 max
                    let nx1 = Math.min(1000, parseInt(match[1], 10)) / 1000;
                    let ny1 = Math.min(1000, parseInt(match[2], 10)) / 1000;
                    let nx2 = Math.min(1000, parseInt(match[3], 10)) / 1000;
                    let ny2 = Math.min(1000, parseInt(match[4], 10)) / 1000;

                    if (rotationAngle === 90) {
                        let ox1 = nx1, oy1 = ny1, ox2 = nx2, oy2 = ny2;
                        nx1 = 1 - oy2; ny1 = ox1; nx2 = 1 - oy1; ny2 = ox2;
                    } else if (rotationAngle === 180) {
                        nx1 = 1 - nx1; ny1 = 1 - ny1; nx2 = 1 - nx2; ny2 = 1 - ny2;
                    } else if (rotationAngle === 270) {
                        let ox1 = nx1, oy1 = ny1, ox2 = nx2, oy2 = ny2;
                        nx1 = oy1; ny1 = 1 - ox2; nx2 = oy2; ny2 = 1 - ox1;
                    }

                    if (swapXY) { let tmpX1 = nx1, tmpX2 = nx2; nx1 = ny1; ny1 = tmpX1; nx2 = ny2; ny2 = tmpX2; }
                    if (mirrorX) { nx1 = 1 - nx1; nx2 = 1 - nx2; }

                    let px1 = nx1 * renderW + offsetX;
                    let py1 = ny1 * renderH + offsetY;
                    let px2 = nx2 * renderW + offsetX;
                    let py2 = ny2 * renderH + offsetY;

                    const fx = Math.min(px1, px2);
                    const fy = Math.min(py1, py2);
                    const fw = Math.abs(px2 - px1);
                    const fh = Math.abs(py2 - py1);

                    ctx.strokeStyle = label.includes('Hat') ? "#00FF00" : "#00CCFF";
                    ctx.lineWidth = 4;
                    ctx.strokeRect(fx, fy, fw, fh);
                    
                    ctx.fillStyle = ctx.strokeStyle;
                    ctx.fillRect(fx, fy - 25, label.length * 10 + 20, 25);
                    ctx.fillStyle = "black";
                    ctx.font = "bold 14px sans-serif";
                    ctx.fillText(label.toUpperCase(), fx + 5, fy - 7);
                });
            }
            
            ctx.fillStyle = "rgba(255,255,255,0.7)";
            ctx.font = "12px monospace";
            ctx.fillText(`R:${rotationAngle} S:${swapXY} M:${mirrorX}`, 10, canvas.height - 10);
        }
        requestAnimationFrame(render);
    }
    requestAnimationFrame(render);

    window.addEventListener('keydown', (e) => {
        if (!isHatModeActive) return;
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
    content = re.sub(r'<script id="blackwell-overlay">.*?</script>', '', content, flags=re.DOTALL)
    content = content.replace('</body>', FINAL_JS + '</body>')
    with open(TARGET_HTML, 'w') as f:
        f.write(content)
    print("✅ Success: Prompt engineered to defeat first-example bias.")
