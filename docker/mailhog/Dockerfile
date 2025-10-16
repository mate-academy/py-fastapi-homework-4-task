FROM golang:1.24

# Install dependencies
RUN apt update && apt install -y \
    wget \
    dos2unix \
    && apt clean

# Set correct GOPATH and GOBIN
ENV GOPATH=/go
ENV GOBIN=/usr/local/bin
ENV PATH="${GOBIN}:${PATH}"

# Install MailHog binary into /usr/local/bin
RUN go install github.com/mailhog/MailHog@latest

# Copy and prepare setup script
COPY commands/setup_mailhog_auth.sh /commands/setup_mailhog_auth.sh
RUN dos2unix /commands/setup_mailhog_auth.sh && chmod +x /commands/setup_mailhog_auth.sh
