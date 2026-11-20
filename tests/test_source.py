from pathlib import Path
from threading import Thread
import json
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from kiosk import create_source


class SourceTest(unittest.TestCase):
    def setUp(self):
        self.server = create_source()
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.server.shutdown)

    def source_response(self, path):
        try:
            with urlopen(self.base + path, timeout=2) as response:
                return response.status, response.read()
        except HTTPError as error:
            with error:
                return error.code, error.read()

    def test_input_documents(self):
        for name in ['assignments', 'access', 'briefings', 'terminals']:
            with self.subTest(document=name):
                value = Path("data", name + ".json").read_text(encoding="utf-8")
                self.assertTrue(json.loads(value))

    def test_mode_controls_and_scope_change(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright, playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(self.base)
            page.get_by_label("发布轮次").select_option("2")
            page.get_by_role("button", name="进入导览").click()
            page.keyboard.press("Tab")
            self.assertEqual(page.locator(":focus").inner_text(), "导览首页")
            page.keyboard.press("Tab")
            self.assertEqual(page.locator(":focus").inner_text(), "一层展厅")
            page.keyboard.press("Tab")
            self.assertEqual(page.locator(":focus").inner_text(), "三层展厅")
            page.keyboard.press("Enter")
            page.get_by_role("heading", name="导览已更新").wait_for()
            self.assertTrue(page.get_by_role("heading", name="导览已更新").is_visible())
            page.get_by_role("link", name="导览首页").click()
            touch = browser.new_page(has_touch=True)
            touch.goto(page.url)
            touch.get_by_role("button", name="二层展厅").tap()
            touch.get_by_role("link", name="拓印侧路").tap()
            touch.get_by_role("heading", name="W22 B").wait_for()
            self.assertTrue(touch.get_by_role("heading", name="W22 B").is_visible())

