FROM golang:1.24-bullseye

# Install dependencies
RUN apt update && apt install -y wget dos2unix && apt clean

# Add Go's bin directory to PATH
ENV PATH="/root/go/bin:$PATH"

# Copy setup script
COPY commands/setup_mailhog_auth.sh /commands/setup_mailhog_auth.sh

# Ensure Unix line endings and executable
RUN dos2unix /commands/setup_mailhog_auth.sh && chmod +x /commands/setup_mailhog_auth.sh

# Install MailHog
RUN go install github.com/mailhog/MailHog@latest