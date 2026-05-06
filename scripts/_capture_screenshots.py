"""One-off screenshot capture for README. Run with backend+frontend already up."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)

FRONT = "http://localhost:29501"
API = "http://localhost:18437"
PREVIEW_SLUG = "newsletter-20260326"
ADMIN_USER = "admin"
ADMIN_PASS = "change-me"
VIEWPORT = {"width": 1440, "height": 900}


def settle(page, ms=1500):
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def shoot(page, name):
    target = OUT / name
    page.screenshot(path=str(target), full_page=False)
    print(f"saved {target.relative_to(ROOT)}")


def try_fill(page, selectors, value):
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                el.fill(value)
                return True
        except Exception:
            continue
    return False


def try_click(page, selectors):
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                el.click()
                return True
        except Exception:
            continue
    return False


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport=VIEWPORT, locale="ko-KR")
    page = ctx.new_page()

    # 1) public list
    page.goto(f"{FRONT}/newsletters", wait_until="domcontentloaded")
    settle(page, 1500)
    shoot(page, "list.png")

    # 2) preview (HTML+PDF asset)
    page.goto(f"{FRONT}/newsletters/{PREVIEW_SLUG}", wait_until="domcontentloaded")
    settle(page, 2500)
    shoot(page, "preview.png")

    # 3) admin (authenticate via API, then capture /admin/newsletters)
    api_resp = ctx.request.post(
        f"{API}/api/v1/auth/login",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    print(f"login api status: {api_resp.status}")
    page.goto(f"{FRONT}/admin/newsletters", wait_until="domcontentloaded")
    settle(page, 2500)
    print(f"admin url: {page.url}")
    shoot(page, "admin.png")

    browser.close()
print("done")
