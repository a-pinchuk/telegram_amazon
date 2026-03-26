from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id, User.is_active == True)
    )
    return result.scalar_one_or_none()


async def get_all_active_participants(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(User.role == "participant", User.is_active == True).order_by(User.full_name)
    )
    return list(result.scalars().all())


async def get_all_active_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(User.is_active == True).order_by(User.full_name)
    )
    return list(result.scalars().all())


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: str | None = None,
    role: str = "participant",
) -> User:
    user = User(
        telegram_id=telegram_id,
        full_name=full_name,
        username=username,
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def deactivate_user(session: AsyncSession, user_id: int) -> None:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.is_active = False
        await session.flush()
