import asyncio

from flask_bot import run_quart
from main import main


async def main2():
    await asyncio.gather(
        run_quart(),
        main(),
    )


if __name__ == '__main__':
    asyncio.run(main2())