"""
Generate naive + rubric answers for all 25 eval questions (no judge call -
judging happens externally) and export as a readable Markdown file.

Usage: venv/Scripts/python.exe -m evals.export_generation_samples [collection_name] [top_k]
"""

import sys
import time

from app import generation, qa
from evals.eval_set import EVAL_QUESTIONS

SECONDS_BETWEEN_CALLS = 7  # conservative: ~8.5 req/min, well under 30 req/min
                           # and comfortably under 12k tokens/min even for
                           # larger context+rubric prompts


def run(collection_name: str, top_k: int = 5) -> list[dict]:
    records = []
    total = len(EVAL_QUESTIONS) * 2
    done = 0

    for item in EVAL_QUESTIONS:
        question = item["question"]
        results = qa.retrieve(collection_name, question, top_k)
        chunks = [r["text"] for r in results]
        sources = [r["source"] for r in results]
        context = "\n\n".join(f"[{s}]\n{c}" for c, s in zip(chunks, sources))

        naive_prompt = qa.build_prompt(question, chunks, sources, "naive")
        naive_answer = generation.generate(naive_prompt)
        done += 1
        print(f"[{done}/{total}]  naive | {question[:60]}", flush=True)
        time.sleep(SECONDS_BETWEEN_CALLS)

        rubric_prompt = qa.build_prompt(question, chunks, sources, "rubric")
        rubric_answer = generation.generate(rubric_prompt)
        done += 1
        print(f"[{done}/{total}] rubric | {question[:60]}", flush=True)
        time.sleep(SECONDS_BETWEEN_CALLS)

        records.append(
            {
                "question": question,
                "expected_source": item["expected_source"],
                "context": context,
                "naive_answer": naive_answer,
                "rubric_answer": rubric_answer,
            }
        )

    return records


def to_markdown(records: list[dict]) -> str:
    lines = [
        "# RAG generation samples — naive vs. rubric prompt",
        "",
        "For each question: the retrieved context actually used, then the answer produced by "
        "the naive prompt (context + question, no instructions) and the answer produced by the "
        "rubric prompt (grounding + \"say I don't know\" + cite source + be concise).",
        "",
        "Please review each pair and judge:",
        "1. **Grounded** — is every claim in the answer actually supported by the context shown? "
        "(false if it states something the context doesn't support, or pulls in outside knowledge)",
        "2. **Relevant** — does the answer actually address the question asked?",
        "",
        "Then suggest concrete improvements to the rubric's wording based on any failure patterns you see.",
        "",
        "---",
        "",
    ]
    for i, r in enumerate(records, 1):
        lines.append(f"## {i}. {r['question']}")
        lines.append(f"*Expected source: `{r['expected_source']}`*")
        lines.append("")
        lines.append("<details><summary>Retrieved context</summary>")
        lines.append("")
        lines.append(r["context"])
        lines.append("")
        lines.append("</details>")
        lines.append("")
        lines.append("**Naive answer:**")
        lines.append(r["naive_answer"])
        lines.append("")
        lines.append("**Rubric answer:**")
        lines.append(r["rubric_answer"])
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    collection = sys.argv[1] if len(sys.argv) > 1 else "test_corpus"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    records = run(collection, k)
    markdown = to_markdown(records)

    out_path = "../data/generation_samples_for_cowork.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"\nWrote {len(records)} question pairs to {out_path}")
