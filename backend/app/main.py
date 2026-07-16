import shutil

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import processing, qa, study_sets


class AskRequest(BaseModel):
    question: str

app = FastAPI(title="RAG Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
    return qa.answer_question(study_set_id, request.question)
