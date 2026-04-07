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
YOLO Detection Backend
Uses Ultralytics YOLO for real-time person and hat detection.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from PIL import Image

from .detection import DetectionBackend, DetectionResult

logger = logging.getLogger(__name__)

# Try to import ultralytics, handle gracefully if not installed
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("ultralytics package not installed. YOLO backend will not be available.")


class YoloDetectionBackend(DetectionBackend):
    """YOLO-based detection backend using Ultralytics."""

    def __init__(self, model_name: str = "yolov8n"):
        """
        Args:
            model_name: YOLO model name (yolov8n, yolov8s, yolov11n, etc.)
        """
        super().__init__("yolo")
        self.model_name = model_name
        self.model: Optional[YOLO] = None
        self._init_lock = None

    async def initialize(self) -> None:
        """Initialize the YOLO model."""
        if not YOLO_AVAILABLE:
            raise RuntimeError(
                "ultralytics package not installed. Install with: pip install ultralytics"
            )

        if self._init_lock is None:
            self._init_lock = asyncio.Lock()

        async with self._init_lock:
            if self.model is None:
                logger.info(f"Loading YOLO model: {self.model_name}")
                self.model = YOLO(self.model_name)
                logger.info(f"YOLO model loaded: {self.model_name}")

    async def detect(self, image: Image.Image) -> DetectionResult:
        """
        Detect objects in an image using YOLO.

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

        # Run inference
        results = self.model(
            img_array,
            conf=0.25,  # Confidence threshold
            iou=0.45,   # IoU threshold
            verbose=False,
        )

        boxes = []
        labels = []
        confidences = []

        if results and results[0].boxes is not None:
            for box, cls, conf in zip(
                results[0].boxes.xyxy,  # xyxy format
                results[0].boxes.cls,
                results[0].boxes.conf,
            ):
                x1, y1, x2, y2 = box.tolist()
                label = self.model.names[int(cls)]
                confidence = conf.item()

                # Convert to normalized 0-1000 scale: [ymin, xmin, ymax, xmax]
                height, width = img_array.shape[:2]
                ymin = int(min(y1, y2) / height * 1000)
                xmin = int(min(x1, x2) / width * 1000)
                ymax = int(max(y1, y2) / height * 1000)
                xmax = int(max(x1, x2) / width * 1000)

                boxes.append([ymin, xmin, ymax, xmax])
                # Normalize label for consistent frontend handling
                label_lower = label.lower()
                if "person" in label_lower:
                    # For person detections, use "Person" as label
                    # Hat detection requires custom training - for now just label as Person
                    normalized_label = "Person"
                else:
                    normalized_label = label
                labels.append(normalized_label)
                confidences.append(confidence)

        return DetectionResult(boxes=boxes, labels=labels, confidences=confidences)

    def get_model_info(self) -> Dict[str, Any]:
        """Return model information."""
        return {
            "type": "yolo",
            "model_name": self.model_name,
            "available": YOLO_AVAILABLE,
        }


def get_person_boxes(result: DetectionResult) -> List[Dict[str, Any]]:
    """
    Extract person detections from a DetectionResult.

    Args:
        result: DetectionResult from YOLO

    Returns:
        List of person detections with box, label, and confidence
    """
    persons = []
    for i, label in enumerate(result.labels):
        if "person" in label.lower():
            persons.append({
                "box": result.boxes[i],
                "label": result.labels[i],
                "confidence": result.confidences[i],
            })
    return persons


def get_hat_boxes(result: DetectionResult) -> List[Dict[str, Any]]:
    """
    Extract hat detections from a DetectionResult.

    Args:
        result: DetectionResult from YOLO

    Returns:
        List of hat detections with box, label, and confidence
    """
    hats = []
    for i, label in enumerate(result.labels):
        if "hat" in label.lower():
            hats.append({
                "box": result.boxes[i],
                "label": result.labels[i],
                "confidence": result.confidences[i],
            })
    return hats
