# Use the official MailHog image instead of building from source
FROM mailhog/mailhog:latest

# Install bash and dos2unix for script processing
USER root
RUN apk add --no-cache bash dos2unix

# Copy the authentication setup script
COPY commands/setup_mailhog_auth.sh /commands/setup_mailhog_auth.sh

# Ensure the script has Unix-style line endings and is executable
RUN dos2unix /commands/setup_mailhog_auth.sh && chmod +x /commands/setup_mailhog_auth.sh

# Switch back to mailhog user for security
USER mailhog
