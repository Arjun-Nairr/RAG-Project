from app import embedding, generation, vector_store


def retrieve(collection_name: str, question: str, top_k: int = 5) -> list[dict]:
    """Shared by the live /ask endpoint and every eval script - the one
    place that actually calls embed+query, so it's never copy-pasted."""
    query_vector = embedding.embed([question])[0]
    return vector_store.query(collection_name, query_vector, top_k=top_k)


def build_naive_prompt(question: str, chunks: list[str]) -> str:
    # no instructions beyond the raw context+question - baseline to compare
    # a rubric version against, per the plan to measure the difference
    # rather than assume it
    context = "\n\n".join(chunks)
    return f"Context:\n{context}\n\nQuestion: {question}"


RUBRIC = """You are answering questions using only the provided study material. Follow these rules:
1. Base your answer only on the provided context - do not use outside knowledge, even if you know the answer some other way.
2. If the context does not contain enough information to answer, say so clearly instead of guessing.
3. Cite the source document for each claim, in the form [filename].
4. Be concise and direct - don't restate the question or add unnecessary preamble."""


def build_rubric_prompt(question: str, chunks: list[str], sources: list[str]) -> str:
    context = "\n\n".join(
        f"[Source: {source}]\n{chunk}" for chunk, source in zip(chunks, sources)
    )
    return f"{RUBRIC}\n\nContext:\n{context}\n\nQuestion: {question}"


PROMPT_BUILDERS = {"naive", "rubric"}


def build_prompt(question: str, chunks: list[str], sources: list[str], prompt_style: str) -> str:
    if prompt_style not in PROMPT_BUILDERS:
        raise ValueError(f"unknown prompt_style: {prompt_style}")
    if prompt_style == "naive":
        return build_naive_prompt(question, chunks)
    return build_rubric_prompt(question, chunks, sources)


def answer_question(
    study_set_id: str, question: str, top_k: int = 5, prompt_style: str = "naive"
) -> dict:
    results = retrieve(study_set_id, question, top_k)
    chunks = [r["text"] for r in results]
    sources = [r["source"] for r in results]

    prompt = build_prompt(question, chunks, sources, prompt_style)
    answer = generation.generate(prompt)

    return {"answer": answer, "sources": results}
