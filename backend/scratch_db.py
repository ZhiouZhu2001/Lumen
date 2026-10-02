import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    engine = create_async_engine("postgresql+asyncpg://lumen:lumen_admin@localhost:5434/lumen", echo=True)
    async with engine.connect() as conn:
        print(await conn.scalar(text("SELECT 1")))
    
    await engine.dispose()

asyncio.run(main())