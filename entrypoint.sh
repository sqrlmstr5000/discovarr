#!/bin/sh
set -e # Exit immediately if a command exits with a non-zero status.

# The runtime environment variable that holds the API URL
RUNTIME_API_URL_ENV_VAR="VITE_AIARR_URL"

# The placeholder string in your JS/HTML code
PLACEHOLDER="__API_ENDPOINT__"

# Default API URL if the environment variable is not set or is empty
# This will be used if VITE_AIARR_URL is not provided when running the container.
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

# Execute the CMD passed to the entrypoint (e.g., uvicorn ...)
echo "INFO: Executing command: $@"
exec "$@"