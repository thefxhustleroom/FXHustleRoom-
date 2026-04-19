import traceback

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import add_event, get_or_create_user
from app.keyboards import language_keyboard, single_button
from app.languages import TELEGRAM_TO_SUPPORTED
from app.states import UserFlow
from app.texts import t

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    logger.info(f"[start_handler] /start received from user {user_id}")

    try:
        # --- Resolve language ---
        raw_lang = (message.from_user.language_code or "").split("-")[0]
        language_code = TELEGRAM_TO_SUPPORTED.get(raw_lang, settings.default_language)
        logger.info(
            f"[start_handler] user={user_id} raw_lang={raw_lang!r} "
            f"resolved_lang={language_code!r}"
        )

        # --- Upsert user in DB ---
        logger.info(f"[start_handler] user={user_id} calling get_or_create_user")
        try:
            await get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
                language=language_code,
            )
            logger.info(f"[start_handler] user={user_id} get_or_create_user OK")
        except Exception:
            logger.error(
                f"[start_handler] user={user_id} get_or_create_user FAILED:\n"
                + traceback.format_exc()
            )
            raise

        # --- Commit session ---
        logger.info(f"[start_handler] user={user_id} committing session")
        try:
            await session.commit()
            logger.info(f"[start_handler] user={user_id} session.commit OK")
        except Exception:
            logger.error(
                f"[start_handler] user={user_id} session.commit FAILED:\n"
                + traceback.format_exc()
            )
            raise

        # --- Set FSM state ---
        logger.info(f"[start_handler] user={user_id} setting FSM state selecting_language")
        await state.set_state(UserFlow.selecting_language)

        # --- Build reply markup ---
        logger.info(f"[start_handler] user={user_id} building language_keyboard")
        try:
            markup = language_keyboard()
            logger.info(f"[start_handler] user={user_id} language_keyboard OK")
        except Exception:
            logger.error(
                f"[start_handler] user={user_id} language_keyboard() FAILED:\n"
                + traceback.format_exc()
            )
            raise

        # --- Resolve message text ---
        logger.info(f"[start_handler] user={user_id} resolving t('select_language', {language_code!r})")
        try:
            text = t("select_language", language_code)
            logger.info(f"[start_handler] user={user_id} t() resolved to: {text!r}")
        except Exception:
            logger.error(
                f"[start_handler] user={user_id} t('select_language', ...) FAILED:\n"
                + traceback.format_exc()
            )
            raise

        # --- Send reply ---
        logger.info(f"[start_handler] user={user_id} calling message.answer()")
        try:
            await message.answer(text, reply_markup=markup)
            logger.info(f"[start_handler] user={user_id} message.answer() OK — response sent")
        except Exception:
            logger.error(
                f"[start_handler] user={user_id} message.answer() FAILED:\n"
                + traceback.format_exc()
            )
            raise

    except Exception:
        logger.error(
            f"[start_handler] user={user_id} unhandled exception — handler aborted:\n"
            + traceback.format_exc()
        )


@router.callback_query(F.data.startswith("lang:"))
async def language_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user_id = callback.from_user.id if callback.from_user else "unknown"
    raw_code = callback.data or ""
    logger.info(f"[language_selected] callback received from user={user_id} data={raw_code!r}")

    try:
        code = raw_code.split(":", 1)[1]
        logger.info(f"[language_selected] user={user_id} parsed language code={code!r}")

        # --- Upsert user in DB ---
        logger.info(f"[language_selected] user={user_id} calling get_or_create_user")
        try:
            user = await get_or_create_user(
                session,
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                full_name=callback.from_user.full_name,
                language=code,
            )
            logger.info(f"[language_selected] user={user_id} get_or_create_user OK")
        except Exception:
            logger.error(
                f"[language_selected] user={user_id} get_or_create_user FAILED:\n"
                + traceback.format_exc()
            )
            raise

        user.language = code
        user.state = "TERMS"

        # --- Record event ---
        logger.info(f"[language_selected] user={user_id} adding language_selected event")
        try:
            await add_event(session, user, "language_selected", {"language": code})
            logger.info(f"[language_selected] user={user_id} add_event OK")
        except Exception:
            logger.error(
                f"[language_selected] user={user_id} add_event FAILED:\n"
                + traceback.format_exc()
            )
            raise

        # --- Commit session ---
        logger.info(f"[language_selected] user={user_id} committing session")
        try:
            await session.commit()
            logger.info(f"[language_selected] user={user_id} session.commit OK")
        except Exception:
            logger.error(
                f"[language_selected] user={user_id} session.commit FAILED:\n"
                + traceback.format_exc()
            )
            raise

        # --- Set FSM state ---
        logger.info(f"[language_selected] user={user_id} setting FSM state terms")
        await state.set_state(UserFlow.terms)

        # --- Send welcome message ---
        logger.info(f"[language_selected] user={user_id} sending welcome message (lang={code!r})")
        try:
            await callback.message.answer(t("welcome", code))
            logger.info(f"[language_selected] user={user_id} welcome message sent OK")
        except Exception:
            logger.error(
                f"[language_selected] user={user_id} sending welcome message FAILED:\n"
                + traceback.format_exc()
            )
            raise

        # --- Send terms message ---
        logger.info(f"[language_selected] user={user_id} sending terms message (lang={code!r})")
        try:
            await callback.message.answer(
                t("terms", code),
                reply_markup=single_button("I Accept", "terms:accept"),
            )
            logger.info(f"[language_selected] user={user_id} terms message sent OK")
        except Exception:
            logger.error(
                f"[language_selected] user={user_id} sending terms message FAILED:\n"
                + traceback.format_exc()
            )
            raise

        # --- Acknowledge callback ---
        logger.info(f"[language_selected] user={user_id} acknowledging callback")
        await callback.answer()
        logger.info(f"[language_selected] user={user_id} callback.answer() OK — handler complete")

    except Exception:
        logger.error(
            f"[language_selected] user={user_id} unhandled exception — handler aborted:\n"
            + traceback.format_exc()
        )
