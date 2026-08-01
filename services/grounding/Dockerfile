FROM python:3.12-slim
ARG TORCH_VERSION=2.13.0
ARG PYTORCH_INDEX_URL=https://download.pytorch.org/whl/test/cu132
WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir --index-url "${PYTORCH_INDEX_URL}" --extra-index-url https://pypi.org/simple "torch==${TORCH_VERSION}" \
    && pip install --no-cache-dir "fastapi>=0.115,<1.0" "uvicorn[standard]>=0.30,<1.0" "pydantic>=2,<3" "python-multipart>=0.0.18,<1.0" "pillow>=10,<12" "transformers>=4.57,<6"
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "/app/services/grounding", "--host", "0.0.0.0", "--port", "8003"]
