FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN useradd -m -u 1000 user
WORKDIR /app
RUN chown user:user /app  # SQLite creates its journal next to the database file
COPY requirements.txt .
# CPU-only PyTorch: the default Linux wheel drags in ~2 GB of CUDA libraries a free Space cannot use.
RUN pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
 && grep -v -E '^(torch|pytest|httpx|#)' requirements.txt > runtime.txt && pip install -r runtime.txt
COPY --chown=user . .
USER user
ENV DATABASE_URL=sqlite:////app/signforge.db \
    SIGNFORGE_DATA_DIR=/app/data/processed \
    SIGNFORGE_CHECKPOINT_DIR=/app/checkpoints \
    SIGNFORGE_BENCHMARK_PATH=/app/data/benchmark_results.json
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
