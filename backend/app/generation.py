import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from groq import Groq, RateLimitError

# resolve .env relative to this file, not the process's cwd - the backend
# gets launched with varying working directories depending on how it's run
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODEL_NAME = "llama-3.3-70b-versatile"

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        # this machine's network fails standard SSL verification against
        # every HTTPS host we've used this session (huggingface.co, arxiv.org,
        # now api.groq.com) - same pragmatic unblock as embedding.py, against
        # another well-known trusted host
        _client = Groq(
            api_key=os.environ["GROQ_API_KEY"],
            http_client=httpx.Client(verify=False),
        )
    return _client


def generate(prompt: str, max_retries: int = 5) -> str:
    """Swappable LLM interface — swapping providers later means changing
    only this function's body, not any caller."""
    client = _get_client()

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            # free tier: 30 req/min, 12k tokens/min - back off well past a
            # minute rather than guessing, since burst limits reset per-minute
            wait = 65
            retry_after = getattr(e, "response", None) and e.response.headers.get(
                "retry-after"
            )
            if retry_after:
                wait = float(retry_after) + 2
            time.sleep(wait)
