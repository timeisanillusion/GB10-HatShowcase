import os
import sys
import re

# ==========================================
# CONFIGURATION
# Update these paths based on the exact structure of the live-vlm-webui repo
# ==========================================
TARGET_HTML_FILE = "live-vlm-webui/templates/index.html" 
TARGET_JS_FILE = "live-vlm-webui/static/js/main.js"

def patch_html():
    if not os.path.exists(TARGET_HTML_FILE):
        print(f"❌ Error: Could not find HTML file at {TARGET_HTML_FILE}")
        return False
        
    with open(TARGET_HTML_FILE, 'r', encoding='utf-8') as file:
        html_content = file.read()

    # Regex to find the video tag with id="webcamVideo", capturing the whole tag
    # Uses \s* to account for potential formatting changes in the source code
    video_tag_pattern = r'(<video[^>]*id=["\']webcamVideo["\'][^>]*>.*?</video>)'
    
    if not re.search(video_tag_pattern, html_content, re.IGNORECASE | re.DOTALL):
        print("⚠️ Warning: Original video tag not found. It may have already been patched or the ID changed.")
        return False

    # The \g<1> safely injects the exact <video> tag we just captured
    replacement = r"""
<div id="videoContainer" style="position: relative; display: inline-block;">
    \g<1>
    <canvas id="overlayCanvas" style="position: absolute; top: 0; left: 0; pointer-events: none; z-index: 10;"></canvas>
</div>
"""
    
    patched_html = re.sub(video_tag_pattern, replacement, html_content, flags=re.IGNORECASE | re.DOTALL)

    with open(TARGET_HTML_FILE, 'w', encoding='utf-8') as file:
        file.write(patched_html)
        
    print(f"✅ Successfully patched HTML using regex: {TARGET_HTML_FILE}")
    return True

def patch_js():
    if not os.path.exists(TARGET_JS_FILE):
        print(f"❌ Error: Could not find JS file at {TARGET_JS_FILE}")
        return False
        
    if not os.path.exists("canvas_overlay.js"):
        print("❌ Error: canvas_overlay.js not found in current directory.")
        return False

    with open("canvas_overlay.js", 'r', encoding='utf-8') as patch_file:
        patch_content = patch_file.read()

    with open(TARGET_JS_FILE, 'r', encoding='utf-8') as file:
        js_content = file.read()

    # Prevent double-patching if the script is run twice
    if "let isInferencing = false;" in js_content:
        print("⚠️ Warning: JS file appears to already be patched. Skipping.")
        return True

    # Append the patch content to the bottom of the target JS file
    with open(TARGET_JS_FILE, 'a', encoding='utf-8') as file:
        file.write("\n\n// --- VLM SHOWCASE OVERLAY PATCH ---\n")
        file.write(patch_content)

    print(f"✅ Successfully appended logic to JS: {TARGET_JS_FILE}")
    return True

if __name__ == "__main__":
    print("Applying VLM Showcase patches...")
    html_success = patch_html()
    js_success = patch_js()
    
    if html_success and js_success:
        print("🎉 All patches applied successfully!")
    else:
        print("⚠️ Patching completed with errors. Please check the logs above.")
        sys.exit(1)