from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from slm.config.settings import get_settings
from slm.logging.setup import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class StructuredOutputError(Exception):
    """Model output could not be parsed into the target schema."""


def extract_json_blob(text: str) -> str:
    """Pull JSON from raw model text (fenced block or first object)."""
    match = _JSON_FENCE.search(text)
    if match:
        return match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


def parse_structured(text: str, model: type[T]) -> T:
    blob = extract_json_blob(text)
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(f"Invalid JSON: {exc}") from exc
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise StructuredOutputError(f"Schema validation failed: {exc}") from exc


def parse_with_retry(text: str, model: type[T]) -> T:
    settings = get_settings()
    last_error: Exception | None = None
    for attempt in range(1, settings.max_retries + 1):
        try:
            return parse_structured(text, model)
        except StructuredOutputError as exc:
            last_error = exc
            logger.warning("structured_parse_failed", attempt=attempt, error=str(exc))
    assert last_error is not None
    raise last_error
