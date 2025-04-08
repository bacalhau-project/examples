# Build stage
FROM node:19-alpine3.18 AS builder
WORKDIR /app

# Copy dependency files and install dependencies
COPY package.json package-lock.json next.config.mjs ./
RUN npm install

# Copy source code and build the Next.js app
COPY . .
RUN npm run build

# Production stage
FROM ghcr.io/bacalhau-project/bacalhau:v1.7.0
WORKDIR /app

# Copy only necessary files for production
COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/.next ./.next/
COPY --from=builder /app/public ./public/
COPY --from=builder /app/next.config.mjs ./

# Install node and npm:
ENV NODE_VERSION 19.9.0

RUN apt-get update && apt-get install -y curl xz-utils ca-certificates

RUN ARCH= && dpkgArch="$(dpkg --print-architecture)" \
    && case "${dpkgArch##*-}" in \
    amd64) ARCH='x64';; \
    arm64) ARCH='arm64';; \
    *) echo "unsupported architecture"; exit 1 ;; \
    esac \
    && curl -fsSLO --compressed "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-$ARCH.tar.xz" \
    && tar -xJf "node-v$NODE_VERSION-linux-$ARCH.tar.xz" -C /usr/local --strip-components=1 --no-same-owner \
    && rm "node-v$NODE_VERSION-linux-$ARCH.tar.xz" \
    && ln -s /usr/local/bin/node /usr/local/bin/nodejs \
    # smoke tests
    && node --version \
    && npm --version

# Install only production dependencies
RUN npm install --production

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh

# Make entrypoint script executable
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 3000

# Run entrypoint script
ENTRYPOINT ["/entrypoint.sh"]