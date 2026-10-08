from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routes import matches, analysis

Base.metadata.create_all(bind=engine)

app = FastAPI(title="VolleyStat API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches.router, prefix="/matches", tags=["Matches"])
app.include_router(analysis.router, prefix="/analysis", tags=["Analyse IA"])
