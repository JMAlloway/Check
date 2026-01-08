"""Script to create admin user."""
import asyncio
from app.db.session import async_session
from app.models.user import User
from app.core.security import get_password_hash
import uuid


async def create_user():
    async with async_session() as db:
        # Check if user already exists
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.username == 'admin'))
        existing = result.scalar_one_or_none()
        if existing:
            print('User admin already exists!')
            return

        user = User(
            id=str(uuid.uuid4()),
            tenant_id='default',
            email='admin@example.com',
            username='admin',
            hashed_password=get_password_hash('admin123'),
            full_name='Admin User',
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        await db.commit()
        print('Created user: admin / admin123')


if __name__ == "__main__":
    asyncio.run(create_user())
