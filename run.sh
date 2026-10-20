#!/bin/bash
set -e

echo "🎨 Starting AirDraw..."

# Determine best Python version (prefer 3.11 if available for MediaPipe compatibility)
if command -v python3.11 &>/dev/null; then
    PY_BIN="python3.11"
elif command -v python3.10 &>/dev/null; then
    PY_BIN="python3.10"
else
    PY_BIN="python3"
fi

echo "Using Python: $($PY_BIN --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment with $PY_BIN..."
    $PY_BIN -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install / update requirements
echo "Checking requirements..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Launch AirDraw
echo "Launching AirDraw application..."
python airdraw.py
