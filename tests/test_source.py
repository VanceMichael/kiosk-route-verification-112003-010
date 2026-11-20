from threading import Thread
import unittest

from playwright.sync_api import sync_playwright
from kiosk import create_source


class KioskSourceTest(unittest.TestCase):
    def setUp(self):
        server = create_source()
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.base = f"http://127.0.0.1:{server.server_port}"
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.shutdown)

    def new_page(self, context):
        page = context.new_page()
        page.set_default_timeout(5000)
        page.goto(self.base)
        return page

    def advance(self, page, turn):
        page.get_by_role("link", name="现场演练轮次").click()
        page.get_by_label("下个轮次").fill(str(turn))
        page.get_by_role("button", name="推进轮次").click()

    def connect(self, page, terminal="K1", entry="E1", language="zh", mode="keyboard"):
        page.get_by_role("link", name="终端连接").click()
        page.get_by_label("终端", exact=True).select_option(terminal)
        page.get_by_label("入口").select_option(entry)
        page.get_by_label("语言").select_option(language)
        page.get_by_label("操作方式").select_option(mode)
        page.get_by_role("button", name="进入导览").click()

    def focus_and_enter(self, page, title):
        for _ in range(25):
            if page.locator(":focus").count() and page.locator(":focus").inner_text() == title:
                page.keyboard.press("Enter")
                page.wait_for_load_state()
                return
            page.keyboard.press("Tab")
        self.fail(f"键盘焦点不能到达 {title}")

    def context_value(self, page, key):
        return page.locator("dt").filter(has_text=key).locator("+ dd").inner_text()

    def test_same_url_does_not_prove_branch_or_installed_version(self):
        with sync_playwright() as playwright, playwright.chromium.launch() as browser:
            with browser.new_context() as operator, browser.new_context() as visitor:
                ops = self.new_page(operator)
                page = self.new_page(visitor)
                self.advance(ops, 2)
                self.connect(page)
                address = page.url
                self.assertEqual(self.context_value(page,"首页版本"), "V19")
                self.focus_and_enter(page, "一层展厅")
                self.assertEqual(page.url, address)
                self.assertTrue(page.get_by_role("dialog").is_visible())
                page.keyboard.press("Enter")
                self.assertFalse(page.get_by_role("dialog").is_visible())
                self.focus_and_enter(page, "拓印")
                self.assertEqual(self.context_value(page,"本页安装版"), "V18")
                self.assertTrue(page.get_by_role("heading", name="W22 A").is_visible())
                competitor = self.new_page(operator)
                self.connect(competitor)
                self.assertTrue(competitor.get_by_role("heading", name="终端检查时段不可用").is_visible())
                self.advance(ops, 3)
                page.reload()
                self.assertTrue(page.get_by_role("heading", name="终端已返回首页").is_visible())

    def test_touch_and_keyboard_paths_show_different_publishable_evidence(self):
        with sync_playwright() as playwright, playwright.chromium.launch() as browser:
            with browser.new_context(has_touch=True) as touch, browser.new_context() as keyboard:
                page = self.new_page(touch)
                self.advance(page, 3)
                self.connect(page, mode="touch")
                page.get_by_role("button", name="二层展厅").tap()
                self.assertTrue(page.get_by_role("heading", name="W26 C").is_visible())
                self.assertTrue(page.get_by_text("cancelled", exact=True).is_visible())
                page.get_by_role("button", name="结束检查").click()
                page = self.new_page(keyboard)
                self.connect(page)
                self.focus_and_enter(page, "临时分流")
                page.keyboard.press("Enter")
                self.focus_and_enter(page, "无台阶通行")
                self.assertTrue(page.get_by_role("heading", name="W22 D").is_visible())
                self.focus_and_enter(page, "馆外工坊")
                self.assertEqual(page.get_by_role("listitem").all_text_contents(), ["E1", "M", "OUT", "ANNEX"])
                page.get_by_role("link", name="现场通行").click()
                table = page.get_by_role("table", name="有向通行表")
                self.assertIn("10:35", table.get_by_role("row").filter(has_text="OUT ANNEX").inner_text())

    def test_stop_notice_targets_one_recipient_until_they_acknowledge(self):
        with sync_playwright() as playwright, playwright.chromium.launch() as browser:
            with browser.new_context() as operator:
                page = self.new_page(operator)
                self.advance(page, 2)
                page.get_by_role("link", name="志愿者公告台").click()
                for label, val in {"通知号":"N-RM1", "原交接号":"RM1", "服务点":"服务甲", "停发时间":"10:00"}.items():
                    page.get_by_label(label, exact=True).fill(val)
                page.get_by_role("button", name="发停用通知").click()
                self.assertTrue(page.get_by_text("通知回条尚未显示").is_visible())
                self.advance(page, 4)
                page.get_by_role("link", name="志愿者公告台").click()
                page.get_by_label("查询通知号").fill("N-RM1")
                page.get_by_role("button", name="查询通知").click()
                self.assertTrue(page.get_by_text("通知回条 N-RM1 停发已读", exact=True).is_visible())
                row = page.get_by_role("row").filter(has_text="RM3")
                self.assertNotIn("停发", row.inner_text())
