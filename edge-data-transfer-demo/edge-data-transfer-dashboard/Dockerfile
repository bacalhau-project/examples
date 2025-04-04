# Build stage
FROM node:19-alpine AS builder
WORKDIR /app

# Copy dependency files and install dependencies
COPY package.json package-lock.json ./
RUN npm install

# Copy source code and build the Next.js app
COPY . .
RUN npm run build

# Production stage
FROM node:19-alpine
WORKDIR /app

# Install only necessary tools for Bacalhau
RUN apk add --no-cache curl bash

# Copy built application from builder stage
COPY --from=builder /app ./

# Install Bacalhau CLI
RUN curl -sL https://get.bacalhau.org/install.sh | bash

# Environment variables (can also be passed via docker-compose)
ENV BACALHAU_API_HOST \
    BACALHAU_API_TLS_USETLS \
    BACALHAU_TOKEN

# Expose port
EXPOSE 3000

# Start command with Bacalhau check and Next.js app
CMD echo "$BACALHAU_TOKEN" | bacalhau node list && npm start
