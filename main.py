from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

import models
from database import Base, SessionLocal, engine
from routers import auth, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables for this learning project.
    Base.metadata.create_all(bind=engine)

    # Fail at startup if the database cannot be reached.
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))

    yield


app = FastAPI(
    title="Task Management API",
    description=(
        "A Task Management API with PostgreSQL, "
        "Pydantic validation, JWT authentication, "
        "and protected CRUD operations."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# Register routers.
app.include_router(auth.router)
app.include_router(tasks.router)


@app.get("/", tags=["General"])
def root():
    return {
        "message": "Welcome to the Task Management API",
        "docs": "/docs",
        "authentication": "/auth",
        "tasks": "/tasks/",
    }


@app.get("/health", tags=["General"])
def health_check():
    return {"status": "ok"}