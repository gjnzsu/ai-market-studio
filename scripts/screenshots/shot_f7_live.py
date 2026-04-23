from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.goto('http://35.224.3.54/')
    page.wait_for_load_state('networkidle')

    # Click the Market Insight example chip
    chips = page.locator('.ex-chip').all()
    chip_clicked = False
    for chip in chips:
        text = chip.inner_text()
        if 'insight' in text.lower():
            chip.click()
            chip_clicked = True
            print(f'Clicked chip: {text}')
            break

    if not chip_clicked:
        page.locator('#user-input').fill('Give me a market insight on EUR/USD and GBP/USD')
        page.locator('#send-btn').click()
        print('Typed and sent message')

    # Wait for assistant bubble to appear (up to 35s)
    page.wait_for_selector('.bubble.assistant', timeout=35000)
    # Extra time for rate chips / news cards to fully render
    time.sleep(4)

    page.screenshot(path='shot_f7_live.png', full_page=True)
    print('Screenshot saved: shot_f7_live.png')
    browser.close()
