# Build stage
FROM golang:1.23-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git

# Set working directory
WORKDIR /app

# Copy go mod and sum files
COPY src/go.mod src/go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY src/ .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o event-pusher

# Final stage
FROM alpine:latest

# Copy the binary from builder
COPY --from=builder /app/event-pusher /event-pusher

COPY build/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
