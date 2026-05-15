#!/bin/bash

# Define colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting backend server...${NC}"
cd backend
python3 app.py &
BACKEND_PID=$!
cd ..

echo -e "${BLUE}Starting frontend server...${NC}"
cd frontend
python3 -m http.server 3000 &
FRONTEND_PID=$!
cd ..

echo "================================================="
echo -e "${GREEN}Backend is running at: http://localhost:8000${NC}"
echo -e "${BLUE}Frontend is running at: http://localhost:3000${NC}"
echo "Press Ctrl+C to stop both servers"
echo "================================================="

# Trap Ctrl+C (SIGINT) to elegantly kill both background processes
trap "echo -e '\nShutting down servers...'; kill $BACKEND_PID $FRONTEND_PID" SIGINT

# Wait for background processes to finish
wait
