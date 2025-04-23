from fastapi import FastAPI
from routers import router
from models import Base, engine

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.include_router(router)