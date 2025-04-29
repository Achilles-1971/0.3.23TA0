from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers import router
from models import Base, engine
import models  # ← ← ← добавляем сюда
from dependencies import get_db
from sqlalchemy.orm import Session
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from datetime import date


app = FastAPI()

# uvicorn main:app --reload --host 0.0.0.0 --port 8000

Path("uploads").mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
app.include_router(router)

# ---------- КУРСЫ ВАЛЮТ ----------
def auto_update_exchange_rates():
    today = date.today().isoformat()
    try:
        print(f"[APScheduler] Updating exchange rates for {today}")
        response = requests.post(f"http://localhost:8000/update-exchange-rates/?target_date={today}")
        print(f"[APScheduler] Done. Status code: {response.status_code}")
    except Exception as e:
        print(f"[APScheduler] ERROR: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_update_exchange_rates, "cron", hour=1)  # каждый день в 01:00
    scheduler.start()

def update_rates_on_startup():
    db: Session = next(get_db())
    today = date.today()

    existing = db.query(models.ExchangeRate).filter(models.ExchangeRate.rate_date == today).first()

    if existing:
        print(f"[Startup] Курсы на {today} уже есть. Обновление не требуется.")
        return

    print(f"[Startup] Курсы на {today} отсутствуют. Загружаем...")

    url = f"https://api.exchangerate.host/{today.isoformat()}?base=RUB&symbols=USD,EUR"
    response = requests.get(url)

    if not response.ok:
        print("[Startup] Ошибка при получении курсов валют.")
        return

    data = response.json()
    rates = data.get("rates", {})

    for to_currency, rate in rates.items():
        db_rate = models.ExchangeRate(
            from_currency="RUB",
            to_currency=to_currency,
            rate=rate,
            rate_date=today
        )
        db.add(db_rate)

    db.commit()
    print(f"[Startup] Курсы валют на {today} успешно загружены.")

# Запуск планировщика
start_scheduler()

# При запуске сервера - сразу проверка курсов
update_rates_on_startup()
