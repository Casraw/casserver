#!/bin/bash
set -e

echo "Initializing production environment..."

# Ensure nginx log files exist and have correct permissions
echo "Setting up nginx log files..."
mkdir -p /var/log/nginx/
touch /var/log/nginx/access.log
touch /var/log/nginx/error.log
chown -R www-data:www-data /var/log/nginx/
chmod 755 /var/log/nginx/
chmod 644 /var/log/nginx/access.log
chmod 644 /var/log/nginx/error.log

# Initialize database
echo "Initializing database..."
python3 -m backend.init_db

# Wait for database to be ready
echo "Waiting for database to be ready..."
sleep 5

# Validate environment variables
echo "Validating environment variables..."
if [[ -z "$MINTER_PRIVATE_KEY" || "$MINTER_PRIVATE_KEY" == "YOUR_MINTER_PRIVATE_KEY_HERE_MUST_BE_SET_IN_ENV" ]]; then
    echo "ERROR: MINTER_PRIVATE_KEY must be set in environment"
    exit 1
fi

if [[ -z "$INTERNAL_API_KEY" || "$INTERNAL_API_KEY" == "bridge_internal_secret_key_change_me_!!!" ]]; then
    echo "ERROR: INTERNAL_API_KEY must be set to a secure value"
    exit 1
fi

if [[ -z "$WCAS_CONTRACT_ADDRESS" || "$WCAS_CONTRACT_ADDRESS" == "0x0000000000000000000000000000000000000000" ]]; then
    echo "ERROR: WCAS_CONTRACT_ADDRESS must be set"
    exit 1
fi

echo "Environment validation passed."

# Start supervisor to manage all services
echo "Starting production services..."
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf 