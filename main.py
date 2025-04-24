from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import router
from models import Base, engine

app = FastAPI()

# Добавить CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(router)