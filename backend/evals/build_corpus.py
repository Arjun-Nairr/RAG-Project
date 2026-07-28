"""
Build (or rebuild) the eval corpus into a Chroma collection, using whichever
embedding provider is active via EMBEDDING_PROVIDER. Needed once per provider
- vectors from different embedding models can't share a collection.

Usage: venv/Scripts/python.exe -m evals.build_corpus [collection_name]
       EMBEDDING_PROVIDER=voyage venv/Scripts/python.exe -m evals.build_corpus test_corpus_voyage
"""

import sys
from pathlib import Path

from app import chunking, embedding, ingestion, vector_store

PDFS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "pdfs"
PAPERS = [
    "attention_is_all_you_need.pdf",
    "bert.pdf",
    "rag_paper.pdf",
    "gpt3_few_shot.pdf",
    "lora.pdf",
]


def build(collection_name: str) -> None:
    # reset first so a rerun doesn't silently double up chunks in an
    # already-populated collection
    try:
        vector_store._client.delete_collection(collection_name)
    except Exception:
        pass

    all_chunks: list[str] = []
    all_sources: list[str] = []

    for filename in PAPERS:
        text = ingestion.extract_text_from_path(PDFS_DIR / filename)
        chunks = chunking.chunk_text(text)
        all_chunks.extend(chunks)
        all_sources.extend([filename] * len(chunks))

    print(f"Embedding {len(all_chunks)} chunks via {embedding.embed.__module__}...")
    vectors = embedding.embed(all_chunks, input_type="document")
    vector_store.add_chunks(collection_name, all_chunks, vectors, all_sources)
    print(f"Indexed {len(all_chunks)} chunks into '{collection_name}'")


if __name__ == "__main__":
    collection = sys.argv[1] if len(sys.argv) > 1 else "test_corpus"
    build(collection)
