from app import chunking, embedding, ingestion, study_sets, vector_store


def process_study_set(study_set_id: str) -> None:
    study_sets.update_status(study_set_id, "processing")

    try:
        study_set = study_sets.get_study_set(study_set_id)
        directory = study_sets.study_set_dir(study_set_id)

        all_chunks: list[str] = []
        all_sources: list[str] = []

        for filename in study_set["files"]:
            text = ingestion.extract_text_from_path(directory / filename)
            chunks = chunking.chunk_text(text)
            all_chunks.extend(chunks)
            all_sources.extend([filename] * len(chunks))

        vectors = embedding.embed(all_chunks)
        vector_store.add_chunks(study_set_id, all_chunks, vectors, all_sources)

        study_sets.update_status(study_set_id, "ready")
    except Exception as e:
        study_sets.update_status(study_set_id, "error", error=str(e))
