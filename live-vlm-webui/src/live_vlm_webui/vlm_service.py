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
VLM Service
Handles async image analysis using any OpenAI-compatible VLM API
(Works with vLLM, SGLang, Ollama, OpenAI, etc.)
"""

import asyncio
import base64
import io
import time
from openai import AsyncOpenAI
from PIL import Image
from typing import Optional
import logging
import httpx

logger = logging.getLogger(__name__)


class VLMService:
    """Service for analyzing images using VLM via OpenAI-compatible API"""

    def __init__(
        self,
        model: str,
        api_base: str = "http://localhost:8000/v1",
        api_key: str = "EMPTY",
        prompt: str = "Describe what you see in this image in one sentence.",
        max_tokens: int = 512,
    ):
        """
        Initialize VLM service

        Args:
            model: Model name (e.g., "llama-3.2-11b-vision-instruct" for vLLM)
            api_base: Base URL for the API (e.g., "http://localhost:8000/v1" for vLLM)
            api_key: API key (use "EMPTY" for local servers)
            prompt: Default prompt to use for image analysis
            max_tokens: Maximum tokens to generate
        """
        self.model = model
        self.api_base = api_base
        self.api_key = api_key if api_key else "EMPTY"
        self.prompt = prompt
        self.max_tokens = max_tokens
        # Allow up to 5 minutes for a single inference request — large models
        # (e.g. 72B) can take a while to load into memory on first use.
        self._client_timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=10.0)
        self.client = AsyncOpenAI(base_url=api_base, api_key=api_key, timeout=self._client_timeout)
        self.current_response = "Initializing..."
        self.is_processing = False
        self.is_model_switching = False  # True while old model is being unloaded
        self._processing_lock = asyncio.Lock()
        self._last_request_payload = None  # For debug: request body (image truncated)
        self._last_response_payload = None  # For debug: API response body

        # Metrics tracking
        self.last_inference_time = 0.0  # seconds
        self.total_inferences = 0
        self.total_inference_time = 0.0

    async def analyze_image(self, image: Image.Image, prompt: Optional[str] = None) -> str:
        """
        Analyze an image using the VLM model

        Args:
            image: PIL Image to analyze
            prompt: Prompt for the VLM (uses default if None)

        Returns:
            Generated response string
        """
        if prompt is None:
            prompt = self.prompt

        try:
            start_time = time.perf_counter()

            # Downscale to max 896px on the long edge before encoding.
            # Qwen2.5-VL tiles images into 14×14-pixel patches; beyond ~896px you
            # get more visual tokens but no meaningful accuracy gain for live scene
            # understanding, and inference time scales roughly with token count.
            MAX_SIDE = 896
            w, h = image.size
            if max(w, h) > MAX_SIDE:
                scale = MAX_SIDE / max(w, h)
                image = image.resize(
                    (int(w * scale), int(h * scale)), Image.LANCZOS
                )

            # Convert PIL Image to base64
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format="JPEG", quality=85)
            img_byte_arr = img_byte_arr.getvalue()
            img_base64 = base64.b64encode(img_byte_arr).decode("utf-8")

            # Create message with image
            image_url = f"data:image/jpeg;base64,{img_base64}"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ]

            # Store request payload for debug (truncate base64 for display)
            truncate_len = 120
            if len(img_base64) > truncate_len:
                image_url_debug = f"data:image/jpeg;base64,{img_base64[:truncate_len]}...<{len(img_base64)} chars total>"
            else:
                image_url_debug = image_url
            messages_debug = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url_debug}},
                    ],
                }
            ]
            self._last_request_payload = {
                "model": self.model,
                "messages": messages_debug,
                "max_tokens": self.max_tokens,
                "temperature": 0.7,
            }

            # Call API — with retry for transient model-loading failures.
            # Large models (e.g. 72B) can take time to swap into memory;
            # Ollama may return a loading error on the first few attempts.
            MAX_RETRIES = 3
            RETRY_DELAYS = [8, 16, 30]  # seconds between attempts
            last_exc: Optional[Exception] = None

            for attempt in range(MAX_RETRIES):
                try:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=self.max_tokens,
                        temperature=0.7,
                    )
                    last_exc = None
                    break  # success — exit retry loop
                except Exception as exc:
                    last_exc = exc
                    raw = str(exc)
                    logger.warning(
                        f"[{self.model}] attempt {attempt + 1}/{MAX_RETRIES} failed: {raw}"
                    )
                    if self._is_loading_error(raw) and attempt < MAX_RETRIES - 1:
                        wait = RETRY_DELAYS[attempt]
                        logger.info(f"[{self.model}] model loading — retrying in {wait}s")
                        self.current_response = (
                            f"[Loading] {self.model} is loading into memory, "
                            f"retrying in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})…"
                        )
                        await asyncio.sleep(wait)
                    else:
                        raise  # non-loading error or out of retries — propagate

            if last_exc is not None:
                raise last_exc

            # Store response payload for debug (serialize to dict)
            try:
                self._last_response_payload = (
                    response.model_dump() if hasattr(response, "model_dump") else response.dict()
                )
            except Exception:
                self._last_response_payload = {
                    "id": getattr(response, "id", None),
                    "model": getattr(response, "model", None),
                    "choices": [
                        {
                            "index": getattr(c, "index", i),
                            "message": {
                                "role": getattr(getattr(c, "message", None), "role", None),
                                "content": getattr(getattr(c, "message", None), "content", None),
                            },
                            "finish_reason": getattr(c, "finish_reason", None),
                        }
                        for i, c in enumerate(getattr(response, "choices", []))
                    ],
                    "usage": getattr(response, "usage", None),
                }

            # Calculate latency
            end_time = time.perf_counter()
            inference_time = end_time - start_time

            # Update metrics
            self.last_inference_time = inference_time
            self.total_inferences += 1
            self.total_inference_time += inference_time

            result = response.choices[0].message.content.strip()
            logger.info(f"VLM response: {result} (latency: {inference_time*1000:.0f}ms)")

            # Check for common text-only model responses about not seeing images
            if not self.is_image_compatible_model():
                logger.warning(f"[WARNING] Model '{self.model}' may not support images. Consider using a VLM like llama-3.2-vision.")

            # Detect if model claims it can't see the image
            negative_responses = [
                "not able to see", "cannot see", "can't see", "unable to view",
                "no image", "no picture", "upload an image", "provide an image"
            ]
            result_lower = result.lower()
            if any(resp in result_lower for resp in negative_responses):
                logger.warning(f"[WARNING] Model '{self.model}' responded as if it can't see the image. This model may not support vision input.")
                return f"[INFO] {result} (Note: This model may not support image input)"

            return result

        except Exception as e:
            error_msg = str(e)
            # Always log the raw exception so the server logs show the real cause
            logger.error(f"Error analyzing image with model '{self.model}': {error_msg}", exc_info=True)
            return self._format_error(error_msg)

    def _is_loading_error(self, error_msg: str) -> bool:
        """Return True if the error looks like a temporary model-loading failure."""
        lower = error_msg.lower()
        loading_signals = (
            "failed to load",
            "model is loading",
            "model is currently loading",
            "not enough memory",
            "out of memory",
            "cuda out of memory",
            "insufficient memory",
            "resourceexhausted",
            "resource exhausted",
            "loading model",
            "context deadline exceeded",
        )
        return any(s in lower for s in loading_signals)

    def _format_error(self, error_msg: str) -> str:
        """Turn a raw exception string into a readable user-facing message.

        The raw error text is always included so it is visible in the UI and
        easy to copy when reporting issues — previously it was silently swallowed
        by the pattern-matching logic.
        """
        lower = error_msg.lower()
        if self._is_loading_error(error_msg):
            return (
                f"[ERROR] Model loading error — Ollama says: {error_msg}\n"
                f"Tip: Run 'ollama run {self.model}' in a terminal first to pre-load the model, "
                f"then switch back to it here."
            )
        elif "not found" in lower or "404" in error_msg:
            return (
                f"[ERROR] Model '{self.model}' not found — pull it with: "
                f"ollama pull {self.model}\nDetails: {error_msg}"
            )
        elif "timeout" in lower or "timed out" in lower:
            return (
                f"[ERROR] Request timed out waiting for '{self.model}'. "
                f"The model may still be loading — try again in a moment.\n"
                f"Details: {error_msg}"
            )
        elif "connection" in lower or "refused" in lower:
            return (
                f"[ERROR] Cannot reach Ollama at {self.api_base}. "
                f"Is Ollama running?\nDetails: {error_msg}"
            )
        else:
            return f"[ERROR] {error_msg}"

    def is_image_compatible_model(self) -> bool:
        """
        Check if the current model is likely to support image inputs.
        Uses a whitelist of known non-VLM models.
        """
        # Known text-only models that don't support images
        text_only_models = {
            'nemotron', 'gpt-3', 'text-', 'embedding', 'codellama',
            'llama3-', 'mistral-', 'mixtral-'
        }
        model_lower = self.model.lower()

        # Check if model name matches known text-only models
        for text_model in text_only_models:
            if text_model in model_lower:
                return False

        return True

    def get_last_request_payload(self) -> Optional[dict]:
        """
        Return the last request payload sent to the API (for debug).
        Image data is truncated to avoid huge JSON. Returns None if no request has been made yet.
        """
        return self._last_request_payload

    def get_last_response_payload(self) -> Optional[dict]:
        """
        Return the last API response payload (for debug).
        Returns None if no response has been received yet.
        """
        return self._last_response_payload

    async def process_frame(self, image: Image.Image, prompt: Optional[str] = None) -> None:
        """
        Process a frame asynchronously. Updates self.current_response when done.
        If already processing, this call is skipped.

        Args:
            image: PIL Image to process
            prompt: Optional custom prompt (uses default if None)
        """
        # Skip while the model is being switched — the old model is being
        # unloaded from Ollama and we must not send any requests until the
        # new model has had a chance to load into memory.
        if self.is_model_switching:
            logger.debug("Model switch in progress, skipping frame")
            return

        # Non-blocking check if we're already processing
        if self._processing_lock.locked():
            logger.debug("VLM busy, skipping frame")
            return

        async with self._processing_lock:
            self.is_processing = True
            try:
                response = await self.analyze_image(image, prompt)
                self.current_response = response
            finally:
                self.is_processing = False

    def get_current_response(self) -> tuple[str, bool]:
        """
        Get the current response and processing status

        Returns:
            Tuple of (response, is_processing)
        """
        return self.current_response, self.is_processing

    def get_metrics(self) -> dict:
        """
        Get current performance metrics

        Returns:
            Dict with latency and throughput metrics
        """
        avg_latency = (
            self.total_inference_time / self.total_inferences if self.total_inferences > 0 else 0.0
        )

        return {
            "last_latency_ms": self.last_inference_time * 1000,
            "avg_latency_ms": avg_latency * 1000,
            "total_inferences": self.total_inferences,
            "is_processing": self.is_processing,
        }

    def update_prompt(self, new_prompt: str, max_tokens: Optional[int] = None) -> None:
        """
        Update the default prompt and optionally max_tokens

        Args:
            new_prompt: New prompt to use
            max_tokens: Maximum tokens to generate (optional)
        """
        self.prompt = new_prompt
        if max_tokens is not None:
            self.max_tokens = max_tokens
            logger.info(f"Updated prompt to: {new_prompt}, max_tokens: {max_tokens}")
        else:
            logger.info(f"Updated prompt to: {new_prompt}")

    def update_api_settings(
        self, api_base: Optional[str] = None, api_key: Optional[str] = None
    ) -> None:
        """
        Update API base URL and/or API key, recreating the client

        Args:
            api_base: New API base URL (optional)
            api_key: New API key (optional, use empty string for local services)
        """
        if api_base:
            self.api_base = api_base
        if api_key is not None:  # Allow empty string
            self.api_key = api_key if api_key else "EMPTY"

        # Recreate the client with new settings (keep the same generous timeout)
        self.client = AsyncOpenAI(base_url=self.api_base, api_key=self.api_key, timeout=self._client_timeout)

        masked_key = (
            "***" + self.api_key[-4:]
            if self.api_key and len(self.api_key) > 4 and self.api_key != "EMPTY"
            else "EMPTY"
        )
        logger.info(f"Updated API settings - base: {self.api_base}, key: {masked_key}")
