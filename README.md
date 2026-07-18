# ChallengeAlura

Proyecto dividido en frontend Streamlit y backend FastAPI.

## Estructura

- `app.py`: frontend de Streamlit.
- `backend/main.py`: servidor FastAPI.
- `backend/rag_service.py`: servicio RAG y lógica de consulta.
- `requirements.txt`: dependencias de Python.
- `.devcontainer/devcontainer.json`: configuración del devcontainer.

## Ejecución local

1. Crear un entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Configurar la API key de Cohere en la sesión:

```bash
export COHERE_API_KEY="tu_cohere_api_key"
```

4. Iniciar el backend:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

5. Iniciar el frontend:

```bash
streamlit run app.py
```

6. Abrir el navegador en `http://localhost:8501`.

## Ejecución en devcontainer

La configuración del devcontainer ejecuta automáticamente:

- instalación de dependencias desde `requirements.txt`
- arranque del servidor FastAPI en `http://localhost:8000`
- arranque de Streamlit en `http://localhost:8501`

### Requisitos del devcontainer

- Archivo `.devcontainer/devcontainer.json`

### Comandos relevantes

- `updateContentCommand`: instala dependencias de Python.
- `postAttachCommand`: ejecuta `uvicorn backend.main:app` y `streamlit run app.py`.

## Deploy en Streamlit Cloud

Para usar este proyecto en Streamlit Cloud, configura los siguientes Secrets:

- `COHERE_API_KEY`: tu clave de Cohere.
- `BACKEND_URL`: si usas un backend externo, pon la URL; si quieres modo local en Streamlit Cloud, déjalo vacío o pon `local`.

> Nota: si el backend corre localmente dentro del mismo contenedor, el frontend usa `BACKEND_URL=http://localhost:8000`.

## Notas adicionales

- El backend FastAPI expone:
  - `GET /health`
  - `POST /query`

- El frontend Streamlit llama a `/query` para obtener las respuestas.
