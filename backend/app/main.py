import json
import os
import shutil
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app import generation, processing, qa, storage, study_sets


class AskRequest(BaseModel):
    question: str

app = FastAPI(title="RAG Pipeline API")

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "demo"
PDFS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "pdfs"
# key -> (source path, display name, one-line description shown in the picker)
DEMO_SPECS = {
    "clear": (PDFS_DIR / "attention_is_all_you_need.pdf", "Clear document", "Clean, well-grounded answers"),
    "semi_clear": (DEMO_DIR / "semi_clear.pdf", "Semi-clear document", "See the quality warning in action"),
    "unreadable": (DEMO_DIR / "unreadable.pdf", "Unreadable document", "See the hard block in action"),
}


@app.on_event("startup")
def _ensure_db():
    # idempotent; degrade gracefully if the DB is unreachable so the app still
    # serves (asking works, history just won't persist)
    try:
        storage.init_db()
    except Exception as e:
        print(f"[warning] question-history DB unavailable at startup: {e}")

# comma-separated - lets one deployment allow both a local dev frontend and
# the real deployed one, e.g. "http://localhost:5173,https://my-app.vercel.app"
_origins = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/study-sets")
async def upload_study_set(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    files: list[UploadFile] = File(...),
):
    non_pdf = [f.filename for f in files if not f.filename.lower().endswith(".pdf")]
    if non_pdf:
        raise HTTPException(status_code=400, detail=f"only PDFs are supported: {non_pdf}")

    filenames = [f.filename for f in files]
    study_set = study_sets.create_study_set(name, filenames)

    target_dir = study_sets.study_set_dir(study_set["id"])
    for f in files:
        with open(target_dir / f.filename, "wb") as out:
            shutil.copyfileobj(f.file, out)

    background_tasks.add_task(processing.process_study_set, study_set["id"])

    return study_set


@app.get("/study-sets")
def get_study_sets():
    return {"study_sets": study_sets.list_study_sets()}


@app.get("/demo")
def get_demo_specs():
    return {
        "demos": [
            {"key": key, "name": name, "description": description}
            for key, (_source_path, name, description) in DEMO_SPECS.items()
        ]
    }


@app.post("/demo/{key}")
def create_demo_study_set(key: str, background_tasks: BackgroundTasks):
    spec = DEMO_SPECS.get(key)
    if spec is None:
        raise HTTPException(status_code=404, detail="unknown demo")

    source_path, name, _description = spec
    filename = source_path.name
    study_set = study_sets.create_study_set(name, [filename])

    target_dir = study_sets.study_set_dir(study_set["id"])
    shutil.copyfile(source_path, target_dir / filename)

    background_tasks.add_task(processing.process_study_set, study_set["id"])

    return study_set


@app.get("/study-sets/{study_set_id}")
def get_study_set(study_set_id: str):
    study_set = study_sets.get_study_set(study_set_id)
    if study_set is None:
        raise HTTPException(status_code=404, detail="study set not found")
    return study_set


@app.post("/study-sets/{study_set_id}/ask")
def ask_question(study_set_id: str, request: AskRequest):
    study_set = study_sets.get_study_set(study_set_id)
    if study_set is None:
        raise HTTPException(status_code=404, detail="study set not found")
    if study_set["status"] != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"study set is not ready yet (status: {study_set['status']})",
        )
    if study_set.get("text_quality") == "unreadable":
        raise HTTPException(
            status_code=400,
            detail=(
                "This document's text couldn't be read clearly (common with scanned "
                "images or handwriting with no usable text layer), so there's nothing "
                "to search or answer from."
            ),
        )

    # stream the answer as NDJSON: one {sources} line, then many {delta} lines,
    # then a {done} line. Retrieval runs first (so sources are known up front),
    # then tokens are forwarded live, then the assembled answer is persisted.
    def event_stream():
        results = qa.retrieve(study_set_id, request.question)
        yield json.dumps({"type": "sources", "sources": results}) + "\n"

        chunks = [r["text"] for r in results]
        sources = [r["source"] for r in results]
        prompt = qa.build_prompt(request.question, chunks, sources, "rubric")

        parts = []
        for delta in generation.generate_stream(prompt):
            parts.append(delta)
            yield json.dumps({"type": "delta", "text": delta}) + "\n"

        answer = "".join(parts)
        # best-effort persist - never fail the response over a storage hiccup
        try:
            storage.save_question(study_set_id, request.question, answer, results)
        except Exception as e:
            print(f"[warning] failed to save question history: {e}")

        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.get("/study-sets/{study_set_id}/history")
def get_history(study_set_id: str):
    return {"history": storage.get_history(study_set_id)}


@app.get("/study-sets/{study_set_id}/files/{filename}")
def get_file(study_set_id: str, filename: str):
    study_set = study_sets.get_study_set(study_set_id)
    if study_set is None:
        raise HTTPException(status_code=404, detail="study set not found")
    # only serve filenames that belong to this study set - blocks path traversal
    if filename not in study_set["files"]:
        raise HTTPException(status_code=404, detail="file not in this study set")
    path = study_sets.study_set_dir(study_set_id) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="file missing on disk")
    # inline so the browser renders it in the iframe instead of downloading
    return FileResponse(path, media_type="application/pdf", content_disposition_type="inline")
