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
        extra = "forbid"

class EnterpriseCreateSchema(BaseModel):
    name: str
    requisites: str
    phone: str
    contact_person: str

    class Config:
        extra = "forbid"

# Схема для показателя
class IndicatorSchema(BaseModel):
    id: int
    name: str
    importance: float
    unit: str

    class Config:
        from_attributes = True
        extra = "forbid"

class IndicatorCreateSchema(BaseModel):
    name: str
    importance: float = Field(..., gt=0, le=1)
    unit: str

    class Config:
        extra = "forbid"

# Схема для валюты
class CurrencySchema(BaseModel):
    code: str
    name: str

    class Config:
        from_attributes = True
        extra = "forbid"

class CurrencyCreateSchema(BaseModel):
    code: str
    name: str

    class Config:
        extra = "forbid"

# Схема для курса валют
class ExchangeRateSchema(BaseModel):
    id: int
    from_currency: str
    to_currency: str
    rate: float
    rate_date: date

    class Config:
        from_attributes = True
        extra = "forbid"

class ExchangeRateCreateSchema(BaseModel):
    from_currency: str
    to_currency: str
    rate: float = Field(..., gt=0)
    rate_date: date

    class Config:
        extra = "forbid"

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
        extra = "forbid"

class IndicatorValueCreateSchema(BaseModel):
    enterprise_id: int
    indicator_id: int
    value_date: date
    value: float
    currency_code: str

    class Config:
        extra = "forbid"

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
        extra = "forbid"

# Схема для агрегации взвешенных показателей
class WeightedIndicatorAggregateSchema(BaseModel):
    total_weighted_value: Optional[float] = None
    warning: Optional[str] = None

    class Config:
        extra = "forbid"

# Схема для группировки взвешенных показателей по периодам
class WeightedIndicatorGroupSchema(BaseModel):
    period: str
    total_weighted_value: Optional[float] = None
    warning: Optional[str] = None

    class Config:
        extra = "forbid"

# Схема для токена (одиночный access token)
class Token(BaseModel):
    access_token: str
    token_type: str

    class Config:
        extra = "forbid"

# Схема для пары access + refresh токенов
class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

    class Config:
        extra = "forbid"

# Схема для обновления токена
class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

    class Config:
        extra = "forbid"

# Схема для регистрации пользователя
class UserCreateSchema(BaseModel):
    username: str
    password: str = Field(..., min_length=8)

    class Config:
        extra = "forbid"

# Схема для обновления профиля пользователя
class UserUpdateSchema(BaseModel):
    username: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        extra = "forbid"

# Схема для пользователя
class UserSchema(BaseModel):
    id: int
    username: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True
        extra = "forbid"