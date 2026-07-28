import os
import time
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODEL_NAME = "voyage-4-lite"
API_URL = "https://api.voyageai.com/v1/embeddings"

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        # same SSL workaround as generation.py - this machine fails standard
        # verification against every HTTPS host tried this session
        _client = httpx.Client(verify=False, timeout=30.0)
    return _client


# Voyage rejects requests over 1,000 input items - a large upload (e.g. a
# 200-page textbook) or the multi-paper eval corpus can realistically exceed
# that, so batch rather than assume every call fits in one request
MAX_BATCH = 1000


def _embed_batch(texts: list[str], input_type: str | None, max_retries: int = 5) -> np.ndarray:
    client = _get_client()
    for attempt in range(max_retries):
        response = client.post(
            API_URL,
            headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
            json={"input": texts, "model": MODEL_NAME, "input_type": input_type},
        )
        if response.status_code == 429:
            if attempt == max_retries - 1:
                response.raise_for_status()
            # accounts without a payment method on file are capped at 3 RPM -
            # wait a full cycle rather than guess, no Retry-After header sent
            retry_after = response.headers.get("retry-after")
            time.sleep(float(retry_after) + 2 if retry_after else 21)
            continue
        response.raise_for_status()
        # response order matches request order, but each item carries its own
        # index - sort by it rather than assume
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        return np.array([item["embedding"] for item in data])


def embed(texts: list[str], input_type: str | None = None) -> np.ndarray:
    """Swappable embedding interface - same call shape as embedding_local.embed,
    so the dispatcher in embedding.py can route to either transparently."""
    if len(texts) <= MAX_BATCH:
        return _embed_batch(texts, input_type)

    batches = [
        _embed_batch(texts[i : i + MAX_BATCH], input_type)
        for i in range(0, len(texts), MAX_BATCH)
    ]
    return np.concatenate(batches)
