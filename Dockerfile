# Production build. Serves everything on FastAPI. Vite apps is built and served in the ./server/static directory in the container. 

# Stage 1: Build Frontend Assets
# Assumes Node.js for the client build. Adjust if using a different environment.
FROM node:lts-alpine AS client-builder
WORKDIR /app/client

# Copy package.json and package-lock.json (or yarn.lock)
COPY client/package.json client/package-lock.json* ./

# Install client dependencies
# Using 'npm ci' for reproducible builds if package-lock.json is present and up-to-date
# Otherwise, 'npm install' can be used.
RUN npm ci || npm install

# Copy the rest of the client application code
COPY client/ ./

# Build the client application
# Adjust 'npm run build' if you use a different command (e.g., yarn build)
# Adjust the output directory if it's not 'dist' (e.g., 'build')
RUN npm run build

# Stage 2: Setup Backend Application
FROM python:3.12-slim AS backend-builder
WORKDIR /app

# Set environment variables to prevent Python from writing .pyc files and to buffer output
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies if your Python packages need them
# Example: RUN apt-get update && apt-get install -y --no-install-recommends some-build-dep && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install Python dependencies
COPY ./server/src/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend application code
# Assumes your backend code is in a 'server' directory relative to the Dockerfile
COPY ./server ./server

# Stage 3: Final Production Image
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Define PUID and PGID build arguments with default values
ARG PUID=1884
ARG PGID=1884

# Create a non-root user and group 'aiarr' with specific GID and UID for security
RUN groupadd -g ${PGID} aiarr && useradd -u ${PUID} -g ${PGID} aiarr

# Copy installed Python packages from the backend-builder stage
COPY --from=backend-builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=backend-builder /usr/local/bin/ /usr/local/bin/

# Copy the backend application code from the backend-builder stage
COPY --from=backend-builder /app/server ./server

# Copy built frontend assets from the client-builder stage
# These assets should be served by your FastAPI application.
# Assumes client build output is in '/app/client/dist' in the client-builder stage.
# Assumes FastAPI will serve static files from a 'static' subdirectory within the 'server' directory.
COPY --from=client-builder /app/client/dist ./server/static

# Create directories for persistent data (config, backups) and set ownership
# These paths align with the volumes in your docker-compose.yml
RUN mkdir -p /config /backups && \
    chown -R ${PUID}:${PGID} /config /backups /app
#VOLUME /config
#VOLUME /backups

# Switch to the non-root user
USER aiarr

# Expose the port the application runs on (should match your FastAPI config and docker-compose)
EXPOSE 8000

WORKDIR /app/server/src

# Command to run the FastAPI application
# Adjust 'server.main:app' if your FastAPI app instance is named differently or located in a different file/module.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]