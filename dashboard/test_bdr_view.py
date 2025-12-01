"""Test the BDR View tab specifically."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    print("Loading production dashboard...")
    page.goto('https://sales-agent-dashboard-fawn.vercel.app')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Click on BDR View tab
    print("Clicking BDR View tab...")
    bdr_tab = page.locator('text=BDR View').first
    if bdr_tab.is_visible():
        bdr_tab.click()
        page.wait_for_timeout(3000)  # Wait for data to load

        # Take screenshot
        screenshot_path = '/tmp/bdr_view_screenshot.png'
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"BDR View screenshot saved to: {screenshot_path}")

        # Check for BDR Work Queue
        work_queue = page.locator('text=BDR Work Queue').first
        print(f"BDR Work Queue visible: {work_queue.is_visible() if work_queue else False}")

        # Check for Outreach Metrics
        outreach = page.locator('text=Outreach Metrics').first
        print(f"Outreach Metrics visible: {outreach.is_visible() if outreach else False}")

        # Check for tasks
        task_count = page.locator('[class*="task"]').count()
        print(f"Task elements found: {task_count}")
    else:
        print("BDR View tab not found!")

    browser.close()
    print("\n✅ Done!")
