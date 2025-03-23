# Build stage
FROM --platform=$BUILDPLATFORM golang:1.23 AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy go mod and sum files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the binary
ARG TARGETPLATFORM
ARG BUILDPLATFORM
RUN echo "Building for $TARGETPLATFORM on $BUILDPLATFORM" && \
    case "$TARGETPLATFORM" in \
    linux/amd64) \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o event-puller ;; \
    linux/arm64) \
    CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -ldflags="-s -w" -o event-puller ;; \
    esac

# Final stage
FROM --platform=$TARGETPLATFORM alpine:3.19

# Install necessary dependencies
RUN apk --no-cache add ca-certificates tzdata file

# Create a non-root user and group
RUN addgroup -g 1000 appuser && \
    adduser -u 1000 -G appuser -s /bin/sh -D appuser

# Set working directory
WORKDIR /app

# Copy the pre-built binary
COPY bin/event-puller .

# Copy static files - maintain backward compatibility
COPY static/ ./static/

# Copy the Next.js dashboard if it exists
COPY dashboard/out/ ./dashboard/out/

# Set ownership
RUN chown -R appuser:appuser /app

# Use the non-root user
USER appuser

# Expose the web UI port
EXPOSE 8080

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]