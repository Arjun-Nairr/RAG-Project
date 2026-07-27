from pathlib import Path

from pypdf import PdfReader


def extract_text_from_path(path: Path) -> str:
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)
