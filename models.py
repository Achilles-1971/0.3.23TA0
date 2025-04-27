from sqlalchemy import create_engine, Column, Integer, String, Numeric, ForeignKey, Date, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Получение строки подключения
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env file")

# Подключение к базе
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модели
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)  # Уточняем, что пароль обязателен
    avatar_url = Column(String, nullable=True)  # Поле для URL аватарки

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
    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", "rate_date", name="uix_exchange_rate_date"),
    )

class IndicatorValue(Base):
    __tablename__ = "indicator_values"
    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    indicator_id = Column(Integer, ForeignKey("indicators.id"))
    value_date = Column(Date)
    value = Column(Numeric)
    currency_code = Column(String, ForeignKey("currencies.code"))
    __table_args__ = (
        Index("ix_value_date", "value_date"),
        Index("ix_enterprise_id", "enterprise_id"),
        Index("ix_indicator_id", "indicator_id"),
    )