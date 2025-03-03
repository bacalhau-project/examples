FROM alpine:3.18


WORKDIR /app
COPY word_counter.sh .
RUN chmod +x word_counter.sh

ENTRYPOINT ["/app/word_counter.sh"] 

# Add metadata labels
LABEL org.opencontainers.image.title="Word Count Container"
LABEL org.opencontainers.image.description="A lightweight container that counts words in files or directories"
LABEL org.opencontainers.image.authors="Bacalhau Project"
LABEL org.opencontainers.image.url="https://github.com/bacalhau-project/bacalhau-examples"
LABEL org.opencontainers.image.source="https://github.com/bacalhau-project/bacalhau-examples/tree/main/utility_containers/word-count"
LABEL org.opencontainers.image.vendor="Bacalhau Project"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.created="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
LABEL org.opencontainers.image.version="$(date +%y.%m)"

# Add Bacalhau-specific labels
LABEL bacalhau.org/image.type="utility"
LABEL bacalhau.org/image.category="text-processing"
LABEL bacalhau.org.image.features="word-count,text-analysis"