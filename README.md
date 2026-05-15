# AI Programming Buddy Prototype

This project is a prototype for an AI programming assistant that acts like a physical buddy.

## Components
1. **Backend (`/backend`)**: The core brain. Python-based FastAPI server that handles AI logic, API requests from VS Code, and messaging bots.
2. **VS Code Extension (`/vscode-extension`)**: The client inside the editor that sends code context, errors, and asks for suggestions.
3. **Telegram Bot (`/backend/bot.py`)**: Remote access to the assistant to add tasks and reminders.
4. **Simulation UI (`/simulation-ui`)**: A local interface (voice and text) to simulate the physical hologram hardware.

## Quick Start

1. **Install Dependencies**
   Make sure you have Python 3 installed. Then, install the required packages:
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Environment Variables**
   Create a `.env` file inside the `backend/` folder based on the provided example:
   ```bash
   cp .env.example backend/.env
   ```
   Open the `backend/.env` file and add your actual API keys (Gemini API key and Telegram Bot token).

3. **Run the Project (Frontend + Backend)**
   You can run both the frontend and backend servers together using the provided script:
   ```bash
   ./run.sh
   ```
   
   The backend will start on `http://localhost:8000` and the frontend dashboard will be available at `http://localhost:3000`.
