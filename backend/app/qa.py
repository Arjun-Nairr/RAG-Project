from app import embedding, generation, vector_store


def build_prompt(question: str, chunks: list[str]) -> str:
    # deliberately naive/no rubric for now - baseline to compare a rubric
    # version against later, per the plan to measure the difference rather
    # than assume it
    context = "\n\n".join(chunks)
    return f"Context:\n{context}\n\nQuestion: {question}"


def answer_question(study_set_id: str, question: str, top_k: int = 5) -> dict:
    query_vector = embedding.embed([question])[0]
    results = vector_store.query(study_set_id, query_vector, top_k=top_k)
    chunks = [r["text"] for r in results]

    prompt = build_prompt(question, chunks)
    answer = generation.generate(prompt)

    return {"answer": answer, "sources": results}
