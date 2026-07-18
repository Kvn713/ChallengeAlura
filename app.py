import streamlit as st
import requests
import os
import time
import random
from typing import Dict, List, Optional

# CONFIG
class Config:
    PAGE_TITLE = "Asistente de Reembolsos"
    PAGE_ICON = "💬"
    LAYOUT = "centered"
    WELCOME_MESSAGE = "¡Hola! Pregunta sobre políticas, plazos y procesos de reembolso"
    DEFAULT_SOURCE = "Atención al Cliente"
    # Si BACKEND_URL está vacío o es 'local', el app usará el RAG en proceso (modo local)
    BACKEND_URL = os.getenv("BACKEND_URL", "")


class Message:
    def __init__(self, rol: str, contenido: str, fuentes: Optional[List[str]] = None):
        self.rol = rol
        self.contenido = contenido
        self.fuentes = fuentes or []

    def to_dict(self) -> Dict:
        return {"rol": self.rol, "contenido": self.contenido, "fuentes": self.fuentes}


def configure_app():
    st.set_page_config(page_title=Config.PAGE_TITLE, page_icon=Config.PAGE_ICON, layout=Config.LAYOUT)


def _is_local_host_url(url: str) -> bool:
    if not url:
        return False
    low = url.lower()
    return "localhost" in low or "127.0.0.1" in low or "::1" in low


def fetch_backend_health(url: str) -> Dict:
    try:
        resp = requests.get(f"{url}/health", timeout=3)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Inicialización perezosa del servicio local (usa backend/rag_service)
_LOCAL_MODE = not Config.BACKEND_URL or Config.BACKEND_URL.lower() == "local"


@st.cache_resource
def _init_local_service():
    from backend.rag_service import RAGSystem, ChatService
    rag = RAGSystem()
    return ChatService(rag)


def get_local_chat_service():
    try:
        return _init_local_service()
    except Exception as e:
        st.session_state.setdefault("local_init_error", str(e))
        return None


class SessionManager:
    @staticmethod
    def initialize():
        if "mensajes" not in st.session_state:
            st.session_state.mensajes = []
        if "backend_health" not in st.session_state:
            # Si estamos en modo local, inicializamos RAG en proceso
            if _LOCAL_MODE:
                st.session_state.backend_health = {"status": "local_not_initialized"}
                try:
                    with st.spinner("Inicializando servicio local..."):
                        svc = get_local_chat_service()
                        if svc is None:
                            st.session_state.backend_health = {"status": "error", "error": st.session_state.get("local_init_error", "Error desconocido")}
                            st.session_state.use_local_fallback = True
                        else:
                            st.session_state.backend_health = {"status": "ok", "backend": "local"}
                            st.session_state.use_local_fallback = True
                except Exception as e:
                    st.session_state.backend_health = {"status": "error", "error": str(e)}
                    st.session_state.use_local_fallback = True
            else:
                # Si BACKEND_URL apunta a localhost, omitimos la comprobación remota para evitar errores ruidosos
                if _is_local_host_url(Config.BACKEND_URL):
                    st.session_state.backend_health = {"status": "skipped_local", "backend": "localhost"}
                    # Intentamos inicializar el servicio local como fallback silencioso
                    try:
                        svc = get_local_chat_service()
                        if svc is None:
                            st.session_state.backend_health = {"status": "error", "error": st.session_state.get("local_init_error", "Error desconocido")}
                            st.session_state.use_local_fallback = False
                        else:
                            st.session_state.backend_health = {"status": "ok", "backend": "local_fallback"}
                            st.session_state.use_local_fallback = True
                    except Exception as e:
                        st.session_state.backend_health = {"status": "error", "error": str(e)}
                        st.session_state.use_local_fallback = False
                else:
                    # Intentar conectar al backend remoto; si falla, intentar fallback local
                    health = fetch_backend_health(Config.BACKEND_URL)
                    st.session_state.backend_health = health
                    if health.get("status") == "error":
                        try:
                            with st.spinner("Backend no disponible — intentando inicializar RAG local..."):
                                svc = get_local_chat_service()
                                if svc is None:
                                    st.session_state.backend_health = {"status": "error", "error": st.session_state.get("local_init_error", "Error desconocido")}
                                    st.session_state.use_local_fallback = False
                                else:
                                    st.session_state.backend_health = {"status": "ok", "backend": "local_fallback"}
                                    st.session_state.use_local_fallback = True
                        except Exception as e:
                            st.session_state.backend_health = {"status": "error", "error": str(e)}
                            st.session_state.use_local_fallback = False
                    else:
                        st.session_state.use_local_fallback = False

    @staticmethod
    def add_message(message: Message):
        st.session_state.mensajes.append(message.to_dict())

    @staticmethod
    def get_messages():
        return st.session_state.mensajes

    @staticmethod
    def clear():
        st.session_state.mensajes = []


