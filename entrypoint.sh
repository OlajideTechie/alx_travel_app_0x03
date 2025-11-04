#!/bin/bash
set -e

# Use Render's PORT or default to 8000
PORT=${PORT:-8000}

# Replace placeholder in supervisord.conf
sed -i "s/%(ENV_PORT)s/$PORT/g" /app/supervisord.conf

# Start Supervisor
exec supervisord -c /app/supervisord.conf