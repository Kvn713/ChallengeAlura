from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from .rag_service import RAGSystem, ChatService


class QueryRequest(BaseModel):
    question: str


app = FastAPI(title="RAG Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar RAG (puede tardar unos segundos mientras descarga/crea embeddings)
rag_system = RAGSystem()
chat_service = ChatService(rag_system)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query")
def query(req: QueryRequest):
    result = chat_service.process_question(req.question)
    # `process_question` devuelve un dict con respuesta y fuentes
    return {"respuesta": result.get("respuesta"), "fuentes": result.get("fuentes", [])}
