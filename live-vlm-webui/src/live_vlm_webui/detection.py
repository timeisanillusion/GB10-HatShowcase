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
Detection Modules
Pluggable object detection backends for real-time video analysis.

Supported backends:
- yolo: Ultralytics YOLO (v8, v11) with pre-trained models
- yolo_world: YOLO-World for open-vocabulary detection with text prompts
- vlm: Original VLM-based detection (fallback)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from PIL import Image

logger = logging.getLogger(__name__)


class DetectionResult:
    """Container for detection results."""

    def __init__(self, boxes: List[List[float]], labels: List[str], confidences: List[float]):
        """
        Args:
            boxes: List of [ymin, xmin, ymax, xmax] normalized coordinates (0-1000 scale)
            labels: List of object class labels
            confidences: List of confidence scores
        """
        self.boxes = boxes
        self.labels = labels
        self.confidences = confidences

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "boxes": self.boxes,
            "labels": self.labels,
            "confidences": self.confidences,
        }


class DetectionBackend(ABC):
    """Abstract base class for detection backends."""

    def __init__(self, name: str):
        self.name = name
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the detection model."""
        pass

    @abstractmethod
    async def detect(self, image: Image.Image) -> DetectionResult:
        """
        Detect objects in an image.

        Args:
            image: PIL Image to analyze

        Returns:
            DetectionResult with boxes, labels, and confidences
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Return model information."""
        pass

    async def detect_person_with_hat(
        self, image: Image.Image
    ) -> Optional[List[List[float]]]:
        """
        Detect a person and determine if they're wearing a hat.

        Returns:
            [ymin, xmin, ymax, xmax, label] or None if no person found
        """
        result = await self.detect(image)

        # Find person detections
        person_indices = [i for i, label in enumerate(result.labels) if "person" in label.lower()]

        if not person_indices:
            return None

        # Return the first person detection with appropriate label
        idx = person_indices[0]
        ymin, xmin, ymax, xmax = result.boxes[idx]
        label = result.labels[idx]

        return [ymin, xmin, ymax, xmax, label]


class DetectionBackendRegistry:
    """Registry for detection backends."""

    _backends: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a detection backend."""

        def decorator(backend_class: type) -> type:
            cls._backends[name] = backend_class
            logger.info(f"Registered detection backend: {name}")
            return backend_class

        return decorator

    @classmethod
    def get_backend(cls, name: str) -> DetectionBackend:
        """Get an instance of a registered backend."""
        backend_class = cls._backends.get(name)
        if backend_class is None:
            raise ValueError(f"Unknown detection backend: {name}. Available: {list(cls._backends.keys())}")
        return backend_class()

    @classmethod
    def list_backends(cls) -> List[str]:
        """List available backend names."""
        return list(cls._backends.keys())


def create_detection_backend(
    backend_type: str,
    model_name: Optional[str] = None,
    prompt: Optional[str] = None,
) -> DetectionBackend:
    """
    Factory function to create detection backends.

    Args:
        backend_type: One of 'yolo', 'yolo_world', 'vlm'
        model_name: Model name for YOLO (e.g., 'yolov8n', 'yolov11n')
        prompt: Prompt for YOLO-World detection

    Returns:
        Configured DetectionBackend instance
    """
    if backend_type == "yolo":
        from .yolo_detection import YoloDetectionBackend

        return YoloDetectionBackend(model_name=model_name or "yolov8n")

    elif backend_type == "yolo_world":
        from .yolo_world_detection import YoloWorldDetectionBackend

        return YoloWorldDetectionBackend(model_name=model_name or "yolo-world-latest", prompt=prompt or "person hat")

    elif backend_type == "vlm":
        from .vlm_detection import VlmDetectionBackend

        return VlmDetectionBackend()

    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


# Import backends after registry is defined (handled conditionally to avoid import errors)
try:
    from .yolo_detection import YoloDetectionBackend
except ImportError:
    pass
try:
    from .yolo_world_detection import YoloWorldDetectionBackend
except ImportError:
    pass
try:
    from .vlm_detection import VlmDetectionBackend
except ImportError:
    pass
