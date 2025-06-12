# Stage 1: Builder for Python dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN pip install --upgrade pip

# Copy requirements and install as wheels
COPY backend/requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# Stage 2: Final Image with Python and Nginx
FROM python:3.11-slim

# Install Nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy python dependency wheels from builder stage
COPY --from=builder /app/wheels /wheels
# Install the python dependencies
RUN pip3 install --no-cache-dir /wheels/*

# Copy the entire application code
# This includes the backend, watchers, tests, and frontend
COPY . .

# Copy Nginx configuration, overwriting the default
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Make entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Set environment variables for the backend
ENV FLASK_ENV=development
ENV SKIP_INTEGRATION_TESTS=false
ENV PYTHONPATH=/app
ENV DATABASE_URL="sqlite:////app/test_bridge_integration.db"
ENV MINTER_PRIVATE_KEY="0x1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b"
ENV POLYGON_RPC_URL="http://localhost:5002"
ENV WCAS_CONTRACT_ADDRESS="0x1234567890123456789012345678901234567890"
ENV INTERNAL_API_KEY="bridge_internal_secret_key_change_me_!!!"
ENV CASCOIN_RPC_URL="http://localhost:5001"
ENV CASCOIN_RPC_USER="testuser"
ENV CASCOIN_RPC_PASSWORD="testpass"
ENV BRIDGE_API_URL="http://localhost:8000/internal"
ENV POLL_INTERVAL_SECONDS="3"
ENV CONFIRMATIONS_REQUIRED="2"

# Expose port 80 for Nginx
EXPOSE 80

# Run entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"] 