#!/bin/bash
# Simple script to start the mock LiteVNA TCP server
# Usage: ./run_mock_litevna.sh [PORT]

PORT=${1:-12346}

echo "Starting mock LiteVNA server on port $PORT..."
python mock_litevna.py --port "$PORT" --verbose