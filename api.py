from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import sqlite3
import random
import string
import os
import json
import hashlib
import secrets
import requests as http_requests
from datetime import datetime, date, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== КОНФИГ ==========
ADMIN_CHAT_ID = 8096023466
BOT_TOKEN = "8990265498:AAHwke0u_4MroSTSiY_Krc-8nUS-XAP__K0"

# ========== МОДЕЛИ ==========
class OpenCaseRequest(BaseModel):
    case_id: str

class SellItemRequest(BaseModel):
    item_id: int

class UpgradeItemRequest(BaseModel):
    item_id: int
    new_price: int = 0
    success: bool = True

class WithdrawRequest(BaseModel):
    item_id: int
    trade_link: str

class ActivatePromoRequest(BaseModel):
    code: str

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class AdminCoinsRequest(BaseModel):
    target_id: int
    coins: int

class AdminSpinsRequest(BaseModel):
    target_id: int
    spins: int

class AdminCaseRequest(BaseModel):
    target_id: int
    case_name: str

class AdminPromoRequest(BaseModel):
    reward: int

class AdminPrimeRequest(BaseModel):
    target_id: int

class AdminBanRequest(BaseModel):
    target_id: int

class AdminBroadcastRequest(BaseModel):
    message: str

# ========== БАЗА ДАННЫХ ==========
DB_PATH = os.path.join(os.path.dirname(__file__), 'artdrop.db')

def get_db():
    return sqlite3.connect(DB_PATH)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token():
    return secrets.token_urlsafe(32)

def get_user_by_token(token):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM sessions WHERE token = ? AND expires_at > ?", (token, datetime.now().isoformat()))
    session = c.fetchone()
    if not session:
        conn.close()
        return None
    c.execute("SELECT * FROM users WHERE user_id=?", (session[0],))
    user = c.fetchone()
    conn.close()
    return user

def open_case_logic(case_name):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT price, max_item_price, jackpot_chance FROM cases WHERE name=?", (case_name,))
    price, max_price, chance = c.fetchone()
    conn.close()
    
    if random.random() * 100 <= chance:
        return ("🔥 ДЖЕКПОТ", max_price)
    
    r = random.random() * 100
    if r <= 30:
        percent = random.uniform(0.5, 0.7)
        item = "🟢 Обычный скин"
    elif r <= 55:
        percent = random.uniform(0.7, 0.9)
        item = "🔵 Средний скин"
    elif r <= 75:
        percent = random.uniform(0.9, 1.2)
        item = "🟣 Хороший скин"
    elif r <= 87:
        percent = random.uniform(1.2, 1.6)
        item = "🟠 Очень хороший"
    else:
        percent = random.uniform(1.6, 2.2)
        item = "🔴 Редкий скин"
    
    return (item, int(price * percent))

def send_trade_request_to_admin(username, item_name, item_price, trade_link):
    """Отправляет заявку на вывод админу в Telegram"""
    text = f"🔔 *НОВАЯ ЗАЯВКА НА ВЫВОД!*\n\n👤 @{username}\n📦 {item_name}\n💰 {item_price} монет\n🔗 {trade_link}"
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        http_requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")

