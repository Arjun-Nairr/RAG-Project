from pathlib import Path

from pypdf import PdfReader

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "pdfs"


def list_documents() -> list[str]:
    return sorted(p.name for p in DATA_DIR.glob("*.pdf"))


def extract_text_from_path(path: Path) -> str:
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def extract_text(filename: str) -> str:
    return extract_text_from_path(DATA_DIR / filename)
