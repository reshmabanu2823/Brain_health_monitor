"""Cloud AI Model configuration, persistence, and dynamic provider switching."""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

log = logging.getLogger(__name__)

ENV_FILE = Path(".env")

AVAILABLE_PROVIDERS = [
    {
        "id": "gemini",
        "name": "Google Gemini",
        "models": ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"],
        "default_model": "gemini-1.5-flash",
        "key_url": "https://aistudio.google.com/app/apikey",
        "free_tier": True,
        "description": "Google Gemini Generative AI. Generous free tier with multimodal reasoning.",
    },
    {
        "id": "groq",
        "name": "Groq Cloud (Fast & Free)",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "default_model": "llama-3.3-70b-versatile",
        "key_url": "https://console.groq.com/keys",
        "free_tier": True,
        "description": "Ultra-fast LPU inference hosting Meta Llama 3.3 70B. Free API keys available.",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "models": ["gpt-4o-mini", "gpt-4o"],
        "default_model": "gpt-4o-mini",
        "key_url": "https://platform.openai.com/api-keys",
        "free_tier": False,
        "description": "OpenAI flagship intelligence models.",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (Open & Free Models)",
        "models": ["meta-llama/llama-3.3-70b-instruct:free", "google/gemini-2.0-flash-exp:free", "mistralai/mistral-7b-instruct:free"],
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "key_url": "https://openrouter.ai/keys",
        "free_tier": True,
        "description": "Unified gateway to open-source models with free options.",
    },
    {
        "id": "local",
        "name": "Local Grounded Engine (Offline Fallback)",
        "models": ["local-deterministic"],
        "default_model": "local-deterministic",
        "key_url": "",
        "free_tier": True,
        "description": "Runs locally without external internet or API keys.",
    },
]


def mask_key(key: Optional[str]) -> str:
    """Mask key for display, e.g. AIzaSy...4X9Z."""
    if not key or len(key) < 8:
        return ""
    return f"{key[:6]}...{key[-4:]}"


def read_env_file() -> Dict[str, str]:
    """Parse key=value pairs from .env if present."""
    env_vars: Dict[str, str] = {}
    if not ENV_FILE.exists():
        return env_vars
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip("'\"")
    except Exception as exc:
        log.warning("Failed to read .env file: %s", exc)
    return env_vars


def write_env_file(updates: Dict[str, str]) -> None:
    """Update or append variables in .env file."""
    current_lines: List[str] = []
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                current_lines = f.readlines()
        except Exception:
            current_lines = []

    written_keys = set()
    new_lines = []
    for line in current_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}\n")
                written_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in written_keys:
            new_lines.append(f"{k}={v}\n")

    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as exc:
        log.error("Failed to write .env file: %s", exc)


