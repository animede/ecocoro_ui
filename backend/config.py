"""Runtime configuration, populated via environment variables set by run_server.py.

uvicorn can also be invoked directly (e.g. `uvicorn backend.main:app`) without going
through run_server.py, so we validate required settings here too instead of assuming
argparse already did it.
"""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    llm_endpoint: str
    llm_model: str
    llm_api_key: str
    model_id: str
    outputs_dir: str
    device: str


def load_settings() -> Settings:
    llm_endpoint = os.environ.get("ECOCORO_LLM_ENDPOINT")
    if not llm_endpoint:
        raise RuntimeError(
            "ECOCORO_LLM_ENDPOINT is not set. Start the server via run_server.py "
            "with --llm-endpoint, or set the ECOCORO_LLM_ENDPOINT environment "
            "variable before launching uvicorn directly."
        )
    return Settings(
        llm_endpoint=llm_endpoint.rstrip("/"),
        llm_model=os.environ.get("ECOCORO_LLM_MODEL", "default"),
        llm_api_key=os.environ.get("ECOCORO_LLM_API_KEY", "EMPTY"),
        model_id=os.environ.get("ECOCORO_MODEL_ID", "alfredplpl/ecocoro-preview-1"),
        outputs_dir=os.environ.get("ECOCORO_OUTPUTS_DIR", "./outputs"),
        device=os.environ.get("ECOCORO_DEVICE", "cuda"),
    )


settings = load_settings()
