from app import chunking, embedding, ingestion, study_sets, text_quality, vector_store


def process_study_set(study_set_id: str) -> None:
    study_sets.update_status(study_set_id, "processing")

    try:
        study_set = study_sets.get_study_set(study_set_id)
        directory = study_sets.study_set_dir(study_set_id)

        all_chunks: list[str] = []
        all_sources: list[str] = []
        all_text: list[str] = []

        for filename in study_set["files"]:
            text = ingestion.extract_text_from_path(directory / filename)
            all_text.append(text)
            chunks = chunking.chunk_text(text)
            all_chunks.extend(chunks)
            all_sources.extend([filename] * len(chunks))

        # computed once here, at processing time, and never re-evaluated per
        # question - it reflects the document(s) as a whole, not any one ask
        score = text_quality.score_text("\n\n".join(all_text))
        quality = text_quality.classify(score, len(all_chunks))
        study_sets.set_text_quality(study_set_id, quality, score)

        if all_chunks:
            vectors = embedding.embed(all_chunks, input_type="document")
            vector_store.add_chunks(study_set_id, all_chunks, vectors, all_sources)

        study_sets.update_status(study_set_id, "ready")
    except Exception as e:
        study_sets.update_status(study_set_id, "error", error=str(e))
