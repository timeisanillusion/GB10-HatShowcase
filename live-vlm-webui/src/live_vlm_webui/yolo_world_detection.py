# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
YOLO-World Detection Backend
Uses Ultralytics YOLO-World for open-vocabulary detection with text prompts.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from PIL import Image

from .detection import DetectionBackend, DetectionResult

logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("ultralytics package not installed. YOLO-World backend will not be available.")


class YoloWorldDetectionBackend(DetectionBackend):
    """
    YOLO-World detection backend.

    YOLO-World is a YOLO model fine-tuned on open-vocabulary detection.
    It can detect objects based on text prompts rather than predefined classes.
    """

    def __init__(self, model_name: str = "yolo-world-latest", prompt: str = "person, hat"):
        """
        Args:
            model_name: YOLO-World model name
            prompt: Comma-separated list of classes to detect
        """
        super().__init__("yolo_world")
        self.model_name = model_name
        self.prompt = prompt
        self.model: Optional[YOLO] = None
        self._init_lock = None
        self._current_classes = prompt.split(",")

    async def initialize(self) -> None:
        """Initialize the YOLO-World model."""
        if not YOLO_AVAILABLE:
            raise RuntimeError(
                "ultralytics package not installed. Install with: pip install ultralytics"
            )

        if self._init_lock is None:
            self._init_lock = asyncio.Lock()

        async with self._init_lock:
            if self.model is None:
                logger.info(f"Loading YOLO-World model: {self.model_name} (CPU mode — avoids VRAM conflict with Ollama)")
                self.model = YOLO(self.model_name)
                self.model.to("cpu")
                logger.info(f"YOLO-World model loaded on CPU: {self.model_name}")

                # Set classes for detection
                self.set_classes(self.prompt)

    def set_classes(self, prompt: str) -> None:
        """
        Update the detection classes based on a text prompt.

        This updates both the internal class list AND calls model.set_classes()
        on the underlying ultralytics YOLO-World model so it actually uses the
        custom vocabulary at inference time.

        Args:
            prompt: Comma-separated list of classes (e.g., "person, hat, bag")
        """
        self.prompt = prompt
        self._current_classes = [c.strip() for c in prompt.split(",")]
        logger.info(f"YOLO-World classes updated: {self._current_classes}")

        # Tell the ultralytics model which vocabulary to use.
        # Without this call YOLO-World falls back to COCO classes and will
        # never detect open-vocabulary items like "hat".
        if self.model is not None:
            self.model.set_classes(self._current_classes)
            logger.info(f"YOLO-World model.set_classes() called: {self._current_classes}")

    async def detect(self, image: Image.Image) -> DetectionResult:
        """
        Detect objects in an image using YOLO-World.

        Args:
            image: PIL Image to analyze

        Returns:
            DetectionResult with boxes, labels, and confidences
        """
        if self.model is None:
            await self.initialize()

        # Convert PIL Image to numpy for YOLO
        import numpy as np
        img_array = np.array(image)

        # Run inference on CPU to avoid VRAM conflict with Ollama LLMs
        results = self.model(
            img_array,
            conf=0.25,  # Confidence threshold
            iou=0.45,   # IoU threshold
            classes=None,  # Let model use its vocabulary
            device="cpu",
            verbose=False,
        )

        boxes = []
        labels = []
        confidences = []

        if results and results[0].boxes is not None:
            for box, cls, conf in zip(
                results[0].boxes.xyxy,
                results[0].boxes.cls,
                results[0].boxes.conf,
            ):
                x1, y1, x2, y2 = box.tolist()
                label = self.model.names[int(cls)]
                confidence = conf.item()

                # Filter to only classes in our prompt
                if label.lower() not in [c.lower() for c in self._current_classes]:
                    continue

                # Convert to normalized 0-1000 scale: [ymin, xmin, ymax, xmax]
                height, width = img_array.shape[:2]
                ymin = int(min(y1, y2) / height * 1000)
                xmin = int(min(x1, x2) / width * 1000)
                ymax = int(max(y1, y2) / height * 1000)
                xmax = int(max(x1, x2) / width * 1000)

                boxes.append([ymin, xmin, ymax, xmax])
                # Normalize label for consistent frontend handling
                label_lower = label.lower()
                if "wearing" in label_lower or "wear" in label_lower:
                    # "person wearing hat" -> "Person (Hat)"
                    normalized_label = "Person (Hat)"
                elif "not" in label_lower and "hat" in label_lower:
                    # "person not wearing hat" -> "Person"
                    normalized_label = "Person"
                elif "hat" in label_lower:
                    # Just "hat" -> use as-is but add context
                    normalized_label = label
                else:
                    normalized_label = label
                labels.append(normalized_label)
                confidences.append(confidence)

        return DetectionResult(boxes=boxes, labels=labels, confidences=confidences)

    def get_model_info(self) -> Dict[str, Any]:
        """Return model information."""
        return {
            "type": "yolo_world",
            "model_name": self.model_name,
            "prompt": self.prompt,
            "classes": self._current_classes,
            "available": YOLO_AVAILABLE,
        }
