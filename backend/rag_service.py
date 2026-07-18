import os
import time
import random
from typing import Dict, List
from tempfile import NamedTemporaryFile
import requests
from dotenv import load_dotenv

from langchain_cohere import CohereEmbeddings, ChatCohere
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain


# CARGA DE VARIABLES DE ENTORNO
load_dotenv()
COHERE_API_KEY = os.getenv("COHERE_API_KEY")


class Config:
    PDF_URL = "https://cdn1.gnarususercontent.com.br/documents/6/internal/b9abdeaf-ffcb-46c4-8e1b-16935a594875.pdf"
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50
    SCORE_THRESHOLD = 0.3
    K_RETRIEVAL = 4


class RAGSystem:
    def __init__(self):
        self.vectorstore = None
        self.retriever = None
        self.document_chain = None
        self._initialize_rag()

    def _initialize_rag(self):
        try:
            docs = self._load_pdf()
            if docs:
                chunks = self._create_chunks(docs)
                self._create_vectorstore(chunks)
                self._configure_retriever()
                self._configure_document_chain()
                print("✅ Sistema RAG inicializado correctamente")
            else:
                print("❌ No se pudo cargar el PDF, modo fallback")
        except Exception as e:
            print(f"❌ Error inicializando RAG: {e}")
            self.vectorstore = None

    def _load_pdf(self) -> List:
        try:
            response = requests.get(Config.PDF_URL)
            response.raise_for_status()
            with NamedTemporaryFile(delete=True, suffix='.pdf') as temp_file:
                temp_file.write(response.content)
                temp_file.flush()
                loader = PyMuPDFLoader(temp_file.name)
                docs = loader.load()
            print(f"✅ PDF procesado: {len(docs)} páginas")
            return docs
        except Exception as e:
            print(f"❌ Error cargando PDF: {e}")
            return []

    def _create_chunks(self, docs) -> List:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = text_splitter.split_documents(docs)
        print(f"✂️ Total de chunks: {len(chunks)}")
        return chunks

    def _create_vectorstore(self, chunks):
        embeddings = CohereEmbeddings(
            model="embed-multilingual-v3.0",
            cohere_api_key=COHERE_API_KEY
        )
        self.vectorstore = FAISS.from_documents(chunks, embeddings)
        print("✅ Vectorstore creado")

    def _configure_retriever(self):
        if self.vectorstore:
            self.retriever = self.vectorstore.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={
                    "score_threshold": Config.SCORE_THRESHOLD,
                    "k": Config.K_RETRIEVAL
                }
            )
            print("✅ Retriever configurado")

    def _configure_document_chain(self):
        prompt_rag = ChatPromptTemplate([
            ("system",
                """Eres el especialista en Políticas de atención al cliente, cambios y devoluciones de la empresa Mercado Central de las 24H.
                Responde siempre utilizando los conocimientos de las bases de datos pasadas a ti.
                Si no hay información sobre la pregunta en los datos, responde solo 'No lo sé'.
                """
            ),
            ("human", "Contexto: {context}\nPregunta del empleado: {input}")
        ])
        llm = ChatCohere(
            model="command-a-03-2025",
            cohere_api_key=COHERE_API_KEY,
            temperature=0.7
        )
        self.document_chain = create_stuff_documents_chain(llm, prompt_rag)
        print("✅ Document chain configurada")

    def query(self, pregunta: str) -> Dict:
        if not self.retriever or not self.document_chain:
            return {"respuesta": "No tengo información específica sobre eso. Contacta con atención al cliente.", "fuentes": ["Atención al Cliente"]}
        try:
            documentos_relacionados = self.retriever.invoke(pregunta)
            if not documentos_relacionados:
                return {"respuesta": "No lo sé", "fuentes": ["No se encontraron documentos relevantes"]}
            answer = self.document_chain.invoke({"input": pregunta, "context": documentos_relacionados})
            if answer.rstrip(".!?") == "No lo sé":
                return {"respuesta": "No lo sé", "fuentes": ["No se encontró información relevante en los documentos"]}
            fuentes = []
            for doc in documentos_relacionados[:3]:
                source = doc.metadata.get('source', 'Documento')
                page = doc.metadata.get('page', '')
                if page:
                    fuentes.append(f"{source} - Página {page}")
                else:
                    fuentes.append(source)
            return {"respuesta": answer, "fuentes": fuentes if fuentes else ["Política de Reembolsos - Documento oficial"]}
        except Exception as e:
            print(f"❌ Error en consulta RAG: {e}")
            return {"respuesta": "Ocurrió un error al procesar tu pregunta.", "fuentes": ["Error en el sistema"]}


class ChatService:
    def __init__(self, rag_system: RAGSystem):
        self.rag_system = rag_system

    def process_question(self, question: str) -> Dict:
        time.sleep(random.uniform(0.5, 1.0))
        return self.rag_system.query(question)
