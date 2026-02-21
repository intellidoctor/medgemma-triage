"""MedGemma model interface for Vertex AI dedicated endpoints.

All model inference goes through this module. Agents must never call
models directly — they call generate_text() or analyze_image() instead.

Architecture:
    - OpenAI SDK pointed at Vertex AI dedicated endpoint DNS
    - GCP bearer token from service account (base64 env var)
    - Sync calls (LangGraph wraps in async when needed)
    - Exceptions bubble up — agents handle retries
"""

import atexit
import base64
import logging
import os
import tempfile
from typing import Optional

import google.auth.transport.requests
from dotenv import load_dotenv
from google.oauth2 import service_account
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GCP credential bootstrap (module-level, runs once at import)
# ---------------------------------------------------------------------------

_CREDS_PATH: Optional[str] = None
_CREDENTIALS: Optional[service_account.Credentials] = None

_MEDGEMMA_27B_MODEL = "google/medgemma-27b-text-it"
_MEDGEMMA_4B_MODEL = "google/medgemma-4b-it"


def _init_credentials() -> None:
    """Decode base64 service account JSON to a temp file and load credentials."""
    global _CREDS_PATH, _CREDENTIALS

    if _CREDENTIALS is not None:
        return

    b64 = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_BASE64")
    if not b64:
        raise EnvironmentError(
            "GOOGLE_APPLICATION_CREDENTIALS_BASE64 is not set. "
            "See .env.example for required environment variables."
        )

    decoded = base64.b64decode(b64).decode("utf-8")
    fd, path = tempfile.mkstemp(suffix=".json", prefix="gcp-creds-")
    os.close(fd)
    with open(path, "w") as f:
        f.write(decoded)
    os.chmod(path, 0o600)
    _CREDS_PATH = path
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path

    _CREDENTIALS = service_account.Credentials.from_service_account_file(
        path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    logger.info("GCP credentials loaded from base64 env var")


def _cleanup_credentials() -> None:
    """Remove temp credentials file on process exit."""
    if _CREDS_PATH and os.path.exists(_CREDS_PATH):
        try:
            os.unlink(_CREDS_PATH)
        except OSError:
            pass


atexit.register(_cleanup_credentials)


def _get_token() -> str:
    """Return a fresh GCP bearer token."""
    _init_credentials()
    assert _CREDENTIALS is not None
    _CREDENTIALS.refresh(google.auth.transport.requests.Request())
    if not _CREDENTIALS.token:
        raise RuntimeError("Failed to obtain GCP access token")
    return _CREDENTIALS.token


# ---------------------------------------------------------------------------
# OpenAI client factories (lazy, one per endpoint)
# ---------------------------------------------------------------------------


def _make_client(base_url_env: str) -> OpenAI:
    """Create an OpenAI client pointed at a Vertex AI dedicated endpoint."""
    base_url = os.environ.get(base_url_env)
    if not base_url:
        raise EnvironmentError(f"{base_url_env} is not set")
    token = _get_token()
    return OpenAI(base_url=base_url, api_key=token)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_text(
    prompt: str,
    system_prompt: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> str:
    """Generate text using MedGemma 27B (text-only, clinical reasoning).

    Args:
        prompt: The user message / clinical question.
        system_prompt: Optional system message for role setting.
        max_tokens: Maximum completion tokens.
        temperature: Sampling temperature.

    Returns:
        The model's text response.

    Raises:
        openai.APIError: On API failures.
        EnvironmentError: On missing configuration.
    """
    logger.info(
        "\033[35m\U0001f680 MedGemma 27B API call — "
        "prompt=%d chars, max_tokens=%d, temp=%.2f\033[0m",
        len(prompt),
        max_tokens,
        temperature,
    )
    client = _make_client("MEDGEMMA_27B_BASE_URL")

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=_MEDGEMMA_27B_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    result = response.choices[0].message.content
    logger.info(
        "\033[35m\U00002705 MedGemma 27B done — %d chars returned\033[0m",
        len(result),
    )
    return result


def analyze_image(
    image: bytes,
    prompt: str,
    system_prompt: str | None = None,
    mime_type: str = "image/jpeg",
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> str:
    """Analyze a medical image using MedGemma 4B (multimodal).

    Args:
        image: Raw image bytes (JPEG, PNG, etc.).
        prompt: Text prompt describing what to look for.
        system_prompt: Optional system message.
        mime_type: MIME type of the image (default: image/jpeg).
        max_tokens: Maximum completion tokens.
        temperature: Sampling temperature.

    Returns:
        The model's text response describing the image.

    Raises:
        openai.APIError: On API failures.
        EnvironmentError: On missing configuration.
    """
    client = _make_client("MEDGEMMA_4B_BASE_URL")

    image_b64 = base64.b64encode(image).decode("utf-8")

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                },
            ],
        }
    )

    response = client.chat.completions.create(
        model=_MEDGEMMA_4B_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content
