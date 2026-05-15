from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import json
import uvicorn
import asyncio
import os
import cv2
import numpy as np
import base64
from deepface import DeepFace
import sqlite3
import pickle
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database setup ---
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    # Drop table to start fresh as requested
    c.execute("DROP TABLE IF EXISTS users")
    c.execute('''CREATE TABLE users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE NOT NULL,
                  phone TEXT UNIQUE NOT NULL,
                  telegram_chat_id TEXT,
                  face_encoding BLOB NOT NULL)''')
    conn.commit()
    conn.close()

init_db()

# Configure Gemini
# Load from environment variable, please set this in your .env file
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if not GOOGLE_API_KEY or GOOGLE_API_KEY == "AIzaSyCmX1s9Gff-gyEfBsh7WhqdaO_uBOtiBY8" or GOOGLE_API_KEY == "AIzaSyCf0pOwfrD1x7l-ZCm7ftU8YDd41dltVfY":
    print("WARNING: Using a missing or potentially leaked API key. Please update GEMINI_API_KEY in .env")
    
genai.configure(api_key=GOOGLE_API_KEY)
# Initialize the model
model = genai.GenerativeModel('gemini-3-flash-preview')

# In-memory storage for prototype
reminders = []
tasks = []
user_profile = {}

# --- WebSocket Connection Manager for Avatar ---
class AvatarConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print("Avatar connected!")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print("Avatar disconnected!")

    async def send_state(self, state: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(state)
            except Exception as e:
                print(f"Error sending to avatar: {e}")

avatar_manager = AvatarConnectionManager()

@app.websocket("/ws/avatar")
async def avatar_endpoint(websocket: WebSocket):
    await avatar_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        avatar_manager.disconnect(websocket)

# A simple POST endpoint so the VS Code extension can manually trigger animations
@app.post("/avatar/trigger")
async def trigger_animation(request: Request):
    data = await request.json()
    state = data.get("state", "idle")
    await avatar_manager.send_state(state)
    return {"status": "success", "state": state}

@app.get("/")
async def root():
    return {"message": "AI Buddy Backend is running with Gemini API"}

@app.get("/profile")
async def get_profile():
    return user_profile

@app.post("/profile")
async def update_profile(request: Request):
    global user_profile
    data = await request.json()
    user_profile.update(data)
    return {"status": "success", "profile": user_profile}

@app.post("/chat")
async def chat(request: Request):
    """General chat endpoint for the frontend dashboard"""
    data = await request.json()
    prompt = data.get("prompt", "")
    
    # Inject current tasks and instructions for adding a task
    system_prompt = f"""You are AI Buddy, a personal programming assistant hologram.
The user's profile and memory context is: {json.dumps(user_profile)}. 
Tailor your tone, code snippets, and explanations based on this profile.

CRITICAL INSTRUCTIONS FOR CONVERSATION & MEMORY:
1. Try to be conversational. Occasionally ask a polite, brief question at the end of your response to learn more about their coding habits, current project goals, or preferences so you can help them better.
2. If the user tells you new information about themselves, their project, or their preferences, you MUST save it to their memory by including the following JSON block at the very end of your response:
```json
{{"action": "update_profile", "key": "<Topic/Category>", "value": "<The detailed information you learned>"}}
```

The user's current tasks and reminders are: {json.dumps(tasks)}
If the user asks you to add a task or remind them of something, you MUST include the following JSON block at the very end of your response:
```json
{{"action": "add_task", "task": "<Task description here>"}}
```
Respond naturally to the user first, then append the JSON block(s) if needed.
"""
    full_prompt = f"{system_prompt}\n\nUser: {prompt}"
    
    try:
        # We can send "idle" while thinking instead of "talking", 
        # or perhaps "thinking" if we had a video. For now we will just wait.
        response = model.generate_content(full_prompt)
        reply = response.text
        
        # Parse for action commands (add_task or update_profile)
        if "```json" in reply and '"action"' in reply:
            try:
                start = reply.find("```json") + 7
                end = reply.find("```", start)
                cmd_data = json.loads(reply[start:end].strip())
                
                action = cmd_data.get("action")
                if action == "add_task":
                    new_task = cmd_data.get("task")
                    tasks.append(new_task)
                    reply = reply[:reply.find("```json")].strip() + f"\n\n*(Task added: {new_task})*"
                elif action == "update_profile":
                    k = cmd_data.get("key", "Note")
                    v = cmd_data.get("value", "")
                    user_profile[k] = v
                    reply = reply[:reply.find("```json")].strip() + f"\n\n*(Memory updated securely: Learned about {k})*"
                    
            except Exception as parse_e:
                print("Failed to parse action json:", parse_e)

        # Send the response to the avatar to speak
        talk_cmd = json.dumps({"state": "talking", "text": reply})
        await avatar_manager.send_state(talk_cmd)
                
        return {"response": reply}
    except Exception as e:
        return {"error": str(e)}

@app.post("/code/suggest")
async def suggest_code(request: Request):
    data = await request.json()
    code_context = data.get("context", "")
    
    prompt = f"As an AI programming assistant, provide a concise suggestion, completion, or improvement for this code:\n\n{code_context}\n\nIMPORTANT: Output ONLY valid executable code. Do NOT enclose the code in markdown code blocks like ```python. Any explanation or reasoning MUST be provided as code comments."
    try:
        response = model.generate_content(prompt)
        suggestion = response.text
        
        # Send text to avatar to speak
        talk_cmd = json.dumps({"state": "talking", "text": suggestion})
        await avatar_manager.send_state(talk_cmd)
    except Exception as e:
        suggestion = f"# Error generating suggestion.\n# {str(e)}"
        err_cmd = json.dumps({"state": "error", "text": "I encountered an error."})
        await avatar_manager.send_state(err_cmd)
        
    return {"suggestion": suggestion}

@app.post("/code/error")
async def handle_error(request: Request):
    data = await request.json()
    error_message = data.get("error", "")
    code = data.get("code", "")
    
    prompt = f"As an AI programming assistant, analyze this error message and suggest a fix.\nError: {error_message}\nCode context (if any): {code}"
    try:
        response = model.generate_content(prompt)
        fix = response.text
    except Exception as e:
        fix = f"Error generating fix.\n{str(e)}"
        
    return {"fix": fix}

@app.post("/add_task")
async def add_task(request: Request):
    data = await request.json()
    task = data.get("task", "")
    if task:
        tasks.append(task)
        return {"status": "success", "task": task, "total_tasks": len(tasks)}
    return {"status": "error", "message": "No task provided"}

@app.get("/tasks")
async def get_tasks():
    return {"tasks": tasks}

# --- Face ID Login & Registration Endpoints ---

def process_base64_image(image_data: str):
    """Convert base64 image from frontend to numpy array for OpenCV/Face_recognition"""
    # Remove header from data URL if present (e.g., 'data:image/jpeg;base64,')
    if "," in image_data:
        image_data = image_data.split(",")[1]
    
    encoded_data = base64.b64decode(image_data)
    nparr = np.frombuffer(encoded_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img

@app.post("/register_face")
async def register_face(request: Request):
    """Endpoint for registering a new user with face mapping using DeepFace"""
    data = await request.json()
    image_str = data.get("image")
    name = data.get("name")
    phone = data.get("phone")
    
    if not image_str or not name or not phone:
        return {"status": "error", "message": "Missing image, name, or phone"}
        
    img = process_base64_image(image_str)
    
    try:
        # Extract face embeddings using DeepFace
        # enforce_detection ensures a face is actually found in the frame
        result = DeepFace.represent(img_path=img, model_name="Facenet", enforce_detection=True)
        
        if not result:
            return {"status": "error", "message": "No face detected in the image."}
            
        if len(result) > 1:
            return {"status": "error", "message": "Multiple faces detected. Please ensure only you are in frame."}
            
        face_encoding = result[0]['embedding']
        
        # Store in DB
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        encoding_bytes = pickle.dumps(face_encoding)
        c.execute("INSERT INTO users (name, phone, face_encoding) VALUES (?, ?, ?)", (name, phone, encoding_bytes))
        conn.commit()
        conn.close()
        
        # Add profile locally
        global user_profile
        user_profile["name"] = name
        user_profile["phone"] = phone

        return {"status": "success", "user": name}
    except ValueError as ve:
        # DeepFace throws ValueError when no face is found with enforce_detection
        return {"status": "error", "message": "Could not detect face. Try better lighting."}
    except sqlite3.IntegrityError:
        return {"status": "error", "message": f"User {name} or phone {phone} already exists. Pick different details."}
    except Exception as e:
        return {"status": "error", "message": f"Internal error during registration: {str(e)}"}

def cosine_similarity(a, b):
    # Compute manual cosine distance (0 is perfect match)
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    return dot_product / (norm_a * norm_b)

@app.post("/login_face")
async def login_face(request: Request):
    """Endpoint to authenticate user based on face using DeepFace"""
    data = await request.json()
    image_str = data.get("image")
    
    if not image_str:
        return {"status": "error", "message": "No image data provided for login"}
        
    # Process login image
    img = process_base64_image(image_str)
    
    try:
        # Generate embedding for incoming image
        login_result = DeepFace.represent(img_path=img, model_name="Facenet", enforce_detection=True)
        if not login_result:
            return {"status": "error", "message": "No face found to log in."}
        login_encoding = np.array(login_result[0]['embedding'])
    except ValueError:
       return {"status": "error", "message": "No face found in camera view. Adjust lighting."}
    except Exception as e:
       return {"status": "error", "message": f"Engine error: {str(e)}"}
    
    # Check against database
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT name, face_encoding FROM users")
    db_users = c.fetchall()
    conn.close()
    
    if not db_users:
        return {"status": "error", "message": "No users registered yet."}
        
    best_match_name = None
    # For Facenet Cosine threshold is typically around 0.40
    best_cosine_distance = float('inf')
    threshold = 0.40 
    
    for row in db_users:
        name = row[0]
        db_encoding = np.array(pickle.loads(row[1]))
        
        # Calculate cosine similarity distance (lower is better, 0 means identical)
        similarity = cosine_similarity(login_encoding, db_encoding)
        dist = 1.0 - similarity
        
        if dist < best_cosine_distance:
            best_cosine_distance = dist
            best_match_name = name
            
    if best_cosine_distance <= threshold and best_match_name:
        # Fetch the phone number of the matched user to load into their profile
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT phone FROM users WHERE name=?", (best_match_name,))
        row = c.fetchone()
        conn.close()
        
        global user_profile
        user_profile["name"] = best_match_name
        if row:
            user_profile["phone"] = row[0]
            
        return {"status": "success", "user": best_match_name, "message": f"Logged in as {best_match_name}"}
            
    return {"status": "error", "message": "Face not recognized or biometrics mismatch"}

@app.post("/telegram/link")
async def telegram_link(request: Request):
    """Endpoint for Telegram bot to map a chat_id to a user profile via phone number"""
    data = await request.json()
    phone = data.get("phone")
    chat_id = data.get("chat_id")
    
    if not phone or not chat_id:
        return {"status": "error", "message": "Missing phone or chat_id"}
        
    # Strip any common formatting from the incoming phone just in case (e.g. + or spaces)
    normalized_phone = "".join(filter(str.isdigit, phone))
    
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT id, name, phone FROM users")
    db_users = c.fetchall()
    
    matched_user = None
    for row in db_users:
        db_phone = "".join(filter(str.isdigit, str(row[2])))
        # Check if the incoming phone ends with or exactly matches the DB phone
        if db_phone and (normalized_phone == db_phone or normalized_phone.endswith(db_phone) or db_phone.endswith(normalized_phone)):
            matched_user = row[1]
            break
            
    if matched_user:
        try:
            c.execute("UPDATE users SET telegram_chat_id=? WHERE name=?", (str(chat_id), matched_user))
            conn.commit()
            
            # Optionally load them into the global profile just to prove it works
            global user_profile
            user_profile["name"] = matched_user
            user_profile["phone"] = row[2]
            
        except Exception as e:
            conn.close()
            return {"status": "error", "message": str(e)}
            
        conn.close()
        return {"status": "success", "user": matched_user}
        
    conn.close()
    return {"status": "error", "message": "Phone number not registered in the system."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
