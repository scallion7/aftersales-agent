"""Customer workspace restores only the selected identity and session."""

import os
import unittest

from app.scripts.demo_stack import DemoStack


@unittest.skipUnless(os.environ.get("RUN_BROWSER_E2E") == "1", "Requires Chromium")
class WorkspaceScopeTests(unittest.TestCase):
    def test_late_history_and_queries_cannot_replace_another_session_or_identity(self):
        from playwright.sync_api import expect, sync_playwright

        with DemoStack() as stack, sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto(stack.url + "/workspace")
            page.locator("#token").fill("demo-user")
            page.locator("#session").fill("scope-a")
            page.locator("#connect").click()
            expect(page.locator("#status")).to_contain_text("会话已连接")
            page.locator("#message").fill(
                "我是会话甲的客户，请为订单 ORD-20240125-006 创建售后工单。"
            )
            page.locator("#send").click()
            expect(page.locator("#status")).to_contain_text(
                "任务状态：已完成", timeout=20000
            )
            expect(page.locator("#events")).to_contain_text("run.completed")
            expect(page.locator("#conversation")).to_contain_text(
                "回复确认仅授权当前唯一提案"
            )
            live_reply = page.locator("#conversation .bubble").last.inner_text()
            # Delay an order lookup and an already authenticated history
            # response after the real server has answered both requests.
            page.evaluate("""() => {
              const realFetch = window.fetch.bind(window);
              window.resumeScope = [];
              window.fetch = async (path, init) => {
                const res = await realFetch(path, init);
                if (!window.releaseScope && (String(path).includes('/orders/ORD-')
                    || String(path).includes('/scope-a?conversation_only=true'))) {
                  await new Promise(resolve => window.resumeScope.push(resolve));
                }
                return res;
              };
            }""")
            page.locator("#order").fill("ORD-20240115-001")
            page.locator("#queryOrder").click()
            page.locator("#connect").click()
            page.wait_for_function("window.resumeScope.length === 2")
            page.locator("#session").fill("scope-b")
            expect(page.locator("#conversation")).to_be_empty()
            expect(page.locator("#events")).to_be_empty()
            page.locator("#connect").click()
            expect(page.locator("#status")).to_contain_text("会话已连接")
            page.evaluate(
                "() => {window.releaseScope = true; window.resumeScope.forEach(resolve => resolve());}"
            )
            page.locator("#message").fill("你好，这是会话乙的咨询。")
            page.locator("#send").click()
            expect(page.locator("#status")).to_contain_text(
                "任务状态：已完成", timeout=20000
            )
            expect(page.locator("#conversation")).to_contain_text("会话乙")
            expect(page.locator("#conversation")).not_to_contain_text("会话甲")
            expect(page.locator("#orderResult")).to_be_empty()
            page.locator("#session").fill("scope-a")
            page.locator("#connect").click()
            expect(page.locator("#conversation")).to_contain_text("会话甲")
            expect(page.locator("#conversation")).not_to_contain_text("会话乙")
            expect(page.locator("#conversation .bubble").last).to_have_text(live_reply)
            expect(page.locator("#events")).to_contain_text("run.completed")
            page.locator("#token").fill("other-user")
            page.locator("#connect").click()
            expect(page.locator("#status")).to_contain_text("会话已连接")
            expect(page.locator("#conversation")).to_be_empty()
            expect(page.locator("#events")).to_be_empty()
            browser.close()
