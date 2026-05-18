FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements-prod.txt ./requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
RUN mkdir -p /dev/shm/load_files_uploads
EXPOSE 8005
CMD ["uvicorn", "load_files.api.main:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "2", "--timeout-keep-alive", "120"]
