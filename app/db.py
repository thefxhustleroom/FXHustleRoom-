from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AppSetting, Base, Event, User


async_engine = create_async_engine(settings.database_url, echo=False, future=True)  # type: ignore[arg-type]
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

sync_engine = create_engine(settings.database_sync_url, future=True)  # type: ignore[arg-type]


def get_sync_session() -> Session:
    return Session(sync_engine)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db(retries: int = 5, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Database init attempt {attempt}/{retries}...")
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await seed_default_settings()
            logger.info("Database initialized successfully")
            return
        except Exception as exc:
            logger.warning(f"Database init attempt {attempt}/{retries} failed: {exc}")
            if attempt < retries:
                await asyncio.sleep(delay)
    raise RuntimeError(f"Database initialization failed after {retries} attempts")


async def seed_default_settings() -> None:
    async with AsyncSessionLocal() as session:
        for key, value in {
            "trading_video_file_id": settings.trading_video_file_id or "",
            "first_signal_text": settings.first_signal_text,
        }.items():
            existing = await session.get(AppSetting, key)
            if not existing:
                session.add(AppSetting(key=key, value=value))
        await session.commit()


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None, full_name: str | None, language: str) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            language=language,
        )
        session.add(user)
        await session.flush()
    else:
        user.username = username
        user.full_name = full_name
        if not user.language:
            user.language = language
    return user


async def add_event(session: AsyncSession, user: User, event_type: str, metadata: dict[str, Any] | None = None) -> None:
    session.add(Event(user_id=user.id, event_type=event_type, metadata_json=json.dumps(metadata or {})))


async def set_app_setting(session: AsyncSession, key: str, value: str) -> None:
    record = await session.get(AppSetting, key)
    if record:
        record.value = value
    else:
        session.add(AppSetting(key=key, value=value))
    await session.commit()


async def get_app_setting(session: AsyncSession, key: str, default: str | None = None) -> str | None:
    record = await session.get(AppSetting, key)
    if record and record.value is not None:
        return record.value
    return default
