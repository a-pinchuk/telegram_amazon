import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import Settings
from bot.db.engine import create_engine, create_session_factory
from bot.db.models import Base
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.db_session import DbSessionMiddleware

from bot.handlers.start import router as start_router
from bot.handlers.admin.manage_users import router as admin_users_router
from bot.handlers.admin.view_reports import router as admin_reports_router
from bot.handlers.employee.daily_report import router as employee_report_router
from bot.handlers.employee.my_stats import router as employee_stats_router
from bot.handlers.employee.edit_report import router as employee_edit_router


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = Settings()

    # Ensure data directory exists
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    engine = create_engine(settings.database_url)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Middleware
    dp.update.outer_middleware(DbSessionMiddleware(session_factory))
    dp.update.outer_middleware(AuthMiddleware(admin_ids=settings.admin_ids))

    # Routers (order matters — more specific first)
    dp.include_routers(
        start_router,
        employee_report_router,
        employee_edit_router,
        employee_stats_router,
        admin_users_router,
        admin_reports_router,
    )

    logging.info("Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
