from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional


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

rag_system = None
chat_service = None
rag_error: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    global rag_system, chat_service, rag_error
    try:
        from .rag_service import RAGSystem, ChatService
        rag_system = RAGSystem()
        chat_service = ChatService(rag_system)
        rag_error = None
        print("✅ RAG backend inicializado correctamente")
    except Exception as e:
        rag_system = None
        chat_service = None
        rag_error = str(e)
        print(f"❌ Error inicializando RAG en startup: {rag_error}")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "rag_ready": chat_service is not None,
        "error": rag_error,
    }


@app.post("/query")
def query(req: QueryRequest):
    if chat_service is None:
        raise HTTPException(status_code=503, detail="RAG service is not available.")
    result = chat_service.process_question(req.question)
    return {"respuesta": result.get("respuesta"), "fuentes": result.get("fuentes", [])}
