from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Link, User, Base
from passlib.context import CryptContext
from jose import JWTError, jwt
import random
import string
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import redis
import os

Base.metadata.create_all(bind=engine)

app = FastAPI()

REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") 

r = redis.Redis(
    host='mighty-cougar-32942.upstash.io',  
    port=6379,  
    password=REDIS_PASSWORD, 
    ssl=True  
)

SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# хеширование паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# Хеширование пароля
def hash_password(password: str):
    return pwd_context.hash(password)

# Создание JWT токена
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Регистрация 
@app.post("/register")
def register(username: str, password: str, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    hashed_password = hash_password(password)
    new_user = User(username=username, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Пользователь создан"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Неверный токен")
    except JWTError:
        raise HTTPException(status_code=401, detail="Неверный токен")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    
    return user

# Создание короткой ссылки 
@app.post("/links/shorten")
def shorten_link(original_url: str, custom_alias: str = None, expires_at: datetime = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        if custom_alias:
            existing_link = db.query(Link).filter(Link.short_code == custom_alias).first()
            if existing_link:
                raise HTTPException(status_code=400, detail="Alias уже занят")
            short_code = custom_alias
        else:
            short_code = generate_short_code()

        new_link = Link(
            original_url=original_url,
            short_code=short_code,
            expires_at=expires_at,
            user_id=current_user.id if current_user else None
        )

        db.add(new_link)
        db.commit()
        db.refresh(new_link)
        return {"short_url": f"http://127.0.0.1:8000/{short_code}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Произошла ошибка: {str(e)}")
    
# Перенаправление по короткой ссылке
@app.get("/{short_code}")
def redirect_link(short_code: str, db: Session = Depends(get_db)):
    try:
        # через кэш в  Redis
        cached_url = r.get(short_code)
        if cached_url:
            return {"original_url": cached_url}

        link = db.query(Link).filter(Link.short_code == short_code).first()
        if not link:
            raise HTTPException(status_code=404, detail="Ссылка не найдена")

        # Обновление статистики
        link.click_count += 1
        link.last_used = datetime.utcnow()
        db.commit()

        r.setex(short_code, 3600, link.original_url)

        if link.expires_at and datetime.utcnow() > link.expires_at:
            raise HTTPException(status_code=410, detail="Срок действия ссылки истёк")

        return {"original_url": link.original_url}

    except redis.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Ошибка подключения к Redis")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Удаление ссылки 
@app.delete("/links/{short_code}")
def delete_link(short_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    db.delete(link)
    db.commit()

    try:
        r.delete(short_code)
    except redis.exceptions.ConnectionError:
        pass  

    return {"detail": "Ссылка успешно удалена"}

# Обновление ссылки
@app.put("/links/{short_code}")
def update_link(short_code: str, new_url: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    link.original_url = new_url
    db.commit()

    try:
        r.delete(short_code)
    except redis.exceptions.ConnectionError:
        pass  

    r.setex(short_code, 3600, link.original_url)

    return {"detail": "Ссылка успешно обновлена"}

# Проверка пароля
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Поиск пользователя в БД
def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user

# Логин (получение JWT-токена)
@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверные учетные данные")

    access_token = create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Статистика по ссылке
@app.get("/links/{short_code}/stats")
def link_stats(short_code: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    
    return {
        "original_url": link.original_url,
        "created_at": link.created_at,
        "last_used": link.last_used,
        "click_count": link.click_count
    }
