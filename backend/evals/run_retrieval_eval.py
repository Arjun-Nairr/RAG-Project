"""
Run the fixed eval set against a Chroma collection and report hit rate + MRR.

Usage: venv/Scripts/python.exe -m evals.run_retrieval_eval [collection_name] [top_k]
"""

import sys

from app import embedding, vector_store
from evals.eval_set import EVAL_QUESTIONS


def run(collection_name: str, top_k: int = 5) -> dict:
    reciprocal_ranks = []
    details = []

    for item in EVAL_QUESTIONS:
        query_vector = embedding.embed([item["question"]])[0]
        results = vector_store.query(collection_name, query_vector, top_k=top_k)
        sources = [r["source"] for r in results]

        rank = next(
            (i + 1 for i, s in enumerate(sources) if s == item["expected_source"]),
            None,
        )
        reciprocal_ranks.append(1 / rank if rank else 0)
        details.append(
            {
                "question": item["question"],
                "expected_source": item["expected_source"],
                "found_at_rank": rank,
                "retrieved_sources": sources,
            }
        )

    hit_rate = sum(1 for r in reciprocal_ranks if r > 0) / len(EVAL_QUESTIONS)
    mrr = sum(reciprocal_ranks) / len(EVAL_QUESTIONS)

    return {
        "collection": collection_name,
        "top_k": top_k,
        "hit_rate": hit_rate,
        "mrr": mrr,
        "details": details,
    }


if __name__ == "__main__":
    collection = sys.argv[1] if len(sys.argv) > 1 else "test_corpus"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    result = run(collection, k)

    print(f"Collection: {result['collection']} | top_k={result['top_k']}")
    print(f"Hit rate: {result['hit_rate']:.2%}")
    print(f"MRR:      {result['mrr']:.4f}")
    print()
    for d in result["details"]:
        status = f"rank {d['found_at_rank']}" if d["found_at_rank"] else "MISSED"
        print(f"[{status:>8}] {d['question']}")
