# Build the manager binary
FROM golang:1.24 as builder

WORKDIR /workspace
# Copy the Go Modules manifests
COPY go.mod go.mod
COPY go.sum go.sum
# cache deps before building and copying source so that we don't need to re-download as much
# and so that source changes don't invalidate our downloaded layer
RUN go mod download

# Copy the go source
COPY main.go main.go
COPY api/ api/
COPY controllers/ controllers/
COPY bacalhau_client/ bacalhau_client/
COPY utils/ utils/


# Build
# RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -a -o manager main.go
RUN CGO_ENABLED=0 GOOS=$GOOS GOARCH=$GOARCH go build -a -o manager main.go

# Use distroless as minimal base image to package the manager binary
# Refer to https://github.com/GoogleContainerTools/distroless for more details
FROM gcr.io/distroless/static:nonroot
WORKDIR /
COPY --from=builder /workspace/manager .
USER 65532:65532

LABEL org.opencontainers.image.title="Bacalhau Kubernetes Operator"
LABEL org.opencontainers.image.description="A Docker image for the Bacalhau Operator project, which provides tools to manage Bacalhau jobs."
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.authors="Krzysztof Dreżewski <krzysztof.drezewski@gmail.com>"

ENTRYPOINT ["/manager"]
