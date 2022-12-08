FROM golang:1.18.8-alpine3.16 AS builder
WORKDIR /build
COPY go.mod ./
COPY go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -a -o /upload .

FROM scratch
WORKDIR /
ENV PATH="/"
COPY --from=builder /upload /upload
# Bacalhau will override the entrypoint, so just use a CMD
CMD [ "upload" ]