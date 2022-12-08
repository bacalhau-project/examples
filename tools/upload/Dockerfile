FROM golang:1.18.8-alpine3.16 AS builder
WORKDIR /build
COPY go.mod ./
COPY go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -a -o /upload .

FROM scratch
WORKDIR /app
COPY --from=builder /upload /upload
ENTRYPOINT ["/upload"]
CMD [ "-h" ]