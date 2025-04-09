# main.py
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
import requests
import pandas as pd
from pymongo import MongoClient
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
import jwt
import hashlib
import os

SECRET_KEY = os.getenv("SECRET_KEY", "mysecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient("mongodb://localhost:27017/")
db = client["investai"]
users_collection = db["users"]
favorites_collection = db["favorites"]
recs_collection = db["recommendations"]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

class UserRegister(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    email: EmailStr
    token: str

class TokenData(BaseModel):
    email: Optional[str] = None

class Recommendation(BaseModel):
    symbol: str
    signal: str
    confidence: float
    timestamp: str
    indicators: dict

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    user = users_collection.find_one({"email": payload.get("sub")})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user

@app.post("/api/register", response_model=UserResponse)
def register(user: UserRegister):
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email já registrado")
    hashed = hash_password(user.password)
    users_collection.insert_one({"email": user.email, "password": hashed})
    token = create_access_token({"sub": user.email}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return UserResponse(email=user.email, token=token)

@app.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_collection.find_one({"email": form_data.username})
    if not user or user["password"] != hash_password(form_data.password):
        raise HTTPException(status_code=400, detail="Credenciais inválidas")
    token = create_access_token({"sub": form_data.username}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/me")
def get_profile(user=Depends(get_current_user)):
    return {"email": user["email"]}

@app.post("/api/favorite")
def add_favorite(symbol: str, user=Depends(get_current_user)):
    favorites_collection.update_one(
        {"email": user["email"]},
        {"$addToSet": {"symbols": symbol}},
        upsert=True
    )
    return {"msg": f"{symbol} adicionado aos favoritos"}

@app.get("/api/favorites")
def get_favorites(user=Depends(get_current_user)):
    fav = favorites_collection.find_one({"email": user["email"]})
    return fav.get("symbols", []) if fav else []

@app.get("/api/recommend")
def get_recommendation(symbol: str = Query(...), user=Depends(get_current_user)):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=100"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
        ])
        df["close"] = pd.to_numeric(df["close"])

        rsi = RSIIndicator(df["close"]).rsi().iloc[-1]
        macd = MACD(df["close"]).macd_diff().iloc[-1]
        sma = SMAIndicator(df["close"], window=20).sma_indicator().iloc[-1]
        price = df["close"].iloc[-1]

        signals = []
        if rsi < 30: signals.append("compra")
        if rsi > 70: signals.append("venda")
        if macd > 0: signals.append("compra")
        if macd < 0: signals.append("venda")
        if price > sma: signals.append("compra")
        if price < sma: signals.append("venda")

        signal = max(set(signals), key=signals.count) if signals else "aguardar"
        confidence = round((signals.count(signal) / len(signals)) * 100, 2) if signals else 50.0

        result = Recommendation(
            symbol=symbol,
            signal=signal.capitalize(),
            confidence=confidence,
            timestamp=datetime.now().isoformat(),
            indicators={"RSI": round(rsi, 2), "MACD": round(macd, 2), "SMA": round(sma, 2), "Preço": round(price, 2)}
        )
        recs_collection.insert_one(result.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
