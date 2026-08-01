"""
Thin wrapper around the Groq chat-completions API (OpenAI-compatible).

SokoPulse's AI features call Groq directly and do not fall back to any
rule-based substitute: if the key is missing/invalid, or the request fails,
that failure is raised as GroqUnavailable and is expected to propagate up to
the view layer, which turns it into a proper error response (see
ai_engine/views.py). The Groq API key and model are managed from the Django
admin (Configuration → System configuration), not environment variables —
see configuration/models.py.
"""
import json

import requests

from configuration.models import SystemConfiguration

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqUnavailable(Exception):
    """Raised whenever the AI layer can't be used — missing key, network error, bad response."""


class GroqNotConfigured(GroqUnavailable):
    """Raised specifically when no Groq API key has been configured yet."""


def is_configured() -> bool:
    return bool(SystemConfiguration.load().groq_api_key)


def _config():
    cfg = SystemConfiguration.load()
    if not cfg.groq_api_key:
        raise GroqNotConfigured(
            "The Groq API key is not configured. Ask an administrator to set it in the "
            "admin panel under Configuration \u2192 System configuration."
        )
    return cfg


def chat_json(system_prompt: str, user_prompt: str, temperature: float = 0.4, max_tokens: int = 2000) -> dict:
    """Call Groq asking for a strict JSON object response, and return it parsed."""
    cfg = _config()
    payload = {
        "model": cfg.groq_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        resp = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {cfg.groq_api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=cfg.groq_timeout_seconds,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except requests.RequestException as exc:
        raise GroqUnavailable(f"Groq request failed: {exc}") from exc
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise GroqUnavailable(f"Groq returned an unexpected response: {exc}") from exc


def chat_text(system_prompt: str, user_prompt: str, temperature: float = 0.5, max_tokens: int = 800) -> str:
    """Call Groq for a free-text (non-JSON) response — used for the conversational assistant."""
    cfg = _config()
    payload = {
        "model": cfg.groq_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        resp = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {cfg.groq_api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=cfg.groq_timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except requests.RequestException as exc:
        raise GroqUnavailable(f"Groq request failed: {exc}") from exc
    except (KeyError, IndexError) as exc:
        raise GroqUnavailable(f"Groq returned an unexpected response: {exc}") from exc
