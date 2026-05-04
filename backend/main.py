from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from pipeline import agents
from schemas import VerificationReport

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOCUMENTS_DIR = Path(__file__).parent / "documents"


def load_documents() -> dict[str, str]:
    documents = {}
    for file_path in DOCUMENTS_DIR.glob("*.txt"):
        documents[file_path.stem] = file_path.read_text()
    return documents


@app.post("/analyze")
async def analyze() -> dict[str, VerificationReport]:
    documents = load_documents()
    return {"report": agents.invoke(documents)}
