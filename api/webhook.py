import asyncio
import json
from http.server import BaseHTTPRequestHandler

from telegram import Update
from bot import build_application


bot_app = build_application()


async def process_update(data):
    update = Update.de_json(data, bot_app.bot)

    await bot_app.initialize()
    try:
        await bot_app.process_update(update)
    finally:
        await bot_app.shutdown()


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            asyncio.run(process_update(data))

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        except Exception as e:
            print("WEBHOOK ERROR:", repr(e))

            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Internal Server Error")

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Webhook is running")
