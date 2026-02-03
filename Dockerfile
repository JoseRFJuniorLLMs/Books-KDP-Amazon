FROM python:3.11-slim

WORKDIR /app

# Instala dependencias do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements primeiro (cache de camadas)
COPY requirements_cloud.txt .
RUN pip install --no-cache-dir -r requirements_cloud.txt

# Copia codigo fonte
COPY src/ ./src/
COPY templates/ ./templates/
COPY config/ ./config/

# Variaveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Comando padrao: executa o pipeline completo
CMD ["python", "-m", "src.pipeline.orchestrator", "--full", "--download-limit", "100"]
