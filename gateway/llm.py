"""Single entry point for structured LLM calls (Anthropic API, JSON output only)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from shared import config

log = logging.getLogger("llm")

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model could not produce a usable structured answer."""


@lru_cache(maxsize=1)
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(timeout=60.0, max_retries=2)


def structured_call(system: str, user: str, output_model: type[T], effort: str = "medium") -> T:
    """One request, validated against `output_model`. Raises LLMError on failure."""
    try:
        response = _client().beta.messages.parse(
            model=config.LLM_MODEL,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=output_model,
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIConnectionError as e:
        raise LLMError(f"LLM unreachable: {e}") from e
    except anthropic.RateLimitError as e:
        raise LLMError("LLM rate limited") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"LLM error {e.status_code}: {e.message}") from e

    if response.stop_reason == "refusal":
        raise LLMError("LLM refused the request")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise LLMError(f"LLM returned no valid structured output (stop_reason={response.stop_reason})")
    return response.parsed_output
