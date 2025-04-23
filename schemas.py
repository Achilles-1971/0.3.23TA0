from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import date

# Схема для предприятия
class EnterpriseSchema(BaseModel):
    id: int
    name: str
    requisites: str
    phone: str
    contact_person: str

    class Config:
        from_attributes = True

class EnterpriseCreateSchema(BaseModel):
    name: str
    requisites: str
    phone: str
    contact_person: str

# Схема для показателя
class IndicatorSchema(BaseModel):
    id: int
    name: str
    importance: float
    unit: str

    class Config:
        from_attributes = True

class IndicatorCreateSchema(BaseModel):
    name: str
    importance: float = Field(..., gt=0, le=1)  # Важность от 0 до 1
    unit: str

# Схема для валюты
class CurrencySchema(BaseModel):
    code: str
    name: str

    class Config:
        from_attributes = True

class CurrencyCreateSchema(BaseModel):
    code: str
    name: str

# Схема для курса валют
class ExchangeRateSchema(BaseModel):
    id: int
    from_currency: str
    to_currency: str
    rate: float
    rate_date: date

    class Config:
        from_attributes = True

class ExchangeRateCreateSchema(BaseModel):
    from_currency: str
    to_currency: str
    rate: float = Field(..., gt=0)  # Курс должен быть положительным
    rate_date: date

    @validator("to_currency")
    def currencies_must_differ(cls, v, values):
        if "from_currency" in values and v == values["from_currency"]:
            raise ValueError("from_currency and to_currency must be different")
        return v

# Схема для значения показателя
class IndicatorValueSchema(BaseModel):
    id: int
    enterprise_id: int
    indicator_id: int
    value_date: date
    value: float
    currency_code: str
    converted_value: Optional[float] = None
    warning: Optional[str] = None

    class Config:
        from_attributes = True

class IndicatorValueCreateSchema(BaseModel):
    enterprise_id: int
    indicator_id: int
    value_date: date
    value: float
    currency_code: str

# Схема для взвешенного показателя
class WeightedIndicatorSchema(BaseModel):
    indicator_id: int
    indicator_name: str
    value_date: date
    original_value: float
    currency_code: str
    importance: float
    weighted_value: float
    converted_weighted_value: Optional[float] = None
    warning: Optional[str] = None

    class Config:
        from_attributes = True

# Схема для агрегации взвешенных показателей
class WeightedIndicatorAggregateSchema(BaseModel):
    total_weighted_value: Optional[float] = None
    warning: Optional[str] = None

# Схема для группировки взвешенных показателей по периодам
class WeightedIndicatorGroupSchema(BaseModel):
    period: str  # Например, "2025-04" для месяца или "2025-Q2" для квартала
    total_weighted_value: Optional[float] = None
    warning: Optional[str] = None

# Схема для токена
class Token(BaseModel):
    access_token: str
    token_type: str