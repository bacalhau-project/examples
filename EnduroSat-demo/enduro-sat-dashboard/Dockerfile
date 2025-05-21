# 1) BUILD STAGE
FROM node:22-alpine AS builder
WORKDIR /app

# install pnpm
RUN npm install -g pnpm@latest

# copy only manifest & lockfile, install all deps
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# copy source & build
COPY . .
RUN pnpm run build

# prune dev‑dependencies (optional with pnpm)
RUN pnpm prune --prod


# 2) PRODUCTION STAGE
FROM node:22-alpine AS runner
WORKDIR /app

# run in production mode
ENV NODE_ENV=production

# install minimal OS tools (for Bacalhau CLI)
RUN apk add --no-cache curl bash

# copy next.js build, runtime deps & static assets
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

# (uncomment to install Bacalhau CLI)
# RUN curl -sL https://get.bacalhau.org/install.sh | bash

EXPOSE 3000

# use exec form, bind to 0.0.0.0 and port 3000
CMD ["npm", "run", "start", "--", "-p", "3000", "-H", "0.0.0.0"]
