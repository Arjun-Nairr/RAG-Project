import json

from app import generation

JUDGE_PROMPT_TEMPLATE = """You are evaluating whether an AI-generated answer is grounded in the provided context and relevant to the question. Respond with ONLY a JSON object, no other text, no markdown formatting.

Context:
{context}

Question: {question}

Answer to evaluate:
{answer}

Evaluate:
1. "grounded": true if every factual claim in the answer is supported by the context above; false if the answer includes information not present in the context, or makes claims the context doesn't support.
2. "relevant": true if the answer actually addresses the question asked; false if it's off-topic, evasive, or doesn't engage with the question.

Respond with exactly this JSON format: {{"grounded": true, "relevant": true}}"""


def judge(question: str, context: str, answer: str) -> dict:
    prompt = JUDGE_PROMPT_TEMPLATE.format(context=context, question=question, answer=answer)
    raw = generation.generate(prompt)

    # LLM judges sometimes wrap JSON in prose/markdown despite instructions -
    # extract the first {...} block rather than assuming a clean response
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"judge did not return JSON: {raw!r}")

    result = json.loads(raw[start : end + 1])
    return {"grounded": bool(result["grounded"]), "relevant": bool(result["relevant"])}
