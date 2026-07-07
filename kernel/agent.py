import base64
import asyncio
import io
import logging
import random
from pathlib import Path
from typing import List, Optional

from openai import (
    AsyncOpenAI, APIStatusError, RateLimitError, InternalServerError,
    APIConnectionError, APITimeoutError,
)
from PIL import Image, ImageOps
from PyQt6.QtCore import QThread, pyqtSignal

from config import API_KEY, API_URL, MAX_IMAGE_WIDTH, JPEG_QUALITY, MAX_IMAGES_PER_REQUEST, ALL_TAG_CATEGORIES
from kernel.models import AITag, PresetTagSet
from kernel.prompt_service import PresetService
from utils.slug import sanitize_slug

_logger = logging.getLogger(__name__)

_MAX_API_RETRIES = 4
_RETRY_BASE_DELAY = 1.5
_RETRYABLE = (RateLimitError, InternalServerError, APIConnectionError, APITimeoutError)


class AIAgentClient:

    def __init__(self, model: str):
        self._base_url = API_URL
        self._api_key = API_KEY
        self._model = model
        self._client: AsyncOpenAI | None = None

    async def __aenter__(self):
        self._client = AsyncOpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=120.0,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.close()
            self._client = None

    async def fetch_models(self) -> List[str]:
        if not self._api_key:
            raise RuntimeError("No API key configured.")
        if not self._client:
            raise RuntimeError("AIAgentClient must be used as an async context manager.")

        models = await self._client.models.list()
        model_ids = [m.id for m in models.data]
        model_ids.sort()
        return model_ids

    def _encode_image(self, image_path: Path) -> str:
        img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
        w, h = img.size
        if w > MAX_IMAGE_WIDTH:
            ratio = MAX_IMAGE_WIDTH / w
            img = img.resize((MAX_IMAGE_WIDTH, int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    @classmethod
    def get_system_prompt(cls, preset: Optional[PresetTagSet] = None) -> str:
        return PresetService.get_system_prompt(preset)

    @classmethod
    def get_full_system_prompt(cls, preset: Optional[PresetTagSet] = None) -> str:
        return PresetService.build_system_prompt(preset)

    @classmethod
    def clear_prompt_cache(cls):
        PresetService.clear_prompt_cache()

    async def analyze_folder(self, image_paths: List[Path], preset: Optional[PresetTagSet] = None) -> List[AITag]:
        if not image_paths:
            return []

        n = min(MAX_IMAGES_PER_REQUEST, len(image_paths))
        image_paths = random.sample(image_paths, n)

        user_content: list = []
        for image_path in image_paths:
            image_b64 = self._encode_image(image_path)
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}",
                    "detail": "low",
                },
            })

        user_content.append({
            "type": "text",
            "text": f"Please analyze these {len(image_paths)} images as a set from the same folder.",
        })

        system_prompt = self.get_system_prompt(preset)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        return await self._call_api(messages)

    async def _call_api(self, messages: list) -> List[AITag]:
        if not self._api_key:
            raise RuntimeError("No API key configured.")
        if not self._model:
            raise RuntimeError("No model selected.")
        if not self._client:
            raise RuntimeError("AIAgentClient must be used as an async context manager.")

        last_err: Optional[Exception] = None
        for attempt in range(_MAX_API_RETRIES):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    max_tokens=2000,
                    temperature=0.1,
                )
                choice = response.choices[0]
                content = choice.message.content or ""
                try:
                    return self._parse_response(content)
                except RuntimeError as parse_err:
                    if choice.finish_reason == "length" and content.strip():
                        _logger.warning("Response truncated (max_tokens); partial parse only. %s", parse_err)
                        tags = self._parse_response_lenient(content)
                        if tags:
                            return tags
                    raise
            except _RETRYABLE as e:
                last_err = e
                delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.75)
                _logger.warning("API transient error (attempt %d/%d): %s; retrying in %.1fs",
                               attempt + 1, _MAX_API_RETRIES, e, delay)
                await asyncio.sleep(delay)
                continue
            except APIStatusError as e:
                status = getattr(e, "status_code", "?")
                raise RuntimeError(f"[{status}] API error: {e}") from e
            except asyncio.TimeoutError as e:
                last_err = e
                delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.75)
                _logger.warning("API timeout (attempt %d/%d); retrying in %.1fs",
                               attempt + 1, _MAX_API_RETRIES, delay)
                await asyncio.sleep(delay)
                continue

        raise RuntimeError(f"API request failed after {_MAX_API_RETRIES} attempts: {last_err}") from last_err

    def _parse_response(self, response: str) -> List[AITag]:
        if not response or not response.strip():
            raise RuntimeError("API returned empty response. No tags generated.")
        return self._parse_lines(response, strict_empty=True)

    def _parse_response_lenient(self, response: str) -> List[AITag]:
        return self._parse_lines(response, strict_empty=False)

    def _parse_lines(self, response: str, strict_empty: bool = True) -> List[AITag]:
        tags: List[AITag] = []
        fence = None
        for raw_line in (response or "").strip().splitlines():
            line = raw_line.strip().strip("`")
            if not line:
                continue
            stripped = line.lower()
            if stripped.startswith("```"):
                if fence is None:
                    fence = True
                    continue
                else:
                    fence = None
                    continue
            if fence:
                continue
            parts = line.split(":", 2)
            if len(parts) < 2:
                continue
            category = parts[0].strip().lower()
            if category not in ALL_TAG_CATEGORIES:
                continue
            value_field = parts[1].strip().strip("\"'")
            if not value_field:
                continue
            confidence = 0.9
            if len(parts) >= 3:
                try:
                    confidence = float(parts[2].strip())
                except ValueError:
                    confidence = 0.9
            confidence = max(0.0, min(1.0, confidence))

            raw_vals = value_field.split(",")
            if len(raw_vals) >= 2:
                try:
                    tail_conf = float(raw_vals[-1].strip())
                    if 0.0 <= tail_conf <= 1.0:
                        confidence = tail_conf
                        raw_vals = raw_vals[:-1]
                except ValueError:
                    pass

            for raw_val in raw_vals:
                slug = sanitize_slug(raw_val)
                if not slug:
                    continue
                tags.append(AITag(category=category, value=slug, confidence=confidence, confirmed=True))

        if not tags:
            if strict_empty:
                raise RuntimeError(
                    "API response contained no valid tags in expected format. "
                    "Raw response preview: " + response[:200]
                )
            return []

        seen: dict = {}
        for tag in tags:
            key = (tag.category, tag.value)
            if key not in seen or tag.confidence > seen[key].confidence:
                seen[key] = tag
        return list(seen.values())


class ModelListFetcher(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            models = asyncio.run(self._fetch())
            self.finished.emit(models)
        except Exception as e:
            self.error.emit(str(e))

    async def _fetch(self):
        async with AIAgentClient("") as client:
            return await client.fetch_models()
