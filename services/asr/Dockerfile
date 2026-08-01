FROM python:3.13-slim
WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir "fastapi>=0.115,<1.0" "uvicorn[standard]>=0.30,<1.0" "pydantic>=2,<3" "faster-whisper>=1.1,<2.0"
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "/app/services/asr", "--host", "0.0.0.0", "--port", "8006"]
