import os

# The model is fully downloaded and cached locally after its first use, so
# there is no legitimate reason for later loads to touch the network at all.
# Forcing offline mode skips huggingface_hub's habit of re-probing the Hub on
# every load (HEAD requests for optional multimodal config files that don't
# apply to this model) - on this machine's network those probes hang for
# minutes retrying through 504 timeouts before falling back to cache anyway.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from functools import lru_cache  # noqa: E402

import numpy as np  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    # cached so the ~80MB model loads once per process, not once per call
    return SentenceTransformer(MODEL_NAME)


def embed(texts: list[str]) -> np.ndarray:
    model = get_model()
    return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