# ========== ИНИЦИАЛИЗАЦИЯ БД ==========
def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        coins INTEGER DEFAULT 500,
        total_deposit INTEGER DEFAULT 0,
        wheel_spins INTEGER DEFAULT 1,
        last_wheel_date TEXT DEFAULT '2000-01-01',
        is_banned INTEGER DEFAULT 0,
        referred_by INTEGER DEFAULT 0,
        prime_expires TEXT DEFAULT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER,
        expires_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_name TEXT,
        item_price INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cases (
        name TEXT PRIMARY KEY,
        price INTEGER,
        max_item_price INTEGER,
        jackpot_chance REAL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        reward INTEGER,
        uses_left INTEGER,
        created_by INTEGER,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        code TEXT,
        reward INTEGER,
        used_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdraw_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        item_name TEXT,
        item_price INTEGER,
        trade_link TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposit_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        created_at TEXT
    )''')
    
    default_cases = [
        ("bomj", 500, 1000, 2.0),
        ("berkut", 1500, 3000, 1.5),
        ("chempion", 5000, 10000, 1.2),
        ("major", 50000, 100000, 1.0),
        ("global", 100000, 200000, 0.8),
        ("s1mple", 500000, 1000000, 0.5),
        ("gabe", 1000000, 2000000, 0.3)
    ]
    for name, price, max_price, chance in default_cases:
        c.execute("INSERT OR IGNORE INTO cases VALUES (?,?,?,?)", (name, price, max_price, chance))
    
    conn.commit()
    conn.close()

init_db()

# ========== СТАТИКА ==========
@app.get("/")
async def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/images/{filename}")
async def get_image(filename: str):
    path = os.path.join("images", filename)
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404)

@app.get("/sounds/{filename}")
async def get_sound(filename: str):
    path = os.path.join("sounds", filename)
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404)

# ========== АУТЕНТИФИКАЦИЯ ==========
@app.post("/api/register")
async def register(req: RegisterRequest):
    if len(req.password) < 8:
        return {"error": "Пароль должен быть не менее 8 символов"}
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT user_id FROM users WHERE username = ?", (req.username,))
    if c.fetchone():
        conn.close()
        return {"error": "Пользователь уже существует"}
    
    c.execute("INSERT INTO users (username, password_hash, coins, wheel_spins) VALUES (?,?,500,1)",
              (req.username, hash_password(req.password)))
    user_id = c.lastrowid
    
    token = generate_token()
    c.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
              (token, user_id, (datetime.now() + timedelta(days=30)).isoformat()))
    conn.commit()
    conn.close()
    
    return {"success": True, "token": token, "user_id": user_id}

@app.post("/api/login")
async def login(req: LoginRequest):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, password_hash FROM users WHERE username = ?", (req.username,))
    user = c.fetchone()
    
    if not user or user[1] != hash_password(req.password):
        conn.close()
        return {"error": "Неверный логин или пароль"}
    
    token = generate_token()
    c.execute("INSERT OR REPLACE INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
              (token, user[0], (datetime.now() + timedelta(days=30)).isoformat()))
    conn.commit()
    conn.close()
    
    return {"success": True, "token": token, "user_id": user[0]}

@app.post("/api/logout")
async def logout(request: Request):
    data = await request.json()
    token = data.get("token")
    if token:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    return {"success": True}

@app.get("/api/me")
async def get_me(token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Сессия истекла"}
    return {"user_id": user[0], "username": user[1], "coins": user[3], "deposit": user[4], "wheel_spins": user[5]}

# ========== БАЛАНС ==========
@app.get("/api/balance")
async def get_balance(token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized", "balance": 0}
    return {"balance": user[3], "wheel_spins": user[5]}

# ========== КЕЙСЫ ==========
@app.post("/api/open_case")
async def open_case(req: OpenCaseRequest, token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized"}
    
    conn = get_db()
    c = conn.cursor()
    
    # Получаем цену кейса
    c.execute("SELECT price FROM cases WHERE name=?", (req.case_id,))
    case_price = c.fetchone()[0]
    
    # Проверяем достаточно ли монет
    if user[3] < case_price:
        conn.close()
        return {"error": "Не хватает монет"}
    
    # Открываем кейс
    item_name, item_price = open_case_logic(req.case_id)
    
    # СПИСЫВАЕМ МОНЕТЫ
    c.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (case_price, user[0]))
    
    # ДОБАВЛЯЕМ ПРЕДМЕТ В ИНВЕНТАРЬ
    c.execute("INSERT INTO inventory (user_id, item_name, item_price) VALUES (?,?,?)", (user[0], item_name, item_price))
    conn.commit()
    conn.close()
    
    return {"item": item_name, "price": item_price}

# ========== ИНВЕНТАРЬ ==========
@app.get("/api/inventory")
async def get_inventory(token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized", "items": []}
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, item_name, item_price FROM inventory WHERE user_id=? ORDER BY id DESC", (user[0],))
    items = [{"id": row[0], "name": row[1], "price": row[2]} for row in c.fetchall()]
    conn.close()
    return {"items": items}

@app.post("/api/sell_item")
async def sell_item(req: SellItemRequest, token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized"}
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT item_price FROM inventory WHERE id=? AND user_id=?", (req.item_id, user[0]))
    item = c.fetchone()
    if not item:
        conn.close()
        return {"error": "Предмет не найден"}
    
    sell_price = int(item[0] * 0.95)
    c.execute("DELETE FROM inventory WHERE id=?", (req.item_id,))
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (sell_price, user[0]))
    conn.commit()
    conn.close()
    return {"price": sell_price}

@app.post("/api/upgrade_item")
async def upgrade_item(req: UpgradeItemRequest, token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized"}
    
    conn = get_db()
    c = conn.cursor()
    if req.success and req.new_price > 0:
        c.execute("UPDATE inventory SET item_price=? WHERE id=? AND user_id=?", (req.new_price, req.item_id, user[0]))
    else:
        c.execute("SELECT item_price FROM inventory WHERE id=? AND user_id=?", (req.item_id, user[0]))
        item = c.fetchone()
        if item:
            comp = int(item[0] * 0.05)
            c.execute("DELETE FROM inventory WHERE id=?", (req.item_id,))
            c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (comp, user[0]))
    conn.commit()
    conn.close()
    return {"success": req.success}

# ========== КОЛЕСО ФОРТУНЫ ==========
@app.post("/api/spin_wheel")
async def spin_wheel(token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized"}
    
    conn = get_db()
    c = conn.cursor()
    
    today = date.today().isoformat()
    if today != user[6]:
        c.execute("UPDATE users SET wheel_spins = wheel_spins + 1, last_wheel_date = ? WHERE user_id = ?", (today, user[0]))
        conn.commit()
        user = get_user_by_token(token)
    
    if user[5] <= 0:
        conn.close()
        return {"error": "Нет прокруток"}
    
    prize = random.choice([50, 100, 250, 500, 1000])
    c.execute("UPDATE users SET wheel_spins = wheel_spins - 1, coins = coins + ? WHERE user_id = ?", (prize, user[0]))
    conn.commit()
    conn.close()
    return {"prize": prize}

# ========== ПРОМОКОДЫ ==========
@app.post("/api/activate_promo")
async def activate_promo(req: ActivatePromoRequest, token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized"}
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT reward, uses_left FROM promocodes WHERE code=?", (req.code,))
    promo = c.fetchone()
    if not promo:
        conn.close()
        return {"error": "Неверный промокод"}
    if promo[1] <= 0:
        conn.close()
        return {"error": "Промокод использован"}
    
    used = c.execute("SELECT COUNT(*) FROM promo_usage WHERE user_id=? AND code=?", (user[0], req.code)).fetchone()[0]
    if used > 0:
        conn.close()
        return {"error": "Вы уже активировали этот промокод"}
    
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (promo[0], user[0]))
    c.execute("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code=?", (req.code,))
    c.execute("INSERT INTO promo_usage (user_id, code, reward, used_at) VALUES (?,?,?,?)", (user[0], req.code, promo[0], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"success": True, "reward": promo[0]}

# ========== ВЫВОД ==========
@app.post("/api/withdraw")
async def withdraw(req: WithdrawRequest, token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized"}
    
    conn = get_db()
    c = conn.cursor()
    if user[4] < 250:
        conn.close()
        return {"error": "Депозит менее 250₽"}
    
    c.execute("SELECT item_name, item_price FROM inventory WHERE id=? AND user_id=?", (req.item_id, user[0]))
    item = c.fetchone()
    if not item:
        conn.close()
        return {"error": "Предмет не найден"}
    
    c.execute("DELETE FROM inventory WHERE id=?", (req.item_id,))
    c.execute("INSERT INTO withdraw_requests (user_id, username, item_name, item_price, trade_link, created_at) VALUES (?,?,?,?,?,?)",
              (user[0], user[1], item[0], item[1], req.trade_link, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # Отправляем уведомление админу
    send_trade_request_to_admin(user[1], item[0], item[1], req.trade_link)
    
    return {"success": True}

@app.get("/api/deposit")
async def get_deposit(token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized", "total": 0}
    return {"total": user[4]}

@app.get("/api/promos")
async def get_promos(token: str):
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized", "promos": []}
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT code, reward FROM promo_usage WHERE user_id=? ORDER BY used_at DESC", (user[0],))
    promos = [{"code": row[0], "reward": row[1]} for row in c.fetchall()]
    conn.close()
    return {"promos": promos}

# ========== АДМИНКА (по паролю) ==========
ADMIN_PASSWORD = "250734382"

def check_admin(request: Request):
    # Простая проверка по паролю через заголовок
    password = request.headers.get("X-Admin-Password")
    return password == ADMIN_PASSWORD

@app.get("/api/admin_stats")
async def admin_stats(request: Request):
    if not check_admin(request):
        return {"error": "Access denied"}
    conn = get_db()
    c = conn.cursor()
    users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_coins = c.execute("SELECT SUM(coins) FROM users").fetchone()[0] or 0
    total_items = c.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    total_deposits = c.execute("SELECT SUM(total_deposit) FROM users").fetchone()[0] or 0
    conn.close()
    return {"users": users, "total_coins": total_coins, "total_items": total_items, "total_deposits": total_deposits}

@app.get("/api/admin_users")
async def admin_users(request: Request):
    if not check_admin(request):
        return {"error": "Access denied"}
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, coins, total_deposit FROM users LIMIT 50")
    users = [{"id": row[0], "username": row[1] or str(row[0]), "coins": row[2], "deposit": row[3]} for row in c.fetchall()]
    conn.close()
    return {"users": users}

@app.post("/api/admin_give_coins")
async def admin_give_coins(req: AdminCoinsRequest, request: Request):
    if not check_admin(request):
        return {"error": "Access denied"}
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (req.coins, req.target_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/admin_give_spins")
async def admin_give_spins(req: AdminSpinsRequest, request: Request):
    if not check_admin(request):
        return {"error": "Access denied"}
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET wheel_spins = wheel_spins + ? WHERE user_id = ?", (req.spins, req.target_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/admin_give_case")
async def admin_give_case(req: AdminCaseRequest, request: Request):
    if not check_admin(request):
        return {"error": "Access denied"}
    item_name, item_price = open_case_logic(req.case_name)
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO inventory (user_id, item_name, item_price) VALUES (?,?,?)", (req.target_id, item_name, item_price))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/admin_create_promo")
async def admin_create_promo(req: AdminPromoRequest, request: Request):
    if not check_admin(request):
        return {"error": "Access denied"}
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO promocodes (code, reward, uses_left, created_by, created_at) VALUES (?,?,?,?,?)",
              (code, req.reward, 100, 0, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"code": code}

@app.post("/api/admin_give_prime")
async def admin_give_prime(req: AdminPrimeRequest, request: Request):
    if not check_admin(request):
        return {"error": "Access denied"}
    expires = (date.today() + timedelta(days=30)).isoformat()
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET prime_expires=? WHERE user_id=?", (expires, req.target_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/admin_ban")
async def admin_ban(req: AdminBanRequest, request: Request):
    if not check_admin(request):
        return {"error": "Access denied"}
    conn = get_db()
    c = conn.cursor()
    current = c.execute("SELECT is_banned FROM users WHERE user_id=?", (req.target_id,)).fetchone()
    new = 0 if current and current[0] else 1
    c.execute("UPDATE users SET is_banned=? WHERE user_id=?", (new, req.target_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/admin_broadcast")
async def admin_broadcast(req: AdminBroadcastRequest, request: Request):
    if not check_admin(request):
        return {"error": "Access denied"}
    # Здесь можно добавить отправку через Telegram API
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
