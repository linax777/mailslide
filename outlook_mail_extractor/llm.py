"""LLM API Integration Module"""

from dataclasses import dataclass
from typing import Any

import httpx


class LLMError(Exception):
    """LLM API error"""

    pass


@dataclass
class LLMConfig:
    """LLM API configuration"""

    api_base: str = "http://localhost:11434/v1"
    api_key: str = ""
    model: str = "llama3"
    timeout: int = 30


class LLMClient:
    """OpenAI compatible LLM API client"""

    def __init__(self, config: LLMConfig):
        self.config = config
        normalized_base = self._normalize_api_base(config.api_base)
        self._client = httpx.Client(
            base_url=normalized_base,
            timeout=config.timeout,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _normalize_api_base(self, api_base: str) -> str:
        """
        Normalize API base URL for stable endpoint joining.

        Args:
            api_base: Raw API base from config

        Returns:
            Normalized base URL ending with '/'

        Raises:
            LLMError: When api_base is empty
        """
        normalized = api_base.strip()
        if not normalized:
            raise LLMError("api_base is empty")
        return normalized.rstrip("/") + "/"

    def _extract_error_detail(self, payload: Any) -> str:
        """Extract best-effort error detail from OpenAI-compatible payload."""
        if not isinstance(payload, dict):
            return ""

        error_field = payload.get("error")
        if isinstance(error_field, str):
            return error_field
        if isinstance(error_field, dict):
            message = error_field.get("message")
            if isinstance(message, str):
                return message
        return ""

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> str:
        """
        Send chat completion request to LLM API.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt (email content)
            temperature: Sampling temperature

        Returns:
            LLM response text

        Raises:
            LLMError: When API request fails
        """
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        try:
            # Keep endpoint relative so base_url path (e.g. /v1/) is preserved.
            response = self._client.post("chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                payload = e.response.json()
                detail = self._extract_error_detail(payload)
            except Exception:
                detail = e.response.text.strip()

            detail = detail or "no response body"
            if len(detail) > 300:
                detail = detail[:300] + "..."

            raise LLMError(f"HTTP error: {e.response.status_code} - {detail}") from e
        except httpx.RequestError as e:
            request_url = str(e.request.url) if e.request else "(unknown URL)"
            raise LLMError(f"Request failed ({request_url}): {e}") from e
        except KeyError as e:
            raise LLMError(f"Invalid response format: {e}") from e

    def close(self) -> None:
        """Close the HTTP client"""
        self._client.close()


def load_llm_config(config_file: str | None = None) -> LLMConfig:
    """
    Load LLM configuration from YAML file.

    Args:
        config_file: Path to llm.yaml (default: llm.yaml in current dir)

    Returns:
        LLMConfig instance
    """
    from pathlib import Path

    import yaml

    config_path = Path(config_file) if config_file else Path("config/llm-config.yaml")

    if not config_path.exists():
        return LLMConfig()

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return LLMConfig(
        api_base=data.get("api_base", "http://localhost:11434/v1"),
        api_key=data.get("api_key", ""),
        model=data.get("model", "llama3"),
        timeout=data.get("timeout", 30),
    )
