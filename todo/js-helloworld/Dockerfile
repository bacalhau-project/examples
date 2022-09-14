FROM denoland/deno:latest
WORKDIR /app
COPY deps.ts .
RUN deno cache deps.ts
COPY process.ts .
RUN deno cache process.ts
RUN mkdir -p /var/tmp/log
CMD ["deno", "run", "--allow-read", "--allow-write", "--allow-env", "process.ts"]