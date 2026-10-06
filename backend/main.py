import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.disputes import router as disputes_router
from routers.donations import router as donations_router
from routers.matches import router as matches_router
from routers.matching import router as matching_router
from routers.notifications import router as notifications_router
from routers.reliability import router as reliability_router
from routers.users import router as users_router
from services.matching_engine import run_matching_round_in_new_session

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_matching_round_in_new_session,
        "interval",
        minutes=10,
        id="matching_round",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Food Redistribution Platform API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(donations_router)
app.include_router(matches_router)
app.include_router(disputes_router)
app.include_router(notifications_router)
app.include_router(reliability_router)
app.include_router(matching_router)


@app.get("/")
def root():
    return {"message": "API is running"}
