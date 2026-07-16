from pathlib import Path

import chromadb

DB_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "chroma"

_client = chromadb.PersistentClient(path=str(DB_DIR))


def get_collection(name: str):
    return _client.get_or_create_collection(name)


def add_chunks(
    collection_name: str,
    chunks: list[str],
    embeddings,
    source_filenames: list[str],
) -> None:
    collection = get_collection(collection_name)
    ids = [f"{source_filenames[i]}::{i}" for i in range(len(chunks))]
    collection.add(
        ids=ids,
        embeddings=[e.tolist() for e in embeddings],
        documents=chunks,
        metadatas=[{"source": source_filenames[i]} for i in range(len(chunks))],
    )


def query(collection_name: str, query_embedding, top_k: int = 5) -> list[dict]:
    collection = get_collection(collection_name)
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k,
    )
    return [
        {"text": doc, "source": meta["source"], "distance": dist}
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
    ]
