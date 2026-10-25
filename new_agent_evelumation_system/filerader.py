from pathlib import Path
from typing import List

from langchain_core.documents import Document
from pypdf import PdfReader


def read_text_from_pdf(pdf_path: str) -> str:
    """Read and return the text content of a PDF file."""
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found at path: {pdf_path}")

    reader = PdfReader(str(path))
    text_parts = [page.extract_text() or "" for page in reader.pages]

    return "\n".join(text_parts)


def read_multiple_pdf(pdf_paths: List[str | Path]) -> List[Document]:
    docs: List[Document] = []
    for path in pdf_paths:
        path_object = path
        text = read_text_from_pdf(path_object)
        docs.append(Document(page_content=text, metadata={"source": str(path_object)}))
    return docs
