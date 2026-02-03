import os, random, uuid, json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import socketio
from sqlalchemy import create_engine, Column, String, Integer, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- DATABASE & PERSISTENCE ---
DATABASE_URL = "sqlite:///./cyber_grid.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True)
    password = Column(String)
    char_name = Column(String)
    char_seed = Column(Float) # Used to regenerate the same random shape
    skill_index = Column(Integer)
    wins = Column(Integer, default=0)

Base.metadata.create_all(bind=engine)

# --- SERVER SETUP ---
app = FastAPI()
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)

waiting_room = None
active_matches = {}

# --- CHARACTER SKILLS (30 UNIQUE) ---
SKILLS = [
    {"name": "Bio-Hacker", "desc": "Patch heals 2x more"},
    {"name": "Zero-Day Spec", "desc": "+20% Zero-Day Damage"},
    {"name": "Fast-Typist", "desc": "-15% Attack Durations"},
    {"name": "Encrypted Heart", "desc": "Encryption lasts +2s"},
    {"name": "Botnet King", "desc": "DDoS causes 2s more Slowdown"},
    {"name": "Social Engineer", "desc": "Phishing stuns for 1s"},
    {"name": "Kernel Hardened", "desc": "-20% Incoming Damage"},
    # ... (Logic supports up to 30)
]

# --- API ENDPOINTS ---
class UserReg(BaseModel):
    username: str
    password: str

@app.post("/api/login")
def login(data: UserReg):
    db = SessionLocal()
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        # Create new procedural character
        user = User(
            username=data.username,
            password=data.password,
            char_name=f"AGENT_{random.randint(1000,9999)}",
            char_seed=random.random(),
            skill_index=random.randint(0, len(SKILLS)-1)
        )
        db.add(user)
        db.commit()
    return {
        "char_name": user.char_name,
        "seed": user.char_seed,
        "skill": SKILLS[user.skill_index],
        "wins": user.wins
    }

# --- MULTIPLAYER LOGIC ---
@sio.event
async def join_queue(sid, data):
    global waiting_room
    if waiting_room and waiting_room != sid:
        room_id = f"match_{uuid.uuid4()}"
        await sio.enter_room(waiting_room, room_id)
        await sio.enter_room(sid, room_id)
        await sio.emit('start_match', {'room': room_id}, room=room_id)
        waiting_room = None
    else:
        waiting_room = sid

@sio.event
async def sync_action(sid, data):
    # Broadcast attacks/defenses to the opponent in the room
    await sio.emit('opponent_action', data, room=data['room'], skip_sid=sid)
@app.get("/")
async def serve_ui():
    # This tells the server: "When someone visits the main site, send them index.html"
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(socket_app, host="0.0.0.0", port=port)
