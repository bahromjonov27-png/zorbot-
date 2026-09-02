from telegram import Update
from telegram.ext import Application

from bot import build_application


app: Application = build_application()


async def handler(request):
    if request.method != "POST":
        return {
            "statusCode": 405,
            "body": "Method Not Allowed",
        }

    data = await request.json()
    update = Update.de_json(data, app.bot)

    await app.initialize()
    try:
        await app.process_update(update)
    finally:
        await app.shutdown()

    return {
        "statusCode": 200,
        "body": "OK",
    }
