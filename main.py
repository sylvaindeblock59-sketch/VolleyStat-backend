from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routes import matches, stats
Base.metadata.create_all(bind=engine)
app = FastAPI(title="VolleyStat API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(matches.router, prefix="/matches", tags=["Matches"])
app.include_router(stats.router,   prefix="/stats",   tags=["Stats"])