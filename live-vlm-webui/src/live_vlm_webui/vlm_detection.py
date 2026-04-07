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
VLM Detection Backend
Fallback to original VLM-based detection with text parsing.
"""

import asyncio
import logging
import re
from typing import Optional, List, Dict, Any
from PIL import Image

from .detection import DetectionBackend, DetectionResult

logger = logging.getLogger(__name__)


class VlmDetectionBackend(DetectionBackend):
    """
    VLM-based detection backend.

    This is the original detection method that sends images to a VLM
    and parses the response for bounding box coordinates.
    """

    def __init__(
        self,
        default_prompt: str = "Describe what you see in this image in one sentence.",
    ):
        super().__init__("vlm")
        self.default_prompt = default_prompt
        self._last_response = ""

    async def initialize(self) -> None:
        """Initialize the VLM backend (no-op for text parsing)."""
        logger.info("VLM detection backend initialized (text parsing mode)")

    async def detect(self, image: Image.Image) -> DetectionResult:
        """
        Detect objects using VLM response parsing.

        Args:
            image: PIL Image to analyze

        Returns:
            DetectionResult (empty until VLM provides response)
        """
        # This backend doesn't actually detect - it waits for VLM response
        # The actual detection happens in the VLM service
        return DetectionResult(boxes=[], labels=[], confidences=[])

    def parse_response(self, text: str) -> DetectionResult:
        """
        Parse VLM response text to extract bounding boxes.

        Expected format: [[ymin, xmin, ymax, xmax, "Label"], ...]

        Args:
            text: VLM response text

        Returns:
            DetectionResult with parsed boxes and labels
        """
        boxes = []
        labels = []

        # Regex pattern for array format: [[ymin, xmin, ymax, xmax, "Label"]]
        pattern = r"\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*\"([^\"]+)\"\s*\]"

        matches = re.findall(pattern, text)
        for match in matches:
            ymin, xmin, ymax, xmax, label = match
            boxes.append([int(ymin), int(xmin), int(ymax), int(xmax)])
            labels.append(label.strip())

        logger.info(f"Parsed {len(boxes)} detections from VLM response")

        return DetectionResult(
            boxes=boxes,
            labels=labels,
            confidences=[1.0] * len(boxes),  # VLM doesn't provide confidence
        )

    def get_model_info(self) -> Dict[str, Any]:
        """Return model information."""
        return {
            "type": "vlm",
            "mode": "text_parsing",
            "default_prompt": self.default_prompt,
        }

    def update_last_response(self, response: str) -> DetectionResult:
        """
        Update the last VLM response and parse it.

        Args:
            response: VLM response text

        Returns:
            Parsed DetectionResult
        """
        self._last_response = response
        return self.parse_response(response)

    def get_last_response(self) -> str:
        """Get the last parsed response."""
        return self._last_response
