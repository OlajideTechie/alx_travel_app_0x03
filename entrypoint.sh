#!/bin/bash
# Set default PORT if not provided
export PORT=${PORT:-8000}

# Replace placeholder in supervisord.conf dynamically
sed -i "s/%(ENV_PORT)s/$PORT/g" /app/supervisord.conf

# Start supervisor
exec supervisord -c /app/supervisord.conf