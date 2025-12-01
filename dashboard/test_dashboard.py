"""Test the production dashboard with Playwright to see what's actually rendering."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Go to production dashboard
    print("Loading production dashboard...")
    page.goto('https://sales-agent-dashboard-fawn.vercel.app')

    # Wait for network to settle (important for SWR data fetching)
    print("Waiting for network idle...")
    page.wait_for_load_state('networkidle')

    # Wait a bit more for React hydration and SWR to fetch
    page.wait_for_timeout(3000)

    # Take screenshot
    screenshot_path = '/tmp/dashboard_screenshot.png'
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"Screenshot saved to: {screenshot_path}")

    # Check for console errors
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    # Get page content to inspect
    content = page.content()

    # Look for key elements
    print("\n--- Page State Check ---")

    # Check System Status
    system_status = page.locator('text=System Status').first
    if system_status:
        parent = system_status.locator('xpath=../..')
        status_text = parent.inner_text()
        print(f"System Status area: {status_text[:100]}...")

    # Check for loading indicators
    loading_count = page.locator('text=Loading').count()
    print(f"'Loading' text count: {loading_count}")

    # Check for actual data
    icp_queue = page.locator('text=ICP Queue').first
    print(f"ICP Queue found: {icp_queue.is_visible() if icp_queue else False}")

    # Check BDR Work Queue
    bdr_queue = page.locator('text=BDR Work Queue').first
    print(f"BDR Work Queue found: {bdr_queue.is_visible() if bdr_queue else False}")

    # Look for company names (real data)
    solar_states = page.locator('text=Solar States').count()
    print(f"'Solar States' (real data) count: {solar_states}")

    # Look for skeleton loaders
    skeleton_count = len(page.locator('[class*="skeleton"]').all())
    print(f"Skeleton loaders visible: {skeleton_count}")

    # Get any error messages
    error_elements = page.locator('[class*="error"]').all()
    print(f"Error elements: {len(error_elements)}")

    # Print console errors if any
    if console_errors:
        print(f"\nConsole errors: {console_errors}")

    browser.close()
    print(f"\n✅ Done! View screenshot at: {screenshot_path}")
