# Build context is prepare.py output, never the repository or .env.
# Before a real release, pin this base image to the reviewed platform digest.
FROM python:3.12.9-slim
ARG RETRIEVAL_BACKEND=tfidf
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false PYTHONPATH=/app:/app/experiments RETRIEVAL_INDEX_DIR=/app/index RETRIEVAL_MODEL_DIR=/app/model RETRIEVAL_AUTH_MODE=cloud-run-iam
WORKDIR /app
COPY requirements-*.txt ./
# Operator supplies a platform-matching wheelhouse; no install-time network.
COPY wheelhouse /wheels
RUN case "$RETRIEVAL_BACKEND" in tfidf) requirements=requirements-runtime.txt ;; semantic) requirements=requirements-semantic.txt ;; *) exit 1 ;; esac && pip install --no-cache-dir --no-index --find-links=/wheels -r "$requirements" && rm -rf /wheels
COPY retrieval_service ./retrieval_service
COPY retrieval_lab ./experiments/retrieval_lab
COPY index ./index
COPY model ./model
RUN useradd --uid 10001 --no-create-home retrieval && chmod -R a-w /app
USER 10001:10001
EXPOSE 8080
CMD ["python","-m","retrieval_service.runtime"]
