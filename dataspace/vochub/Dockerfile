FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ARG EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV EMBED_MODEL=${EMBED_MODEL} MODEL_CACHE=/models
# Bake the embedding model and the BM25 keyword model into the image so the stack starts offline.
RUN python -c "import os; from fastembed import SparseTextEmbedding, TextEmbedding; TextEmbedding(os.environ['EMBED_MODEL'], cache_dir='/models'); SparseTextEmbedding('Qdrant/bm25', cache_dir='/models')"
COPY . .
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=12 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
