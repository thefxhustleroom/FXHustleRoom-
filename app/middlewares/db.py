from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Railway provides this automatically
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix for asyncpg
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create engine
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
)

Base = declarative_base()

# Initialize database
async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
