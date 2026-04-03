from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.goto('http://35.224.3.54/')
    page.wait_for_load_state('networkidle')
    page.screenshot(path='shot_f7_recon_initial.png', full_page=True)

    # Print chip texts
    chips = page.locator('.example-chip').all()
    print(f'Found {len(chips)} chips:')
    for c in chips:
        print(' -', c.inner_text())

    # Print all class names on the page (sample)
    html = page.content()
    import re
    classes = re.findall(r'class=["\']([^"\']+)["\']', html)
    unique = sorted(set(classes))
    print('\nUnique classes:')
    for cls in unique:
        print(' ', cls)

    browser.close()
