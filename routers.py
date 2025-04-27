from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import timedelta, date
from passlib.exc import UnknownHashError
import models
import schemas
from dependencies import get_db, get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, pwd_context, create_refresh_token
from sqlalchemy.sql import func
import os
import uuid
from pathlib import Path
import shutil

router = APIRouter()

@router.post("/register", response_model=schemas.TokenPair, tags=["auth"], summary="Register a new user")
def register_user(user: schemas.UserCreateSchema, db: Session = Depends(get_db)):
    # Проверяем, существует ли уже пользователь с таким username
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Хэшируем пароль
    hashed_password = pwd_context.hash(user.password)
    
    # Создаём нового пользователя
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Генерируем токены
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(db_user.id)},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": str(db_user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/token", response_model=schemas.TokenPair, tags=["auth"], summary="Вход и получение токена доступа")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Имя пользователя не существует",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        if not pwd_context.verify(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except UnknownHashError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный формат хеша пароля в базе данных",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": str(user.id)}) 
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=schemas.TokenRefreshResponse, tags=["auth"], summary="Refresh access token")
def refresh_access_token(refresh_token: str = Query(...), db: Session = Depends(get_db)):
    from dependencies import verify_refresh_token, create_access_token
    user_id = verify_refresh_token(refresh_token)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(data={"sub": str(user_id)}, expires_delta=access_token_expires)
    return {"access_token": new_access_token, "token_type": "bearer"}
# -----------------------------------
# Маршруты для пользователей
# -----------------------------------

