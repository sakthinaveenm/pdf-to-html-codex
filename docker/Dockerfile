FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-tam && rm -rf /var/lib/apt/lists/*
COPY backend /app/backend
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY frontend/public /app/frontend/public
ENV PYTHONPATH=/app/backend PDF_STORAGE=/data
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
