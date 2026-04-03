from __future__ import annotations

from decimal import Decimal

from aiogram import Bot
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Signal


class IncomingSignal(BaseModel):
    pair: str
    direction: str
    entry: Decimal
    sl: Decimal
    tp1: Decimal | None = None
    tp2: Decimal | None = None
    risk_percentage: Decimal | None = None
    chart_image_url: HttpUrl | None = None


def format_signal(signal: IncomingSignal) -> str:
    lines = [
        f"{signal.pair.upper()} {signal.direction.upper()}",
        "",
        f"Entry: {signal.entry}",
        f"Stop Loss: {signal.sl}",
    ]
    if signal.tp1 is not None:
        lines.append(f"Take Profit 1: {signal.tp1}")
    if signal.tp2 is not None:
        lines.append(f"Take Profit 2: {signal.tp2}")
    if signal.risk_percentage is not None:
        lines.append(f"Risk: {signal.risk_percentage}%")
    return "\n".join(lines)


async def persist_signal(session: AsyncSession, payload: IncomingSignal) -> Signal:
    signal = Signal(
        pair=payload.pair.upper(),
        direction=payload.direction.upper(),
        entry=payload.entry,
        sl=payload.sl,
        tp1=payload.tp1,
        tp2=payload.tp2,
        risk_percentage=payload.risk_percentage,
        chart_image_url=str(payload.chart_image_url) if payload.chart_image_url else None,
    )
    session.add(signal)
    await session.commit()
    await session.refresh(signal)
    return signal


async def send_signal_to_premium_group(bot: Bot, payload: IncomingSignal) -> None:
    text = format_signal(payload)
    if payload.chart_image_url:
        await bot.send_photo(settings.premium_group_id, photo=str(payload.chart_image_url), caption=text)
    else:
        await bot.send_message(settings.premium_group_id, text)
