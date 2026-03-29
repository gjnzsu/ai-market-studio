"""Capture inline chart in assistant chat bubble."""
import asyncio
from playwright.async_api import async_playwright

OUTPUT = "C:/SourceCode/ai-market-studio/shot_06_inline_chart.png"
URL = "http://35.224.3.54/"
PROMPT = "Show me EUR/USD trend for the last 3 days"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        print(f"Navigating to {URL} ...")
        await page.goto(URL, wait_until="networkidle", timeout=30_000)
        print("Page loaded.")

        # Click Chat tab if present and not already active
        chat_tab = page.locator("[data-tab='chat'], #chat-tab, button:has-text('Chat'), a:has-text('Chat')")
        if await chat_tab.count() > 0:
            print("Clicking Chat tab...")
            await chat_tab.first.click()
            await page.wait_for_timeout(1_000)
        else:
            print("No Chat tab found — assuming chat is already visible.")

        # Type prompt
        print("Typing prompt...")
        await page.locator("#user-input").fill(PROMPT)
        await page.wait_for_timeout(300)

        # Click Send
        print("Clicking Send...")
        await page.locator("#send-btn").click()

        # Wait for assistant bubble with canvas (up to 30 s)
        print("Waiting for assistant bubble with canvas...")
        canvas_selector = ".bubble.assistant canvas"
        try:
            await page.wait_for_selector(canvas_selector, timeout=30_000)
            print("Canvas found inside assistant bubble.")
        except Exception:
            # Fall back: wait for any assistant bubble if canvas never appears
            print("Canvas not found within 30 s — falling back to any assistant bubble.")
            await page.wait_for_selector(".bubble.assistant", timeout=5_000)

        # Brief pause so chart renders fully
        await page.wait_for_timeout(1_500)

        await page.screenshot(path=OUTPUT, full_page=False)
        print(f"Screenshot saved to {OUTPUT}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
