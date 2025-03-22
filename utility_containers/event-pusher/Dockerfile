FROM golang:1.19-alpine AS builder

WORKDIR /build

# Copy go mod and sum files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -o event-pusher .

# Use a minimal alpine image for the final container
FROM alpine:3.17

WORKDIR /app

# Copy the binary from the builder stage
COPY --from=builder /build/event-pusher .

# Copy the default config file
COPY config.yaml .

# Create a volume for optional configuration overrides
VOLUME /app/config

# Run the binary
CMD ["./event-pusher"]