import pyttsx3
import speech_recognition as sr
import requests
import time

BACKEND_URL = "http://localhost:8000"

def speak(text):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id if len(voices) > 1 else voices[0].id)
    engine.say(text)
    engine.runAndWait()

def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n[Simulator] Listening for commands...")
        r.adjust_for_ambient_noise(source)
        try:
            audio = r.listen(source, timeout=5)
            text = r.recognize_google(audio)
            print(f"[Simulator] You said: {text}")
            return text.lower()
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            print("[Simulator] Could not understand audio")
        except Exception as e:
            print(f"[Simulator] Error: {e}")
    return ""

def simulate_hologram():
    print("===============================")
    print(" AI BUDDY HARDWARE SIMULATION")
    print("===============================")
    speak("Hello! Your programming buddy is online.")
    
    while True:
        mode = input("\n[Simulator] Press 'v' for Voice command, 't' for Text task, or 'q' to quit: ").strip().lower()
        
        if mode == 'q':
            speak("Goodbye!")
            break
        elif mode == 't':
            task = input("Enter a task/reminder: ").strip()
            if task:
                try:
                    res = requests.post(f"{BACKEND_URL}/add_task", json={"task": task})
                    if res.status_code == 200:
                        print("[Simulator] Added to your backend successfully!")
                        speak(f"Got it. Added to your tasks.")
                except Exception:
                    print("[Simulator] Failed to connect to the backend server.")
        elif mode == 'v':
            command = listen()
            if "task" in command or "remind" in command:
                speak("Adding reminder now.")
                try:
                    res = requests.post(f"{BACKEND_URL}/add_task", json={"task": command})
                    if res.status_code == 200:
                        speak("Task saved.")
                except Exception:
                    speak("I couldn't reach the server right now.")
            elif command:
                speak(f"I heard {command}, but I don't know how to do that yet.")
        else:
            print("Invalid input.")

if __name__ == "__main__":
    simulate_hologram()
