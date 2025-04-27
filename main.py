from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers import router
from models import Base, engine
from pathlib import Path

app = FastAPI()

# Создаём директорию для статики, если её нет
Path("uploads").mkdir(parents=True, exist_ok=True)

# Монтирование директории для статических файлов (аватарки)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Создаём таблицы в базе
Base.metadata.create_all(bind=engine)

# Подключаем маршруты
app.include_router(router)
