FROM python:3.12-slim
WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir "fastapi>=0.115,<1.0" "uvicorn[standard]>=0.30,<1.0" "pydantic>=2,<3" "python-multipart>=0.0.18,<1.0" "opencv-python-headless>=4.10,<5"
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "/app/services/vision-orchestrator", "--host", "0.0.0.0", "--port", "8001"]
