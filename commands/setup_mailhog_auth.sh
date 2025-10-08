#!/usr/bin/env bash
set -euo pipefail

AUTH_FILE="/mailhog.auth"
MAILHOG_BIN="/usr/local/bin/mailhog"

if [[ -z "${MAILHOG_USER:-}" || -z "${MAILHOG_PASSWORD:-}" ]]; then
  echo "[FATAL] MAILHOG_USER або MAILHOG_PASSWORD не задано, а MH_AUTH_FILE увімкнено."
  echo "        Або задай обидві змінні, або прибери MH_AUTH_FILE/авторизацію."
  exit 1
fi

if [[ ! -x "$MAILHOG_BIN" ]]; then
  if command -v MailHog >/dev/null 2>&1; then
    MAILHOG_BIN="$(command -v MailHog)"
  elif command -v mailhog >/dev/null 2>&1; then
    MAILHOG_BIN="$(command -v mailhog)"
  else
    exit 1
  fi
fi

HASHED_PASSWORD="$("$MAILHOG_BIN" bcrypt "$MAILHOG_PASSWORD")"
if [[ -z "$HASHED_PASSWORD" ]]; then
  exit 1
fi

echo "${MAILHOG_USER}:${HASHED_PASSWORD}" > "$AUTH_FILE"
chmod 600 "$AUTH_FILE"

echo "[OK] Created $AUTH_FILE for user: '${MAILHOG_USER}'."
