"""
A/B compare naive vs. rubric prompts on the same question set, scored by
LLM-as-judge for groundedness + relevance.

Paced deliberately to stay under Groq's free-tier limits (30 req/min,
12k tokens/min for llama-3.3-70b-versatile): each call (generate or judge)
is followed by a fixed delay, since both count against the same pool.

Usage: venv/Scripts/python.exe -m evals.run_generation_eval [collection_name] [top_k]
"""

import sys
import time

from app import generation, qa
from evals.eval_set import EVAL_QUESTIONS
from evals.judge import judge

SECONDS_BETWEEN_CALLS = 6  # ~10 req/min, well under the 30/min free-tier cap


def run_one(collection_name: str, question: str, prompt_style: str, top_k: int) -> dict:
    results = qa.retrieve(collection_name, question, top_k)
    chunks = [r["text"] for r in results]
    sources = [r["source"] for r in results]
    context = "\n\n".join(chunks)

    prompt = qa.build_prompt(question, chunks, sources, prompt_style)
    answer = generation.generate(prompt)
    time.sleep(SECONDS_BETWEEN_CALLS)

    verdict = judge(question, context, answer)
    time.sleep(SECONDS_BETWEEN_CALLS)

    return {"question": question, "answer": answer, **verdict}


def run(collection_name: str, top_k: int = 5) -> dict:
    results = {"naive": [], "rubric": []}
    total = len(EVAL_QUESTIONS) * 2
    done = 0

    for item in EVAL_QUESTIONS:
        for style in ("naive", "rubric"):
            r = run_one(collection_name, item["question"], style, top_k)
            results[style].append(r)
            done += 1
            print(
                f"[{done}/{total}] {style:>6} | grounded={r['grounded']} relevant={r['relevant']} | {item['question'][:60]}",
                flush=True,
            )

    summary = {}
    for style in ("naive", "rubric"):
        n = len(results[style])
        summary[style] = {
            "grounded_rate": sum(r["grounded"] for r in results[style]) / n,
            "relevant_rate": sum(r["relevant"] for r in results[style]) / n,
        }

    return {"summary": summary, "details": results}


if __name__ == "__main__":
    collection = sys.argv[1] if len(sys.argv) > 1 else "test_corpus"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    result = run(collection, k)

    print()
    print(f"Collection: {collection} | top_k={k} | n={len(EVAL_QUESTIONS)}")
    print()
    for style in ("naive", "rubric"):
        s = result["summary"][style]
        print(f"{style.upper():>7} — grounded: {s['grounded_rate']:.1%}  relevant: {s['relevant_rate']:.1%}")
    print()

    for style in ("naive", "rubric"):
        print(f"--- {style} failures (grounded=False or relevant=False) ---")
        for r in result["details"][style]:
            if not r["grounded"] or not r["relevant"]:
                print(f"  Q: {r['question']}")
                print(f"     grounded={r['grounded']} relevant={r['relevant']}")
