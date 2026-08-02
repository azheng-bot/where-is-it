FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib
COPY services /app/services
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "fastapi>=0.115,<1.0" "uvicorn[standard]>=0.30,<1.0" "pydantic>=2,<3" "faster-whisper>=1.1,<2.0" nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "/app/services/asr", "--host", "0.0.0.0", "--port", "8006"]