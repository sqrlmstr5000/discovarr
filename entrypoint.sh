#!/bin/sh
set -e # Exit immediately if a command exits with a non-zero status.

# --- PUID/PGID Runtime Configuration ---
# Use environment variables PUID and PGID, with defaults if not set.
# These defaults should ideally match the ones used at build time if no runtime vars are provided.
PUID_TO_SET=${PUID:-1884}
PGID_TO_SET=${PGID:-1884}

APP_USER="discovarr"

# Check if the user exists before trying to get its ID
if id "$APP_USER" >/dev/null 2>&1; then
    CURRENT_UID=$(id -u "$APP_USER")
    CURRENT_GID=$(id -g "$APP_USER")

    echo "INFO: Desired PUID=${PUID_TO_SET}, PGID=${PGID_TO_SET}"
    echo "INFO: Current ${APP_USER} UID=${CURRENT_UID}, GID=${CURRENT_GID}"

    # Modify group GID if necessary
    if [ "$PGID_TO_SET" != "$CURRENT_GID" ]; then
        echo "INFO: Modifying group ${APP_USER} GID from $CURRENT_GID to $PGID_TO_SET"
        groupmod -o -g "$PGID_TO_SET" "$APP_USER"
    fi

    # Modify user UID if necessary
    if [ "$PUID_TO_SET" != "$CURRENT_UID" ]; then
        echo "INFO: Modifying user ${APP_USER} UID from $CURRENT_UID to $PUID_TO_SET"
        usermod -o -u "$PUID_TO_SET" "$APP_USER"
    fi
else
    echo "WARNING: User ${APP_USER} not found. Skipping PUID/PGID modification. This might indicate an issue with the Docker image build."
fi
# --- End PUID/PGID Runtime Configuration ---

# The runtime environment variable that holds the API URL
RUNTIME_API_URL_ENV_VAR="VITE_DISCOVARR_URL"

# The placeholder string in your JS/HTML code
PLACEHOLDER="__API_ENDPOINT__"

# Default API URL if the environment variable is not set or is empty
# This will be used if VITE_DISCOVARR_URL is not provided when running the container.
DEFAULT_FALLBACK_URL="http://localhost:8000/api" # Adjust if your default API path is different

# Directory where your built frontend assets are located (copied from client/dist)
# This path is inside the Docker container.
STATIC_ASSETS_DIR="/app/server/static"

# Determine the target URL
TARGET_URL=$(printenv "${RUNTIME_API_URL_ENV_VAR}")

if [ -z "${TARGET_URL}" ]; then
  echo "INFO: Environment variable '${RUNTIME_API_URL_ENV_VAR}' is not set or is empty."
  echo "INFO: Using default fallback API URL: '${DEFAULT_FALLBACK_URL}'"
  TARGET_URL="${DEFAULT_FALLBACK_URL}"
else
  echo "INFO: Using API URL from environment variable '${RUNTIME_API_URL_ENV_VAR}': '${TARGET_URL}'"
fi

echo "INFO: Replacing placeholder '${PLACEHOLDER}' with '${TARGET_URL}' in JS and HTML files..."

# Find all .js and .html files in the static assets directory and its subdirectories
# and replace the placeholder.
# Using '#' as a delimiter for sed to avoid issues with slashes ('/') in the URL.
# The -print0 and xargs -0 pattern handles filenames with spaces or special characters.
find "${STATIC_ASSETS_DIR}" -type f \( -name "*.js" -o -name "*.html" \) -print0 | \
  xargs -0 sed -i "s#${PLACEHOLDER}#${TARGET_URL}#g"

echo "INFO: Placeholder replacement complete."

# Update ownership of key directories after potential UID/GID changes and before switching user.
# This ensures the application user can read/write necessary files.
echo "INFO: Ensuring ownership of /app, /config, /backups for UID ${PUID_TO_SET} and GID ${PGID_TO_SET}"
chown -R "${PUID_TO_SET}:${PGID_TO_SET}" /app /config /backups

# Execute the CMD passed to the entrypoint (e.g., uvicorn ...)
# Use gosu to drop privileges and execute the command as the APP_USER
echo "INFO: Executing command as user ${APP_USER} (UID: $(id -u ${APP_USER}), GID: $(id -g ${APP_USER})): $@"
exec gosu "$APP_USER" "$@"