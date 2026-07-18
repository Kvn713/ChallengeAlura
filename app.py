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
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


class Message:
    def __init__(self, rol: str, contenido: str, fuentes: Optional[List[str]] = None):
        self.rol = rol
        self.contenido = contenido
        self.fuentes = fuentes or []

    def to_dict(self) -> Dict:
        return {"rol": self.rol, "contenido": self.contenido, "fuentes": self.fuentes}


def configure_app():
    st.set_page_config(page_title=Config.PAGE_TITLE, page_icon=Config.PAGE_ICON, layout=Config.LAYOUT)


class SessionManager:
    @staticmethod
    def initialize():
        if "mensajes" not in st.session_state:
            st.session_state.mensajes = []

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
    try:
        resp = requests.post(f"{Config.BACKEND_URL}/query", json={"question": question}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"respuesta": "Error comunicándose con el backend.", "fuentes": [str(e)]}


class ChatUI:
    def __init__(self):
        self.quick_questions = [
            ("⏰ Plazos", "¿Cuál es el plazo máximo para solicitar un reembolso?"),
            ("📝 Proceso", "¿Cómo solicito un reembolso?"),
            ("⏳ Tiempo", "¿Cuánto tiempo tarda en procesarse un reembolso?"),
            ("✅ Elegible", "¿Qué productos son elegibles para reembolso?"),
            ("❌ Cancelar", "¿Puedo cancelar un reembolso ya solicitado?"),
            ("📄 Docs", "¿Qué documentos necesito para el reembolso?")
        ]

    def render_header(self):
        st.title(f"{Config.PAGE_ICON} {Config.PAGE_TITLE}")
        st.caption(Config.WELCOME_MESSAGE)
        with st.expander("ℹ️ Estado del sistema"):
            try:
                health = requests.get(f"{Config.BACKEND_URL}/health", timeout=3).json()
                if health.get("status") == "ok":
                    st.success("✅ Backend disponible")
                else:
                    st.warning("⚠️ Backend no responde correctamente")
            except Exception:
                st.warning("⚠️ No se pudo conectar con el backend")

    def render_messages(self):
        for msg in SessionManager.get_messages():
            with st.chat_message(msg["rol"]):
                st.markdown(msg["contenido"])
                if msg.get("fuentes"):
                    with st.expander("📚 Fuentes"):
                        for f in msg.get("fuentes", []):
                            st.write(f"• {f}")

    def render_quick_questions(self):
        st.markdown("---")
        st.caption("⚡ Preguntas rápidas:")
        cols = st.columns(3)
        for idx, (label, question) in enumerate(self.quick_questions):
            col = cols[idx % 3]
            with col:
                if st.button(label, key=f"quick_{idx}"):
                    self._handle_question(question)

    def render_chat_input(self):
        question = st.chat_input("Escribe tu pregunta sobre reembolsos...")
        if question:
            self._handle_question(question)

    def render_clear_button(self):
        st.divider()
        if st.button("🗑️ Limpiar conversación"):
            SessionManager.clear()
            st.experimental_rerun()

    def _handle_question(self, question: str):
        user_message = Message(rol="user", contenido=question)
        SessionManager.add_message(user_message)
        with st.spinner("🤔 Analizando documentos..."):
            result = call_backend(question)
        respuesta = result.get("respuesta", "No hay respuesta")
        fuentes = result.get("fuentes", [Config.DEFAULT_SOURCE])
        assistant_message = Message(rol="assistant", contenido=respuesta, fuentes=fuentes)
        SessionManager.add_message(assistant_message)
        st.experimental_rerun()


def main():
    configure_app()
    SessionManager.initialize()
    ui = ChatUI()
    ui.render_header()
    ui.render_messages()
    ui.render_quick_questions()
    ui.render_chat_input()
    ui.render_clear_button()


if __name__ == "__main__":
    main()