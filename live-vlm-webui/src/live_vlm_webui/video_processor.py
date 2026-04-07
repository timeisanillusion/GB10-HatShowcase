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
Video Track Processor
Handles video frames, sends to VLM for analysis,
and passes through original frame with detection overlay options
"""

import asyncio
import cv2
import numpy as np
from PIL import Image
from aiortc import VideoStreamTrack
from aiortc.mediastreams import MediaStreamError
from typing import Optional
import logging
import time
import av

from .vlm_service import VLMService
from .detection import DetectionBackend, DetectionResult

# Enable swscaler warnings to track hardware acceleration status
# TODO: Implement hardware-accelerated color space conversion on Jetson using NVMM/VPI
av.logging.set_level(av.logging.WARNING)

logger = logging.getLogger(__name__)


class VideoProcessorTrack(VideoStreamTrack):
    """
    Video track that receives frames, sends them to VLM for analysis,
    and passes the original frame through (zero-copy)
    """

    # Class variable for frame processing interval (can be updated dynamically)
    process_every_n_frames = 30
    # Max allowed latency before dropping frames (in seconds, 0 = disabled)
    max_frame_latency = 0.0

    def __init__(self, track: VideoStreamTrack, vlm_service: VLMService, text_callback=None, detection_backend: Optional[DetectionBackend] = None):
        super().__init__()
        self.track = track
        self.vlm_service = vlm_service
        self.text_callback = text_callback  # Callback to send text updates
        # Store detection_backend as a mutable reference (dict) so it can be updated dynamically
        self._detection_backend_ref = {"backend": detection_backend}
        self.last_frame: Optional[np.ndarray] = None
        self.frame_count = 0
        self.dropped_frames = 0
        self.first_frame_pts = None  # Track first frame PTS to calculate relative time
        self.first_frame_time = None  # Wall clock time of first frame
        self.frame_time_base = None  # Time base for PTS conversion (e.g., 1/90000)
        self.last_detection_result: Optional[DetectionResult] = None
        self.last_detection_time = 0  # Track when detection was last run

    @property
    def detection_backend(self) -> Optional[DetectionBackend]:
        """Get current detection backend (dynamic lookup)."""
        return self._detection_backend_ref.get("backend")

    @detection_backend.setter
    def detection_backend(self, value: Optional[DetectionBackend]):
        """Set detection backend dynamically."""
        self._detection_backend_ref["backend"] = value

    async def recv(self):
        """
        Receive frame from input track and process it.
        Sends frames to VLM and YOLO (if configured) but passes original frame through.
        """
        try:
            # Get frame from incoming track
            frame = await self.track.recv()

            # Initialize timing on first frame
            if self.first_frame_pts is None and frame.pts is not None:
                self.first_frame_pts = frame.pts
                self.first_frame_time = time.time()
                # Store time_base for PTS conversion (e.g., 1/90000 for 90kHz clock)
                self.frame_time_base = float(frame.time_base)
                logger.info(
                    f"Latency tracking initialized: PTS={frame.pts}, time_base={frame.time_base} ({self.frame_time_base}s per tick)"
                )

            # Calculate actual frame age (latency) using PTS and time_base
            # Note: Some streams (like RTSP) may not have PTS set, so skip latency checks
            frame_latency = 0.0
            if frame.pts is not None and self.first_frame_pts is not None:
                # PTS is in time_base units, convert to seconds: pts * time_base
                frame_time_offset = (frame.pts - self.first_frame_pts) * self.frame_time_base
                expected_wall_time = self.first_frame_time + frame_time_offset
                current_time = time.time()
                frame_latency = current_time - expected_wall_time

            # Check for accumulated latency and drop old frames if needed (only if max_latency > 0)
            max_latency = self.__class__.max_frame_latency
            if max_latency > 0 and frame_latency > max_latency and frame.pts is not None:
                logger.warning(
                    f"Frame is {frame_latency:.2f}s behind, dropping frames (threshold: {max_latency}s)"
                )

                # Drop frames until we get a fresh one
                dropped_count = 0
                while frame_latency > max_latency:
                    self.dropped_frames += 1
                    dropped_count += 1

                    # Get next frame
                    frame = await self.track.recv()

                    # Recalculate latency for new frame (using time_base for correct conversion)
                    if frame.pts is not None and self.first_frame_pts is not None:
                        frame_time_offset = (
                            frame.pts - self.first_frame_pts
                        ) * self.frame_time_base
                        expected_wall_time = self.first_frame_time + frame_time_offset
                        frame_latency = time.time() - expected_wall_time
                    else:
                        # If PTS becomes unavailable, stop dropping frames
                        break

                    # Prevent infinite loop
                    if dropped_count > 100:
                        logger.error(
                            f"Dropped {dropped_count} frames, but still behind. Resetting timing."
                        )
                        if frame.pts is not None:
                            self.first_frame_pts = frame.pts
                            self.first_frame_time = time.time()
                            self.frame_time_base = float(frame.time_base)
                        break

                if dropped_count > 0:
                    logger.info(
                        f"Dropped {dropped_count} frames, now at {frame_latency:.2f}s latency"
                    )

            # Increment frame counter
            self.frame_count += 1

            # Only convert to numpy when needed (for VLM processing or first frame)
            # This avoids expensive CPU color conversion on every frame
            interval = self.__class__.process_every_n_frames
            need_conversion = (self.frame_count % interval == 0) or (self.frame_count == 1)

            if need_conversion:
                t1 = time.time()
                # Convert to numpy array (expensive: YUV→BGR color conversion on CPU)
                img = frame.to_ndarray(format="bgr24")
                t2 = time.time()
                self.last_frame = img.copy()
                t3 = time.time()

                # Log timing every 100 frames to identify bottlenecks
                if self.frame_count % 100 == 0:
                    logger.info(
                        f"Frame conversion times: to_ndarray={1000*(t2-t1):.1f}ms, copy={1000*(t3-t2):.1f}ms"
                    )

                # Log first frame
                if self.frame_count == 1:
                    logger.info(f"First frame received: {img.shape}")

                # Send frame to VLM for analysis (async, non-blocking)
                # Only if YOLO detection is not available
                if self.frame_count % interval == 0:
                    # Convert to PIL Image for VLM
                    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

                    # Perform YOLO detection if backend is available (faster than VLM)
                    if self.detection_backend is not None:
                        detection_task = asyncio.create_task(self._run_yolo_detection(pil_img))
                        logger.debug(f"Frame {self.frame_count}: Running YOLO detection")
                    else:
                        detection_task = None

                    # Skip VLM processing if YOLO detection is active
                    if detection_task is None:
                        # Fire and forget - don't wait for result
                        asyncio.create_task(self.vlm_service.process_frame(pil_img))
                        logger.info(f"Frame {self.frame_count}: Sending to VLM (interval={interval})")
                    else:
                        logger.info(f"Frame {self.frame_count}: YOLO detection active, skipping VLM processing")

                    # Update detection result if YOLO is available
                    if detection_task:
                        try:
                            result = await detection_task
                            self.last_detection_result = result
                            self.last_detection_time = time.time()
                            logger.debug(f"Frame {self.frame_count}: YOLO detected {len(result.labels)} objects")
                        except Exception as e:
                            logger.warning(f"YOLO detection failed: {e}")

            # Get current response (may be old if VLM is still processing)
            response, is_processing = self.vlm_service.get_current_response()

            # Get metrics
            metrics = self.vlm_service.get_metrics()

            # Send text update via callback (for WebSocket)
            if self.text_callback:
                # Skip sending response if YOLO detection is active and no VLM processing
                # Only send detection result if it's recent
                if self.detection_backend is not None and self.last_detection_result is not None and time.time() - self.last_detection_time < 2.0:
                    # Send detection result without VLM response
                    self.text_callback("", metrics, self.last_detection_result)
                elif not is_processing:
                    # Only send response if VLM is not processing
                    self.text_callback(response, metrics)
            else:
                # Fallback: send detection result if available
                if self.detection_backend is not None and self.last_detection_result is not None:
                    self.text_callback("", {}, self.last_detection_result)

            # Return original frame directly - zero-copy passthrough!
            # This avoids expensive BGR→YUV conversion
            return frame

        except MediaStreamError:
            # Track ended (user stopped, tab closed, etc.) — normal, not an error
            logger.debug("Video track ended")
            raise
        except Exception as e:
            logger.error(f"Error processing frame: {e}", exc_info=True)
            raise

    async def _run_yolo_detection(self, image: Image.Image) -> DetectionResult:
        """
        Run YOLO detection on an image.

        Args:
            image: PIL Image to analyze

        Returns:
            DetectionResult from YOLO
        """
        if self.detection_backend is None:
            return DetectionResult(boxes=[], labels=[], confidences=[])
        return await self.detection_backend.detect(image)

    def get_last_detection(self) -> Optional[DetectionResult]:
        """Get the last YOLO detection result."""
        return self.last_detection_result

    def _add_text_overlay(self, img: np.ndarray, text: str, status: str = "") -> np.ndarray:
        """
        Add text overlay to image

        Args:
            img: Input image (BGR format)
            text: Text to overlay (VLM response)
            status: Optional status text

        Returns:
            Image with text overlay
        """
        img_copy = img.copy()
        height, width = img_copy.shape[:2]

        # Prepare text
        full_text = f"{text} {status}" if status else text

        # Text wrapping - split long captions
        max_chars_per_line = 60
        words = full_text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= max_chars_per_line:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(" ".join(current_line))

        # Text properties
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        font_thickness = 2
        text_color = (255, 255, 255)  # White
        bg_color = (0, 0, 0)  # Black background
        padding = 10
        line_height = 30

        # Calculate total height needed
        total_text_height = len(lines) * line_height + 2 * padding

        # Create semi-transparent overlay at bottom
        overlay = img_copy.copy()
        cv2.rectangle(overlay, (0, height - total_text_height), (width, height), bg_color, -1)

        # Blend overlay with original image
        alpha = 0.7
        cv2.addWeighted(overlay, alpha, img_copy, 1 - alpha, 0, img_copy)

        # Add text lines
        y_position = height - total_text_height + padding + line_height
        for line in lines:
            cv2.putText(
                img_copy,
                line,
                (padding, y_position),
                font,
                font_scale,
                text_color,
                font_thickness,
                cv2.LINE_AA,
            )
            y_position += line_height

        return img_copy
