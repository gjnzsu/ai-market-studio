from playwright.sync_api import sync_playwright

ERRORS = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.on('console', lambda msg: ERRORS.append(f'[{msg.type}] {msg.text}') if msg.type in ('error', 'warning') else None)
    page.on('pageerror', lambda err: ERRORS.append(f'[pageerror] {err}'))

    print('=== Navigating to app ===')
    page.goto('http://localhost:8000')
    page.wait_for_load_state('networkidle')
    page.screenshot(path='shot_01_initial.png', full_page=True)
    print('shot_01_initial.png saved')

    tabs = page.locator('.nav-tab').all()
    tab_labels = [t.inner_text() for t in tabs]
    print(f'Tabs found: {tab_labels}')
    assert len(tabs) >= 2, f'Expected >= 2 tabs, got {len(tabs)}'
    print('Tab nav: OK')
    print('=== Clicking Dashboard tab ===')
    page.locator('.nav-tab', has_text='Dashboard').click()
    page.wait_for_timeout(500)
    page.screenshot(path='shot_02_dashboard.png', full_page=True)
    print('shot_02_dashboard.png saved')

    assert page.locator('#dash-preset').is_visible(), 'Preset selector not visible'
    print('Preset selector: OK')
    assert page.locator('#dash-start').is_visible(), 'Start date not visible'
    assert page.locator('#dash-end').is_visible(), 'End date not visible'
    start_val = page.locator('#dash-start').input_value()
    end_val   = page.locator('#dash-end').input_value()
    print(f'Date pickers: OK  (start={start_val}, end={end_val})')
    assert page.locator('#dash-load-btn').is_visible(), 'Load button not visible'
    print('Load button: OK')

    print('=== Loading dashboard data ===')
    page.locator('#dash-load-btn').click()
    page.wait_for_timeout(10000)
    page.screenshot(path='shot_03_dashboard_loaded.png', full_page=True)
    print('shot_03_dashboard_loaded.png saved')
    status = page.locator('#dash-status').inner_text()
    print(f'Dashboard status: "{status}"')
    panels = page.locator('.chart-panel').all()
    print(f'Chart panels rendered: {len(panels)}')

    print('=== Switching to Chat tab ===')
    page.locator('.nav-tab', has_text='Chat').click()
    page.wait_for_timeout(300)
    page.screenshot(path='shot_04_chat.png', full_page=True)
    print('shot_04_chat.png saved')

    print('=== Sending chat message ===')
    page.locator('#user-input').fill('What is the EUR/USD rate?')
    page.locator('#send-btn').click()
    page.wait_for_function("document.querySelectorAll('.bubble.assistant').length > 0", timeout=20000)
    page.screenshot(path='shot_05_chat_response.png', full_page=True)
    print('shot_05_chat_response.png saved')
    reply = page.locator('.bubble.assistant').first.inner_text()
    print(f'Assistant reply: {reply[:300]}')

    js_errors = [e for e in ERRORS if 'error' in e.lower()]
    print(f'Console errors: {len(js_errors)}')
    for e in js_errors:
        print(f'  {e}')

    print('\n=== All checks passed ===')
    browser.close()

