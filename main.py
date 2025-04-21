from fastapi import FastAPI, Query
from sqlalchemy import create_engine, Column, Integer, String, Numeric, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from pydantic import BaseModel
from datetime import date
import os

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:111@localhost:5432/0.3.23")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Enterprise(Base):
    __tablename__ = "enterprises"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    requisites = Column(String)
    phone = Column(String)
    contact_person = Column(String)


class Indicator(Base):
    __tablename__ = "indicators"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    importance = Column(Numeric)
    unit = Column(String)


class Currency(Base):
    __tablename__ = "currencies"
    code = Column(String, primary_key=True)
    name = Column(String)


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    id = Column(Integer, primary_key=True)
    from_currency = Column(String, ForeignKey("currencies.code"))
    to_currency = Column(String, ForeignKey("currencies.code"))
    rate = Column(Numeric)
    rate_date = Column(Date)


class IndicatorValue(Base):
    __tablename__ = "indicator_values"
    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    indicator_id = Column(Integer, ForeignKey("indicators.id"))
    value_date = Column(Date)
    value = Column(Numeric)
    currency_code = Column(String, ForeignKey("currencies.code"))

class EnterpriseSchema(BaseModel):
    id: int
    name: str
    requisites: str
    phone: str
    contact_person: str

    class Config:
        from_attributes = True


class IndicatorSchema(BaseModel):
    id: int
    name: str
    importance: float
    unit: str

    class Config:
        from_attributes = True


class CurrencySchema(BaseModel):
    code: str
    name: str

    class Config:
        from_attributes = True


class ExchangeRateSchema(BaseModel):
    id: int
    from_currency: str
    to_currency: str
    rate: float
    rate_date: date

    class Config:
        from_attributes = True


class IndicatorValueSchema(BaseModel):
    id: int
    enterprise_id: int
    indicator_id: int
    value_date: date
    value: float
    currency_code: str
    converted_value: Optional[float] = None

    class Config:
        from_attributes = True


@app.get("/enterprises/", response_model=List[EnterpriseSchema])
def get_enterprises():
    db = SessionLocal()
    return db.query(Enterprise).all()


@app.get("/indicators/", response_model=List[IndicatorSchema])
def get_indicators():
    db = SessionLocal()
    return db.query(Indicator).all()


@app.get("/currencies/", response_model=List[CurrencySchema])
def get_currencies():
    db = SessionLocal()
    return db.query(Currency).all()


@app.get("/exchange-rates/", response_model=List[ExchangeRateSchema])
def get_exchange_rates():
    db = SessionLocal()
    return db.query(ExchangeRate).all()


@app.get("/indicator-values/", response_model=List[IndicatorValueSchema])
def get_indicator_values(
    enterprise_id: int = Query(None),
    indicator_id: int = Query(None),
    from_date: date = Query(None),
    to_date: date = Query(None),
    target_currency: str = Query("RUB")
):
    db = SessionLocal()
    query = db.query(IndicatorValue)

    if enterprise_id:
        query = query.filter(IndicatorValue.enterprise_id == enterprise_id)
    if indicator_id:
        query = query.filter(IndicatorValue.indicator_id == indicator_id)
    if from_date:
        query = query.filter(IndicatorValue.value_date >= from_date)
    if to_date:
        query = query.filter(IndicatorValue.value_date <= to_date)

    result = []
    for item in query.all():
        item_dict = IndicatorValueSchema.from_orm(item).dict()

        if item.currency_code == target_currency:
            item_dict["converted_value"] = float(item.value)
        else:
            rate = db.query(ExchangeRate).filter_by(
                from_currency=item.currency_code,
                to_currency=target_currency,
                rate_date=item.value_date
            ).first()
            if rate:
                item_dict["converted_value"] = round(float(item.value) * float(rate.rate), 2)
            else:
                item_dict["converted_value"] = None

        result.append(item_dict)

    return result
