import os

# EMBEDDING_PROVIDER selects which implementation backs embed() - "local"
# (default, no external API key needed), "huggingface" (what the deployed
# instance runs, needs HUGGINGFACE_API_KEY), or "voyage" (evaluated first,
# kept working but unused - see README for why huggingface won out). Callers
# never see this switch - they only ever call embedding.embed(...).
# stripped+lowercased - a stray trailing space or case mismatch from pasting
# into a dashboard's env var field would otherwise silently fall through to
# the local branch with no error, which is exactly what loads torch
_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "local").strip().lower()

print(f"[embedding] EMBEDDING_PROVIDER={_PROVIDER!r}")

if _PROVIDER == "huggingface":
    from app.embedding_huggingface import embed  # noqa: F401
elif _PROVIDER == "voyage":
    from app.embedding_voyage import embed  # noqa: F401
else:
    from app.embedding_local import embed  # noqa: F401
