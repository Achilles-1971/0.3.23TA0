from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers import router
from models import Base, engine
import models
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
    scheduler.add_job(auto_update_exchange_rates, "cron", hour=1)
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

def update_missing_exchange_rates_for_indicator_values():
    db: Session = next(get_db())
    base_currency = "RUB"

    needed = db.query(
        models.IndicatorValue.currency_code,
        models.IndicatorValue.value_date
    ).filter(models.IndicatorValue.currency_code != base_currency).distinct().all()

    currencies = list(set([c for c, _ in needed]))
    dates = list(set([d for _, d in needed]))

    if not currencies or not dates:
        print("[Startup] Нет недостающих валют/дат для загрузки курсов.")
        return

    print(f"[Startup] Поиск недостающих курсов: валюты={currencies}, даты {min(dates)} → {max(dates)}")

    for currency in currencies:
        for date in dates:
            exists = db.query(models.ExchangeRate).filter_by(
                from_currency=currency,
                to_currency=base_currency,
                rate_date=date
            ).first()
            if exists:
                continue

            url = f"https://api.exchangerate.host/{date.isoformat()}?base={currency}&symbols={base_currency}"
            response = requests.get(url)
            if not response.ok:
                print(f"[Startup] ❌ Не удалось загрузить курс для {currency} на {date}")
                continue

            data = response.json().get("rates", {})
            rate = data.get(base_currency)
            if rate is None:
                print(f"[Startup] ❌ Курс не найден: {currency} → {base_currency} на {date}")
                continue

            db.add(models.ExchangeRate(
                from_currency=currency,
                to_currency=base_currency,
                rate_date=date,
                rate=rate
            ))
            print(f"[Startup] ✔ {currency} → {base_currency} на {date} = {rate}")

    db.commit()


start_scheduler()
update_rates_on_startup()
update_missing_exchange_rates_for_indicator_values()
