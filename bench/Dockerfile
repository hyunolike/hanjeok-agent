# syntax=docker/dockerfile:1
#
# The guide service and its Neo4j in one container, for a Hugging Face Space.
#
# One container because a Space is one container. Nothing in it needs to
# persist: the graph is rebuilt from files on every start, which is what "the
# graph store is disposable" already demanded (constitution, Constraints).
#
# What is slow is done here, at build time, so that starting is quick:
# dependencies, the embedding model's weights, the embeddings of every place,
# and the graph itself. Starting is then starting Neo4j and the server.
#
# Build from the bench directory:
#   docker build -t hanjeok-guide .
# With another export (not the synthetic one), put it and, if you have one, its
# embedding cache under .cache/ and pass:
#   --build-arg EXPORT_DIR=.cache/exports/<name> --build-arg EMBEDDING_CACHE=.cache/guide-embeddings.sqlite
FROM neo4j:5.26-community

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

# A Space runs the container as uid 1000 and only that user's home is certain
# to be writable. Everything the running service writes goes under it.
RUN useradd --create-home --uid 1000 guide 2>/dev/null || true
ENV HOME=/home/guide \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    HF_HOME=/opt/hf \
    PATH=/opt/venv/bin:$PATH
WORKDIR /app/bench

# Dependencies first, so editing source does not reinstall torch.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

# The embedding model's weights, pinned to the revision the code names.
RUN python -c "from bench.embeddings import LocalEmbedder; LocalEmbedder().embed_query('warm')"

# The policy wiki, at the commit CI builds the bundle from. Cloned here and not
# at start: if the wiki were briefly unreachable the service could not start,
# and the same image would answer from different reasons on different days.
ARG WIKI_REF=7fc19c0c4a034868866bcf5a920e3f82050830c7
RUN git clone --quiet https://github.com/hyunolike/travel-context-wiki.git /app/wiki \
    && git -C /app/wiki checkout --quiet "$WIKI_REF"

# The export, and the embeddings of its places.
ARG EXPORT_DIR=tests/fixtures/hanjeok-export
ARG EMBEDDING_CACHE=deploy/empty-cache
COPY ${EXPORT_DIR} /app/data/export
COPY ${EMBEDDING_CACHE} /app/data/cache-in
RUN mkdir -p /app/data \
    && if [ -f /app/data/cache-in ]; then mv /app/data/cache-in /app/data/embeddings.sqlite; else rm -rf /app/data/cache-in; fi \
    && guide refresh --export /app/data/export --cache /app/data/embeddings.sqlite --embed-only
# Recorded Hanjeok responses for the synthetic export. Used only in replay mode.
COPY tests/fixtures/hanjeok-live /app/data/live
COPY reports/guide /app/bench/reports/guide
COPY deploy /app/deploy

# Everything the running service writes is under these, owned by the user it
# runs as. The graph is built as that user so its files are too.
RUN mkdir -p /app/graph \
    && chown -R 1000:1000 /app /opt/hf /home/guide /var/lib/neo4j /logs /data 2>/dev/null; chmod +x /app/deploy/*.sh
USER 1000
ENV BENCH_WIKI_ROOT=/app/wiki \
    HF_HUB_OFFLINE=1
RUN /app/deploy/build-graph.sh

ENV PORT=7860 \
    GUIDE_ENV=production \
    GUIDE_LIVE_MODE=replay \
    GUIDE_LIVE_RECORDING=/app/data/live \
    GUIDE_TRUST_PROXY=1
EXPOSE 7860
ENTRYPOINT ["/app/deploy/start.sh"]
