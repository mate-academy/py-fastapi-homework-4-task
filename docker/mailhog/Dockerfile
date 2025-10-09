FROM golang:1.24-bookworm AS build
RUN go env -w GOTOOLCHAIN=auto
RUN go install github.com/mailhog/MailHog@v1.0.1

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /go/bin/MailHog /usr/local/bin/mailhog

COPY commands/setup_mailhog_auth.sh /commands/setup_mailhog_auth.sh
RUN chmod +x /commands/setup_mailhog_auth.sh

EXPOSE 1025 8025

CMD ["mailhog", "-smtp-bind-addr", "0.0.0.0:1025", "-ui-bind-addr", "0.0.0.0:8025"]