def call_backend(question: str) -> Dict:
    # Si estamos en modo local o se activó fallback local, usar servicio local
    if _LOCAL_MODE or st.session_state.get("use_local_fallback", False):
        service = get_local_chat_service()
        if service is None:
            # servicio no inicializado o falló
            err = st.session_state.get("local_init_error", "Servicio local no disponible")
            return {"respuesta": "Servicio local no disponible.", "fuentes": [err]}
        try:
            res = service.process_question(question)
            if isinstance(res, dict):
                return {"respuesta": res.get("respuesta"), "fuentes": res.get("fuentes", [])}
            return {"respuesta": getattr(res, 'respuesta', str(res)), "fuentes": getattr(res, 'fuentes', [])}
        except Exception as e:
            return {"respuesta": "Error procesando localmente.", "fuentes": [str(e)]}

    try:
        resp = requests.post(f"{Config.BACKEND_URL}/query", json={"question": question}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"respuesta": "Error comunicándose con el backend.", "fuentes": [str(e)]}


class ChatUI:
    def __init__(self):
        self.quick_questions = [
            ("📄 Docs", "¿Qué documentos necesito para el reembolso?"),
            ("✅ Elegible", "¿Qué productos son elegibles para reembolso?"),
            ("📝 Proceso", "¿Cómo solicito un reembolso?"),
            ("⏰ Plazos", "¿Cuál es el plazo máximo para solicitar un reembolso?"),
            ("⏳ Tiempo", "¿Cuánto tiempo tarda en procesarse un reembolso?"),
            ("❌ Cancelar", "¿Puedo cancelar un reembolso ya solicitado?")
        ]

    def render_header(self):
        self._set_styles()
        st.title(f"{Config.PAGE_ICON} {Config.PAGE_TITLE}")
        st.caption(Config.WELCOME_MESSAGE)
        # Si estamos en modo local, permitir inicializar el servicio desde la UI
        if _LOCAL_MODE:
            status = st.session_state.get("backend_health", {})
            if status.get("status") == "local_not_initialized":
                if st.button("🔌 Inicializar servicio local"):
                    with st.spinner("Inicializando servicio local..."):
                        svc = get_local_chat_service()
                        if svc is None:
                            st.session_state.backend_health = {"status": "error", "error": st.session_state.get("local_init_error", "Error desconocido")}
                            st.error("❌ Error inicializando servicio local")
                        else:
                            st.session_state.backend_health = {"status": "ok"}
                            st.success("✅ Servicio local inicializado")

        with st.expander("ℹ️ Estado del sistema"):
            health = st.session_state.backend_health
            if health.get("status") == "ok":
                if health.get("backend") == "local_fallback" or health.get("backend") == "local":
                    st.success("✅ Servicio local activo (fallback)")
                else:
                    st.success("✅ Backend disponible")
            elif health.get("status") == "error":
                # Mostrar mensaje conciso sin el stack/trace de errores de conexión
                err = health.get('error', '')
                if err and ("localhost" in err or "127.0.0.1" in err):
                    st.warning("⚠️ No se pudo conectar con el backend remoto (host local). Se omitió la comprobación para localhost.")
                else:
                    st.warning(f"⚠️ No se pudo conectar con el backend: {err}")
            elif health.get("status") == "local_not_initialized":
                st.info("ℹ️ Servicio local no inicializado. Pulsa 'Inicializar servicio local' para cargar los documentos.")
            else:
                st.warning("⚠️ Backend no responde correctamente")

    def _set_styles(self):
        st.markdown(
            """
            <style>
                .css-1v0mbdj e1fqkh3o2 {background: #151c2d;}
                .stApp {
                    background: linear-gradient(180deg, #0d1322 0%, #1b233a 100%);
                    color: #e8eef8;
                }
                .stButton>button {
                    background-color: #6b7280; /* gris */
                    color: #ffffff;
                    border-radius: 12px;
                    border: none;
                    padding: 12px 16px;
                    font-weight: 600;
                }
                .stButton>button:hover {
                    background-color: #4b5563; /* gris oscuro al pasar */
                }
                .stButton>button:focus {
                    outline: 2px solid #9ca3af; /* contorno gris claro */
                }
                .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
                    color: #cfd9ff;
                }
                .streamlit-expanderHeader {
                    background-color: #192841;
                    border-radius: 10px;
                    color: #edf2ff;
                }
                .stExpanderHeader {
                    color: #edf2ff;
                }
                .stDivider {
                    border-top: 1px solid #2f3b56;
                }
                .message-user {
                    background: #1e2a44;
                    border: 1px solid #38558b;
                    border-radius: 16px;
                    padding: 14px;
                    margin-bottom: 12px;
                    color: #e8eef8;
                }
                .message-assistant {
                    background: #121924;
                    border: 1px solid #2f3d5f;
                    border-radius: 16px;
                    padding: 14px;
                    margin-bottom: 12px;
                    color: #dbe6ff;
                }
                .message-user p, .message-assistant p {
                    margin: 6px 0 0;
                    line-height: 1.6;
                }
                .stTextInput>div>div>input, .stTextArea>div>div>textarea {
                    background: #121924;
                    color: #e8eef8;
                    border: 1px solid #2f3d5f;
                }
                .dialog-window {
                    background: rgba(18,25,36,0.6);
                    border: 1px solid #2f3d5f;
                    border-radius: 12px;
                    padding: 12px;
                    height: 60vh;
                    overflow-y: auto;
                }
                .dialog-window::-webkit-scrollbar { width: 8px; }
                .dialog-window::-webkit-scrollbar-thumb { background: #2f3d5f; border-radius: 8px; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def render_dialog_window(self):
        msgs = SessionManager.get_messages()
        # Construir HTML de todos los mensajes para un único contenedor scrollable
        html = ['<div class="dialog-window">']
        for msg in msgs:
            role = msg.get("rol", "").lower()
            style_class = "message-user" if role == "user" else "message-assistant"
            contenido = msg.get('contenido', '')
            html.append(f"<div class=\"{style_class}\"><strong>{msg.get('rol','').title()}:</strong><p>{contenido}</p>")
            fuentes = msg.get('fuentes', []) or []
            if fuentes:
                html.append('<div style="margin-top:8px;padding-left:8px;color:#cdd9ff">')
                html.append('<strong>Fuentes:</strong><ul style="margin:6px 0 0 18px;">')
                for f in fuentes:
                    html.append(f"<li>{f}</li>")
                html.append('</ul></div>')
            html.append('</div>')
        html.append('</div>')
        st.markdown('\n'.join(html), unsafe_allow_html=True)

    def render_quick_questions(self):
        st.markdown("---")
        st.caption("⚡ Preguntas rápidas:")
        # Render botones en columna vertical (uno debajo del otro)
        for idx, (label, question) in enumerate(self.quick_questions):
            if st.button(label, key=f"quick_{idx}"):
                self._handle_question(question)
            # pequeño separador
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    def render_chat_input(self):
        question = st.chat_input("Escribe tu pregunta sobre reembolsos...")
        if question:
            self._handle_question(question)

    def render_clear_button(self):
        st.divider()
        if st.button("🗑️ Limpiar conversación"):
            SessionManager.clear()

    def _handle_question(self, question: str):
        user_message = Message(rol="user", contenido=question)
        SessionManager.add_message(user_message)
        with st.spinner("🤔 Analizando documentos..."):
            result = call_backend(question)
        respuesta = result.get("respuesta", "No hay respuesta")
        fuentes = result.get("fuentes", [Config.DEFAULT_SOURCE])
        assistant_message = Message(rol="assistant", contenido=respuesta, fuentes=fuentes)
        SessionManager.add_message(assistant_message)


def main():
    configure_app()
    SessionManager.initialize()
    ui = ChatUI()
    ui.render_header()

    # Layout: izquierda 1/4 (botones), derecha 3/4 (conversación)
    left_col, right_col = st.columns([1, 3])

    with left_col:
        ui.render_quick_questions()
        ui.render_clear_button()

    with right_col:
        # Input arriba, cuadro de diálogo (scrollable) debajo
        ui.render_chat_input()
        ui.render_dialog_window()


if __name__ == "__main__":
    main()