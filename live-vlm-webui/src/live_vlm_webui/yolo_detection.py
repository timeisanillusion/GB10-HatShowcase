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


def associate_hats_with_persons(result: DetectionResult) -> DetectionResult:
    """
    Post-process a YOLO-World DetectionResult (containing 'person' and 'hat' detections)
    to produce a person-only result where each person is labelled with their hat status.

    Algorithm:
      - Separate detections into person boxes and hat boxes.
      - For each person, define a "head zone" as the top 30 % of the bounding box.
      - A hat is considered worn by a person when at least 30 % of the hat box area
        overlaps with that person's head zone.
      - The output contains only person boxes, labelled "Hat" (wearing) or "No Hat" (not wearing).

    Args:
        result: DetectionResult from YOLO-World with mixed person/hat detections.

    Returns:
        DetectionResult with one entry per person, labelled "Hat" or "No Hat".
    """
    persons: List[Dict[str, Any]] = []
    hats: List[Dict[str, Any]] = []

    HAT_KEYWORDS = {"hat", "cap", "helmet", "beanie", "beret", "hardhat", "hard hat"}

    for i, label in enumerate(result.labels):
        lower = label.lower()
        if lower == "person":
            persons.append({"box": result.boxes[i], "conf": result.confidences[i]})
        elif any(kw in lower for kw in HAT_KEYWORDS):
            hats.append({"box": result.boxes[i], "conf": result.confidences[i]})

    new_boxes: List[List[float]] = []
    new_labels: List[str] = []
    new_confidences: List[float] = []

    for person in persons:
        ymin, xmin, ymax, xmax = person["box"]
        person_height = ymax - ymin

        # Head zone = top 30 % of the person bounding box (in 0-1000 scale)
        head_zone_ymax = ymin + person_height * 0.30

        has_hat = False
        for hat in hats:
            hymin, hxmin, hymax, hxmax = hat["box"]

            # Intersection of hat box with head zone
            inter_ymin = max(ymin, hymin)
            inter_ymax = min(head_zone_ymax, hymax)
            inter_xmin = max(xmin, hxmin)
            inter_xmax = min(xmax, hxmax)

            inter_h = inter_ymax - inter_ymin
            inter_w = inter_xmax - inter_xmin

            if inter_h > 0 and inter_w > 0:
                hat_area = (hymax - hymin) * (hxmax - hxmin)
                overlap_area = inter_h * inter_w
                if hat_area > 0 and (overlap_area / hat_area) >= 0.30:
                    has_hat = True
                    break

        new_boxes.append(person["box"])
        new_labels.append("Hat" if has_hat else "No Hat")
        new_confidences.append(person["conf"])

    return DetectionResult(boxes=new_boxes, labels=new_labels, confidences=new_confidences)
