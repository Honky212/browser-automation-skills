from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from browser_automation_skills.browser_launcher import BrowserLauncher


class _LocalPageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<!doctype html><html><head><title>Local Browser Test</title></head><body>Chromium is working</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


@pytest.fixture
def local_page_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LocalPageHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


async def test_browser_launcher_navigates_to_local_page_and_closes(local_page_url):
    launcher = BrowserLauncher(headless=True)
    try:
        context = await launcher.launch()
        page = await context.new_page()
        await page.goto(local_page_url)

        assert await page.title() == "Local Browser Test"
        assert await page.locator("body").inner_text() == "Chromium is working"
    finally:
        await launcher.close()