@router.get("/users/me", response_model=schemas.UserSchema, tags=["users"], summary="Get current user")
def read_current_user(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.put("/users/me", response_model=schemas.UserSchema, tags=["users"], summary="Update current user profile")
def update_current_user(
    user_update: schemas.UserUpdateSchema,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Проверка уникальности username, если оно обновляется
    if user_update.username and user_update.username != current_user.username:
        existing_user = db.query(models.User).filter(models.User.username == user_update.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
        current_user.username = user_update.username
    
    # Обновление avatar_url, если указано
    if user_update.avatar_url is not None:
        current_user.avatar_url = user_update.avatar_url
    
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/users/me/avatar", response_model=schemas.UserSchema, tags=["users"], summary="Upload user avatar")
async def upload_user_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Проверка MIME-типа файла
    allowed_types = ["image/jpeg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPEG or PNG images are allowed")
    
    # Проверка размера файла (например, не более 5 МБ)
    max_size = 5 * 1024 * 1024  # 5 MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="File size exceeds 5 MB")
    
    # Создание директории для аватарок
    upload_dir = Path("uploads/avatars")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Генерация уникального имени файла
    file_extension = file.filename.split(".")[-1].lower()
    file_name = f"{uuid.uuid4()}.{file_extension}"
    file_path = upload_dir / file_name
    
    # Сохранение файла
    with file_path.open("wb") as buffer:
        buffer.write(content)
    
    # Формирование URL
    avatar_url = f"/uploads/avatars/{file_name}"
    
    # Обновление пользователя
    current_user.avatar_url = avatar_url
    db.commit()
    db.refresh(current_user)
    
    return current_user

# -----------------------------------
# Маршруты для предприятий
# -----------------------------------

@router.get("/enterprises/", response_model=List[schemas.EnterpriseSchema], tags=["enterprises"], summary="Get all enterprises")
def get_enterprises(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(models.Enterprise).all()

@router.post("/enterprises/", response_model=schemas.EnterpriseSchema, tags=["enterprises"], summary="Create a new enterprise")
def create_enterprise(enterprise: schemas.EnterpriseCreateSchema, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_enterprise = models.Enterprise(**enterprise.dict())
    db.add(db_enterprise)
    db.commit()
    db.refresh(db_enterprise)
    return db_enterprise

@router.put("/enterprises/{id}", response_model=schemas.EnterpriseSchema, tags=["enterprises"], summary="Update an enterprise")
def update_enterprise(id: int, enterprise: schemas.EnterpriseCreateSchema, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_enterprise = db.query(models.Enterprise).filter(models.Enterprise.id == id).first()
    if not db_enterprise:
        raise HTTPException(status_code=404, detail="Enterprise not found")
    for key, value in enterprise.dict().items():
        setattr(db_enterprise, key, value)
    db.commit()
    db.refresh(db_enterprise)
    return db_enterprise

@router.delete("/enterprises/{id}", tags=["enterprises"], summary="Delete an enterprise")
def delete_enterprise(id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_enterprise = db.query(models.Enterprise).filter(models.Enterprise.id == id).first()
    if not db_enterprise:
        raise HTTPException(status_code=404, detail="Enterprise not found")
    db.delete(db_enterprise)
    db.commit()
    return {"detail": "Enterprise deleted"}

# -----------------------------------
# Маршруты для показателей
# -----------------------------------

@router.get("/indicators/", response_model=List[schemas.IndicatorSchema], tags=["indicators"], summary="Get all indicators")
def get_indicators(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(models.Indicator).all()

@router.post("/indicators/", response_model=schemas.IndicatorSchema, tags=["indicators"], summary="Create a new indicator")
def create_indicator(indicator: schemas.IndicatorCreateSchema, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_indicator = models.Indicator(**indicator.dict())
    db.add(db_indicator)
    db.commit()
    db.refresh(db_indicator)
    return db_indicator

@router.put("/indicators/{id}", response_model=schemas.IndicatorSchema, tags=["indicators"], summary="Update an indicator")
def update_indicator(id: int, indicator: schemas.IndicatorCreateSchema, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_indicator = db.query(models.Indicator).filter(models.Indicator.id == id).first()
    if not db_indicator:
        raise HTTPException(status_code=404, detail="Indicator not found")
    for key, value in indicator.dict().items():
        setattr(db_indicator, key, value)
    db.commit()
    db.refresh(db_indicator)
    return db_indicator

@router.delete("/indicators/{id}", tags=["indicators"], summary="Delete an indicator")
def delete_indicator(id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_indicator = db.query(models.Indicator).filter(models.Indicator.id == id).first()
    if not db_indicator:
        raise HTTPException(status_code=404, detail="Indicator not found")
    db.delete(db_indicator)
    db.commit()
    return {"detail": "Indicator deleted"}

# -----------------------------------
# Маршруты для валют
# -----------------------------------

@router.get("/currencies/", response_model=List[schemas.CurrencySchema], tags=["currencies"], summary="Get all currencies")
def get_currencies(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(models.Currency).all()

@router.post("/currencies/", response_model=schemas.CurrencySchema, tags=["currencies"], summary="Create a new currency")
def create_currency(currency: schemas.CurrencyCreateSchema, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_currency = models.Currency(**currency.dict())
    db.add(db_currency)
    db.commit()
    db.refresh(db_currency)
    return db_currency

@router.put("/currencies/{code}", response_model=schemas.CurrencySchema, tags=["currencies"], summary="Update a currency")
def update_currency(code: str, currency: schemas.CurrencyCreateSchema, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_currency = db.query(models.Currency).filter(models.Currency.code == code).first()
    if not db_currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    for key, value in currency.dict().items():
        setattr(db_currency, key, value)
    db.commit()
    db.refresh(db_currency)
    return db_currency

@router.delete("/currencies/{code}", tags=["currencies"], summary="Delete a currency")
def delete_currency(code: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_currency = db.query(models.Currency).filter(models.Currency.code == code).first()
    if not db_currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    db.delete(db_currency)
    db.commit()
    return {"detail": "Currency deleted"}

# -----------------------------------
# Маршруты для курсов валют
# -----------------------------------

@router.get("/exchange-rates/", response_model=List[schemas.ExchangeRateSchema], tags=["exchange_rates"], summary="Get all exchange rates")
def get_exchange_rates(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(models.ExchangeRate).all()

@router.post("/exchange-rates/", response_model=schemas.ExchangeRateSchema, tags=["exchange_rates"], summary="Create a new exchange rate")
def create_exchange_rate(exchange_rate: schemas.ExchangeRateCreateSchema, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_exchange_rate = models.ExchangeRate(**exchange_rate.dict())
    db.add(db_exchange_rate)
    db.commit()
    db.refresh(db_exchange_rate)
    return db_exchange_rate

@router.put("/exchange-rates/{id}", response_model=schemas.ExchangeRateSchema, tags=["exchange_rates"], summary="Update an exchange rate")
def update_exchange_rate(id: int, exchange_rate: schemas.ExchangeRateCreateSchema, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_exchange_rate = db.query(models.ExchangeRate).filter(models.ExchangeRate.id == id).first()
    if not db_exchange_rate:
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    for key, value in exchange_rate.dict().items():
        setattr(db_exchange_rate, key, value)
    db.commit()
    db.refresh(db_exchange_rate)
    return db_exchange_rate

@router.delete("/exchange-rates/{id}", tags=["exchange_rates"], summary="Delete an exchange rate")
def delete_exchange_rate(id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_exchange_rate = db.query(models.ExchangeRate).filter(models.ExchangeRate.id == id).first()
    if not db_exchange_rate:
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    db.delete(db_exchange_rate)
    db.commit()
    return {"detail": "Exchange rate deleted"}

# -----------------------------------
# Маршруты для значений показателей
# -----------------------------------

@router.get("/indicator-values/", response_model=List[schemas.IndicatorValueSchema], tags=["indicator_values"], summary="Get indicator values with optional filters")
def get_indicator_values(
    enterprise_id: int = Query(None),
    indicator_id: int = Query(None),
    from_date: date = Query(None),
    to_date: date = Query(None),
    target_currency: str = Query("RUB"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = db.query(models.IndicatorValue)
    if enterprise_id:
        query = query.filter(models.IndicatorValue.enterprise_id == enterprise_id)
    if indicator_id:
        query = query.filter(models.IndicatorValue.indicator_id == indicator_id)
    if from_date:
        query = query.filter(models.IndicatorValue.value_date >= from_date)
    if to_date:
        query = query.filter(models.IndicatorValue.value_date <= to_date)
    
    query = query.offset(skip).limit(limit)
    indicator_values = query.all()

    dates = {item.value_date for item in indicator_values}
    currencies = {item.currency_code for item in indicator_values}

    exchange_rates = db.query(models.ExchangeRate).filter(
        models.ExchangeRate.from_currency.in_(currencies),
        models.ExchangeRate.to_currency == target_currency,
        models.ExchangeRate.rate_date.in_(dates)
    ).all()

    rate_dict: Dict[tuple, float] = {
        (rate.from_currency, rate.rate_date): float(rate.rate) for rate in exchange_rates
    }

    result = []
    for item in indicator_values:
        item_dict = schemas.IndicatorValueSchema.from_orm(item).dict()
        if item.currency_code == target_currency:
            item_dict["converted_value"] = float(item.value)
            item_dict["warning"] = None
        else:
            rate_key = (item.currency_code, item.value_date)
            if rate_key in rate_dict:
                item_dict["converted_value"] = round(float(item.value) * rate_dict[rate_key], 2)
                item_dict["warning"] = None
            else:
                item_dict["converted_value"] = None
                item_dict["warning"] = f"No exchange rate found for {item.currency_code} to {target_currency} on {item.value_date}"
        result.append(item_dict)

    return result

@router.post(
    "/indicator-values/", 
    response_model=schemas.IndicatorValueSchema, 
    status_code=201, 
    summary="Создать значение показателя", 
    description="Создаёт новое значение показателя для заданного предприятия с возможной конвертацией валют."
)
def create_indicator_value(
    indicator_value: schemas.IndicatorValueCreateSchema,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    enterprise = db.query(models.Enterprise).get(indicator_value.enterprise_id)
    if not enterprise:
        raise HTTPException(status_code=400, detail="Предприятие не найдено")

    indicator = db.query(models.Indicator).get(indicator_value.indicator_id)
    if not indicator:
        raise HTTPException(status_code=400, detail="Показатель не найден")

    currency = db.query(models.Currency).get(indicator_value.currency_code)
    if not currency:
        raise HTTPException(status_code=400, detail="Валюта не найдена")

    db_value = models.IndicatorValue(**indicator_value.dict())
    db.add(db_value)
    db.commit()
    db.refresh(db_value)
    return db_value

@router.put("/indicator-values/{id}", response_model=schemas.IndicatorValueSchema, tags=["indicator_values"], summary="Update an indicator value")
def update_indicator_value(id: int, indicator_value: schemas.IndicatorValueCreateSchema, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_indicator_value = db.query(models.IndicatorValue).filter(models.IndicatorValue.id == id).first()
    if not db_indicator_value:
        raise HTTPException(status_code=404, detail="Indicator value not found")
    for key, value in indicator_value.dict().items():
        setattr(db_indicator_value, key, value)
    db.commit()
    db.refresh(db_indicator_value)
    return db_indicator_value

@router.delete("/indicator-values/{id}", tags=["indicator_values"], summary="Delete an indicator value")
def delete_indicator_value(id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_indicator_value = db.query(models.IndicatorValue).filter(models.IndicatorValue.id == id).first()
    if not db_indicator_value:
        raise HTTPException(status_code=404, detail="Indicator value not found")
    db.delete(db_indicator_value)
    db.commit()
    return {"detail": "Indicator value deleted"}

# -----------------------------------
# Маршруты для взвешенных показателей
# -----------------------------------

@router.get("/weighted-indicators/", 
            response_model=List[schemas.WeightedIndicatorSchema] | schemas.WeightedIndicatorAggregateSchema | List[schemas.WeightedIndicatorGroupSchema], 
            tags=["weighted_indicators"], 
            summary="Get weighted indicators, their aggregate, or grouped by period")
def get_weighted_indicators(
    enterprise_id: int = Query(...),
    indicator_id: int = Query(None),
    from_date: date = Query(None),
    to_date: date = Query(None),
    target_currency: str = Query("RUB"),
    aggregate: bool = Query(False),
    group_by: str = Query(None, regex="^(month|quarter)?$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = db.query(models.IndicatorValue, models.Indicator.name, models.Indicator.importance).join(
        models.Indicator, models.IndicatorValue.indicator_id == models.Indicator.id
    ).filter(models.IndicatorValue.enterprise_id == enterprise_id)

    if indicator_id:
        query = query.filter(models.IndicatorValue.indicator_id == indicator_id)
    if from_date:
        query = query.filter(models.IndicatorValue.value_date >= from_date)
    if to_date:
        query = query.filter(models.IndicatorValue.value_date <= to_date)

    if not group_by and not aggregate:
        query = query.offset(skip).limit(limit)
    indicator_values = query.all()

    dates = {item[0].value_date for item in indicator_values}
    currencies = {item[0].currency_code for item in indicator_values}

    exchange_rates = db.query(models.ExchangeRate).filter(
        models.ExchangeRate.from_currency.in_(currencies),
        models.ExchangeRate.to_currency == target_currency,
        models.ExchangeRate.rate_date.in_(dates)
    ).all()

    rate_dict: Dict[tuple, float] = {
        (rate.from_currency, rate.rate_date): float(rate.rate) for rate in exchange_rates
    }

    if group_by:
        if group_by == "month":
            period_expr = func.to_char(models.IndicatorValue.value_date, 'YYYY-MM')
        elif group_by == "quarter":
            period_expr = func.concat(
                func.extract('year', models.IndicatorValue.value_date),
                '-Q',
                func.extract('quarter', models.IndicatorValue.value_date)
            )

        grouped_query = db.query(
            period_expr.label('period'),
            (models.IndicatorValue.value * models.Indicator.importance).label('weighted_value'),
            models.IndicatorValue.currency_code,
            models.IndicatorValue.value_date
        ).join(
            models.Indicator, models.IndicatorValue.indicator_id == models.Indicator.id
        ).filter(
            models.IndicatorValue.enterprise_id == enterprise_id
        )

        if indicator_id:
            grouped_query = grouped_query.filter(models.IndicatorValue.indicator_id == indicator_id)
        if from_date:
            grouped_query = grouped_query.filter(models.IndicatorValue.value_date >= from_date)
        if to_date:
            grouped_query = grouped_query.filter(models.IndicatorValue.value_date <= to_date)

        grouped_results = grouped_query.all()

        grouped_dict = {}
        for period, weighted_value, currency_code, value_date in grouped_results:
            if period not in grouped_dict:
                grouped_dict[period] = {"total_weighted_value": 0.0, "warning": None, "has_missing_rate": False}
            
            if currency_code == target_currency:
                converted_value = float(weighted_value)
            else:
                rate_key = (currency_code, value_date)
                if rate_key in rate_dict:
                    converted_value = round(float(weighted_value) * rate_dict[rate_key], 2)
                else:
                    grouped_dict[period]["has_missing_rate"] = True
                    converted_value = None

            if converted_value is not None:
                grouped_dict[period]["total_weighted_value"] += converted_value
            else:
                grouped_dict[period]["has_missing_rate"] = True

        result = []
        for period, data in grouped_dict.items():
            result.append(schemas.WeightedIndicatorGroupSchema(
                period=period,
                total_weighted_value=round(data["total_weighted_value"], 2) if not data["has_missing_rate"] else None,
                warning="No exchange rate found for some values" if data["has_missing_rate"] else None
            ))
        result.sort(key=lambda x: x.period)
        return result

    if aggregate:
        total_weighted_value = 0.0
        warning = None
        for item, indicator_name, importance in indicator_values:
            weighted_value = float(item.value) * float(importance)
            if item.currency_code == target_currency:
                converted_weighted_value = weighted_value
            else:
                rate_key = (item.currency_code, item.value_date)
                if rate_key in rate_dict:
                    converted_weighted_value = round(weighted_value * rate_dict[rate_key], 2)
                else:
                    warning = f"No exchange rate found for some values"
                    converted_weighted_value = None
            if converted_weighted_value is not None:
                total_weighted_value += converted_weighted_value
            else:
                total_weighted_value = None
                warning = f"No exchange rate found for some values"
                break

        return schemas.WeightedIndicatorAggregateSchema(
            total_weighted_value=total_weighted_value,
            warning=warning
        )

    result = []
    for item, indicator_name, importance in indicator_values:
        weighted_value = float(item.value) * float(importance)
        item_dict = {
            "indicator_id": item.indicator_id,
            "indicator_name": indicator_name,
            "value_date": item.value_date,
            "original_value": float(item.value),
            "currency_code": item.currency_code,
            "importance": float(importance),
            "weighted_value": weighted_value,
            "converted_weighted_value": None,
            "warning": None
        }
        if item.currency_code == target_currency:
            item_dict["converted_weighted_value"] = round(weighted_value, 2)
        else:
            rate_key = (item.currency_code, item.value_date)
            if rate_key in rate_dict:
                item_dict["converted_weighted_value"] = round(weighted_value * rate_dict[rate_key], 2)
            else:
                item_dict["converted_weighted_value"] = None
                item_dict["warning"] = f"No exchange rate found for {item.currency_code} to {target_currency} on {item.value_date}"
        result.append(item_dict)

    return result