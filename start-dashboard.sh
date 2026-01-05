#!/bin/bash

# Start the Streamlit Admin Dashboard
# This script starts the admin dashboard on port 8501

cd "$(dirname "$0")"

echo "Starting Academy Admin Dashboard..."

# Set environment variables
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Run Streamlit
python -m streamlit run dashboard/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    --theme.base=light \
    --theme.primaryColor="#2563eb"