def get_current_ai_config() -> Dict[str, Any]:
    """Inspect environment and return current cloud AI provider status."""
    env_vars = read_env_file()

    # Active provider priority: CORTIA_AI_PROVIDER > check existing keys
    provider_id = (
        os.getenv("CORTIA_AI_PROVIDER")
        or env_vars.get("CORTIA_AI_PROVIDER")
    )

    gemini_key = os.getenv("CORTIA_AI_API_KEY") or os.getenv("GEMINI_API_KEY") or env_vars.get("GEMINI_API_KEY") or env_vars.get("CORTIA_AI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY") or env_vars.get("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY") or env_vars.get("OPENAI_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY") or env_vars.get("OPENROUTER_API_KEY")

    if not provider_id:
        if gemini_key:
            provider_id = "gemini"
        elif groq_key:
            provider_id = "groq"
        elif openai_key:
            provider_id = "openai"
        elif openrouter_key:
            provider_id = "openrouter"
        else:
            provider_id = "local"

    # Determine key and model for active provider
    active_key = None
    active_model = None
    if provider_id == "gemini":
        active_key = gemini_key
        active_model = os.getenv("CORTIA_GEMINI_MODEL") or env_vars.get("CORTIA_GEMINI_MODEL") or "gemini-1.5-flash"
    elif provider_id == "groq":
        active_key = groq_key
        active_model = os.getenv("CORTIA_GROQ_MODEL") or env_vars.get("CORTIA_GROQ_MODEL") or "llama-3.3-70b-versatile"
    elif provider_id == "openai":
        active_key = openai_key
        active_model = os.getenv("CORTIA_OPENAI_MODEL") or env_vars.get("CORTIA_OPENAI_MODEL") or "gpt-4o-mini"
    elif provider_id == "openrouter":
        active_key = openrouter_key
        active_model = os.getenv("CORTIA_OPENROUTER_MODEL") or env_vars.get("CORTIA_OPENROUTER_MODEL") or "meta-llama/llama-3.3-70b-instruct:free"
    else:
        active_model = "local-deterministic"

    is_cloud = provider_id in ("gemini", "groq", "openai", "openrouter") and bool(active_key)

    prov_meta = next((p for p in AVAILABLE_PROVIDERS if p["id"] == provider_id), AVAILABLE_PROVIDERS[0])

    return {
        "active_provider": provider_id,
        "provider_name": prov_meta["name"],
        "model_name": active_model,
        "is_cloud": is_cloud,
        "has_api_key": bool(active_key),
        "masked_key": mask_key(active_key),
        "available_providers": AVAILABLE_PROVIDERS,
    }


def test_cloud_provider(provider_id: str, api_key: str, model_name: Optional[str] = None) -> Dict[str, Any]:
    """Perform a fast test ping to the specified cloud provider to verify API key validity."""
    import time
    t0 = time.time()

    if not api_key and provider_id != "local":
        return {"success": False, "error": "API Key is required."}

    if provider_id == "local":
        return {"success": True, "latency_ms": 1, "model": "local-deterministic", "message": "Local engine ready."}

    try:
        if provider_id == "gemini":
            model = model_name or "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": "Reply with only 'OK'"}]}],
                "generationConfig": {"maxOutputTokens": 5}
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload)
                elapsed = int((time.time() - t0) * 1000)
                if res.status_code == 200:
                    return {"success": True, "latency_ms": elapsed, "model": model, "message": "Google Gemini connected successfully."}
                err_text = res.text[:200]
                try:
                    err_json = res.json()
                    err_text = err_json.get("error", {}).get("message", err_text)
                except Exception:
                    pass
                return {"success": False, "error": f"Gemini error ({res.status_code}): {err_text}"}

        elif provider_id in ("groq", "openai", "openrouter"):
            if provider_id == "groq":
                base_url = "https://api.groq.com/openai/v1"
                model = model_name or "llama-3.3-70b-versatile"
                headers = {"Authorization": f"Bearer {api_key}"}
            elif provider_id == "openrouter":
                base_url = "https://openrouter.ai/api/v1"
                model = model_name or "meta-llama/llama-3.3-70b-instruct:free"
                headers = {"Authorization": f"Bearer {api_key}", "HTTP-Referer": "http://localhost:8000", "X-Title": "CORTIA"}
            else:
                base_url = "https://api.openai.com/v1"
                model = model_name or "gpt-4o-mini"
                headers = {"Authorization": f"Bearer {api_key}"}

            headers["Content-Type"] = "application/json"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Reply with only 'OK'"}],
                "max_tokens": 5
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                elapsed = int((time.time() - t0) * 1000)
                if res.status_code == 200:
                    return {"success": True, "latency_ms": elapsed, "model": model, "message": f"{provider_id.upper()} connected successfully."}
                err_text = res.text[:200]
                try:
                    err_json = res.json()
                    err_text = err_json.get("error", {}).get("message", err_text)
                except Exception:
                    pass
                return {"success": False, "error": f"{provider_id.capitalize()} error ({res.status_code}): {err_text}"}

        else:
            return {"success": False, "error": f"Unsupported provider: {provider_id}"}

    except httpx.TimeoutException:
        return {"success": False, "error": "Connection timed out after 10 seconds."}
    except Exception as exc:
        return {"success": False, "error": f"Connection failed: {str(exc)}"}
