FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-all.txt requirements-shm.txt requirements-shm-app.txt ./
RUN pip install --no-cache-dir -r requirements-all.txt -r requirements-shm-app.txt

COPY app ./app
COPY src ./src
COPY configs/dataset_lock.json ./configs/dataset_lock.json
COPY outputs/combined/architecture-audit-final/models ./outputs/combined/architecture-audit-final/models
COPY references/Rail_Corrugation/images ./references/Rail_Corrugation/images

ENV PYTHONPATH=/app/src

CMD ["sh", "-c", "streamlit run app/main.py --server.address=0.0.0.0 --server.port=${PORT:-8080} --server.headless=true"]
