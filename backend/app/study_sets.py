import uuid
from pathlib import Path

STUDY_SETS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "study_sets"

# In-memory only — cleared on server restart (ephemeral, by design for now).
STUDY_SETS: dict[str, dict] = {}


def create_study_set(name: str, filenames: list[str]) -> dict:
    study_set_id = str(uuid.uuid4())
    study_set_dir = STUDY_SETS_DIR / study_set_id
    study_set_dir.mkdir(parents=True, exist_ok=True)

    study_set = {
        "id": study_set_id,
        "name": name,
        "files": filenames,
        "status": "uploaded",
    }
    STUDY_SETS[study_set_id] = study_set
    return study_set


def study_set_dir(study_set_id: str) -> Path:
    return STUDY_SETS_DIR / study_set_id


def get_study_set(study_set_id: str) -> dict | None:
    return STUDY_SETS.get(study_set_id)


def update_status(study_set_id: str, status: str, error: str | None = None) -> None:
    study_set = STUDY_SETS[study_set_id]
    study_set["status"] = status
    if error is not None:
        study_set["error"] = error


def list_study_sets() -> list[dict]:
    return list(STUDY_SETS.values())
