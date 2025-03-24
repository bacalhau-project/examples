FROM alpine:3.19

# Install necessary dependencies
RUN apk --no-cache add ca-certificates tzdata

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

# Run the application
CMD ["./event-puller"]