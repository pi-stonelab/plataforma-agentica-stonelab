FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY agentes agentes
COPY backend/app backend/app
COPY ferramentas ferramentas
COPY frontend frontend
COPY mock mock
COPY seguranca seguranca

RUN useradd --create-home --uid 10001 stonelab \
    && mkdir dados_locais \
    && chown stonelab:stonelab dados_locais

USER stonelab
WORKDIR /app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
