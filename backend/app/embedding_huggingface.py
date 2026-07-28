import os
import time
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# same model as embedding_local.py, on purpose - keeps this comparison
# isolated to "hosted vs local execution", not entangled with a model-quality
# change too
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_NAME}/pipeline/feature-extraction"

# no published hard cap for this endpoint (unlike Voyage's documented 1,000)
# - kept moderate to bound single-request payload/latency without guessing
MAX_BATCH = 100

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        # same SSL workaround as generation.py/embedding_voyage.py - this
        # machine fails standard verification against every HTTPS host tried
        _client = httpx.Client(verify=False, timeout=30.0)
    return _client


def _embed_batch(texts: list[str], max_retries: int = 5) -> np.ndarray:
    client = _get_client()
    for attempt in range(max_retries):
        response = client.post(
            API_URL,
            headers={"Authorization": f"Bearer {os.environ['HUGGINGFACE_API_KEY']}"},
            json={"inputs": texts, "normalize": True},
        )
        if response.status_code == 503:
            # serverless cold start - model is being loaded onto a worker,
            # HF reports how long via estimated_time
            if attempt == max_retries - 1:
                response.raise_for_status()
            wait = response.json().get("estimated_time", 10)
            time.sleep(wait + 1)
            continue
        response.raise_for_status()
        # response is a bare array of vectors, in request order (no index field)
        return np.array(response.json())


def embed(texts: list[str], input_type: str | None = None) -> np.ndarray:
    """Swappable embedding interface - same call shape as embedding_local.embed
    and embedding_voyage.embed. input_type is accepted-and-ignored: this model
    has no query/document prompt distinction (same as the local model)."""
    if len(texts) <= MAX_BATCH:
        return _embed_batch(texts)

    batches = [_embed_batch(texts[i : i + MAX_BATCH]) for i in range(0, len(texts), MAX_BATCH)]
    return np.concatenate(batches)
