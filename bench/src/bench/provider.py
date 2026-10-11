"""The benchmark's sole hosted provider: NVIDIA NIM, without paid fallbacks."""

import os

BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"
EXTRA_BODY = {"chat_template_kwargs": {"enable_thinking": False}}


def api_key():
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key:
        raise ValueError("NVIDIA_API_KEY is required")
    return key
