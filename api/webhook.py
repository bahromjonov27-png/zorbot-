import asyncio
import json
from http.server import BaseHTTPRequestHandler

from telegram import Update
from bot import build_application


application = build_application()


async def process_update(data):
    update = Update.de_json(data, application.bot)

    await application.initialize()
    try:
        await application.process_update(update)
    finally:
        await application.shutdown()


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
