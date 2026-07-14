"""Capture the three README screenshots from a verified authenticated session."""
import hashlib
import json
import os
import shutil
import tempfile
import zlib
from pathlib import Path
from urllib.parse import urlencode, urlparse

from playwright.sync_api import Locator, Page, sync_playwright

FRONT = os.environ.get("AEROONE_SCREENSHOT_FRONT_URL", "http://localhost:29501").rstrip("/")
API = os.environ.get("AEROONE_SCREENSHOT_API_URL", "http://localhost:18437").rstrip("/")
SCREENSHOT_ADMIN_USERNAME_ENV = "AEROONE_SCREENSHOT_ADMIN_USERNAME"
SCREENSHOT_ADMIN_PASSWORD_ENV = "AEROONE_SCREENSHOT_ADMIN_PASSWORD"
README_SCREENSHOTS = ("dashboard.png", "newsletter.png", "newsletter-dark.png")
VIEWPORT = {"width": 1440, "height": 900}
NAVIGATION_TIMEOUT_MS = 15_000
SETTLE_TIMEOUT_MS = 15_000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
COPY_BUFFER_BYTES = 64 * 1024

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
PUBLISH_JOURNAL = OUT / ".readme-screenshot-publication.json"
PUBLISH_BACKUP_PREFIX = ".readme-screenshot-backup-"


def read_admin_credentials() -> tuple[str, str]:
    names = (SCREENSHOT_ADMIN_USERNAME_ENV, SCREENSHOT_ADMIN_PASSWORD_ENV)
    values = {name: os.environ.pop(name, "") for name in names}
    missing = [name for name in names if not values[name].strip()]
    if missing:
        raise SystemExit(
            "Screenshot capture requires environment-provided administrator credentials. "
            f"Set {', '.join(missing)} and rerun."
        )
    return values[SCREENSHOT_ADMIN_USERNAME_ENV], values[SCREENSHOT_ADMIN_PASSWORD_ENV]


def assert_response_status(response, destination: str) -> None:
    if response is None:
        raise RuntimeError(f"No navigation response for {destination}.")
    if response.status != 200:
        raise RuntimeError(f"Unexpected HTTP {response.status} while opening {destination}.")


def assert_route(page: Page, expected_path: str) -> None:
    current = urlparse(page.url)
    expected = urlparse(f"{FRONT}{expected_path}")
    if (current.scheme, current.netloc, current.path) != (expected.scheme, expected.netloc, expected.path):
        raise RuntimeError(f"Expected {expected_path}, but browser reached {page.url}.")


def settle(page: Page) -> None:
    page.wait_for_load_state("load", timeout=SETTLE_TIMEOUT_MS)
    page.evaluate("async () => { if (document.fonts) await document.fonts.ready; }")
    page.wait_for_timeout(250)


def open_route(page: Page, path: str, ready: Locator) -> None:
    response = page.goto(f"{FRONT}{path}", wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
    assert_response_status(response, path)
    assert_route(page, path)
    ready.wait_for(state="visible", timeout=NAVIGATION_TIMEOUT_MS)
    settle(page)


def assert_newsletter_ready(page: Page) -> None:
    reading = page.get_by_test_id("newsletters-reading")
    if reading.get_attribute("data-calendar-open") != "true":
        raise RuntimeError("Newsletter capture requires the expanded calendar.")
    page.get_by_test_id("newsletters-calendar-panel").wait_for(state="visible", timeout=NAVIGATION_TIMEOUT_MS)
    reading.locator("iframe").first.wait_for(state="visible", timeout=NAVIGATION_TIMEOUT_MS)


def set_newsletter_theme(page: Page, theme: str) -> None:
    query = urlencode({"theme": theme, "next": "/newsletters"})
    response = page.goto(
        f"{FRONT}/theme?{query}",
        wait_until="domcontentloaded",
        timeout=NAVIGATION_TIMEOUT_MS,
    )
    assert_response_status(response, f"/theme?theme={theme}")
    assert_route(page, "/newsletters")
    page.get_by_test_id("newsletters-reading").wait_for(state="visible", timeout=NAVIGATION_TIMEOUT_MS)
    settle(page)
    if page.locator("html").get_attribute("data-theme") != theme:
        raise RuntimeError(f"Newsletter theme did not settle to {theme}.")
    assert_newsletter_ready(page)


def validate_png(path: Path, description: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{description} is missing.")
    try:
        image_size = path.stat().st_size
        with path.open("rb") as image:
            if image.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                raise RuntimeError(f"{description} is not a PNG file.")
            chunk_count = 0
            while True:
                header = image.read(8)
                if len(header) != 8:
                    raise RuntimeError(f"{description} is missing a complete PNG chunk header.")
                length = int.from_bytes(header[:4], "big")
                chunk_type = header[4:]
                if length > image_size - image.tell() - 4:
                    raise RuntimeError(f"{description} has a truncated PNG chunk.")
                if chunk_count == 0 and chunk_type != b"IHDR":
                    raise RuntimeError(f"{description} does not start with an IHDR chunk.")

                crc = zlib.crc32(chunk_type)
                chunk_data = bytearray() if chunk_type == b"IHDR" else None
                remaining = length
                while remaining:
                    block = image.read(min(remaining, COPY_BUFFER_BYTES))
                    if not block:
                        raise RuntimeError(f"{description} has a truncated PNG chunk.")
                    crc = zlib.crc32(block, crc)
                    if chunk_data is not None:
                        chunk_data.extend(block)
                    remaining -= len(block)

                expected_crc = image.read(4)
                if len(expected_crc) != 4 or crc & 0xFFFFFFFF != int.from_bytes(expected_crc, "big"):
                    raise RuntimeError(f"{description} has an invalid PNG checksum.")
                if chunk_type == b"IHDR":
                    if chunk_count != 0 or length != 13:
                        raise RuntimeError(f"{description} has an invalid IHDR chunk.")
                    if not chunk_data or int.from_bytes(chunk_data[:4], "big") == 0 or int.from_bytes(chunk_data[4:8], "big") == 0:
                        raise RuntimeError(f"{description} has invalid PNG dimensions.")
                if chunk_type == b"IEND":
                    if length != 0 or image.read(1):
                        raise RuntimeError(f"{description} has an invalid PNG end chunk.")
                    return
                chunk_count += 1
    except OSError as error:
        raise RuntimeError(f"Could not validate {description}: {error}") from error


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(COPY_BUFFER_BYTES):
            digest.update(block)
    return digest.hexdigest()


def validate_staged_screenshots(stage: Path) -> dict[str, str]:
    staged_hashes: dict[str, str] = {}
    for filename in README_SCREENSHOTS:
        staged = stage / filename
        validate_png(staged, f"Staged README screenshot {filename}")
        staged_hashes[filename] = file_sha256(staged)
    return staged_hashes


def write_publication_journal(payload: dict[str, object]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".readme-screenshot-journal-",
        suffix=".tmp",
        dir=OUT,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as journal:
            json.dump(payload, journal, sort_keys=True)
            journal.write("\n")
            journal.flush()
            os.fsync(journal.fileno())
        os.replace(temporary, PUBLISH_JOURNAL)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_publication_journal() -> tuple[Path, dict[str, bool], dict[str, str]]:
    try:
        with PUBLISH_JOURNAL.open(encoding="utf-8") as journal:
            payload = json.load(journal)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Cannot read interrupted screenshot publication journal {PUBLISH_JOURNAL.relative_to(ROOT)}."
        ) from error

    if not isinstance(payload, dict):
        raise RuntimeError("Interrupted screenshot publication journal has an invalid format.")
    backup_name = payload.get("backup_dir")
    original_files = payload.get("original_files")
    staged_hashes = payload.get("staged_hashes")
    if (
        not isinstance(backup_name, str)
        or Path(backup_name).name != backup_name
        or not backup_name.startswith(PUBLISH_BACKUP_PREFIX)
        or not isinstance(original_files, dict)
        or not isinstance(staged_hashes, dict)
        or set(original_files) != set(README_SCREENSHOTS)
        or set(staged_hashes) != set(README_SCREENSHOTS)
        or any(type(existed) is not bool for existed in original_files.values())
        or any(
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            for digest in staged_hashes.values()
        )
    ):
        raise RuntimeError("Interrupted screenshot publication journal has invalid publication metadata.")
    return OUT / backup_name, original_files, staged_hashes


def replace_from_backup(source: Path, destination: Path) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.restore-",
        suffix=destination.suffix,
        dir=OUT,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def restore_previous_screenshots(backup: Path, original_files: dict[str, bool]) -> None:
    for filename in README_SCREENSHOTS:
        destination = OUT / filename
        if original_files[filename]:
            source = backup / filename
            if not source.is_file():
                raise RuntimeError(f"Screenshot backup is missing {filename}.")
            replace_from_backup(source, destination)
        else:
            try:
                destination.unlink()
            except FileNotFoundError:
                pass


def remove_publication_artifacts(backup: Path) -> None:
    PUBLISH_JOURNAL.unlink(missing_ok=True)
    if backup.exists():
        shutil.rmtree(backup)


def publication_matches_staged_screenshots(staged_hashes: dict[str, str]) -> bool:
    return all(
        (target := OUT / filename).is_file() and file_sha256(target) == digest
        for filename, digest in staged_hashes.items()
    )


def recover_incomplete_publication() -> None:
    if not PUBLISH_JOURNAL.exists():
        return

    backup, original_files, staged_hashes = read_publication_journal()
    if publication_matches_staged_screenshots(staged_hashes):
        remove_publication_artifacts(backup)
        print("completed screenshot publication cleanup")
        return

    try:
        restore_previous_screenshots(backup, original_files)
    except Exception as error:
        raise RuntimeError(
            "Screenshot publication is incomplete and could not be rolled back. "
            f"Keep {PUBLISH_JOURNAL.relative_to(ROOT)} and its backup directory for recovery."
        ) from error
    remove_publication_artifacts(backup)
    print("rolled back incomplete screenshot publication")


def stage_screenshot(page: Page, stage: Path, filename: str) -> None:
    target = stage / filename
    page.screenshot(path=str(target), full_page=False)
    validate_png(target, f"Captured README screenshot {filename}")


def publish_screenshots(stage: Path) -> None:
    staged_hashes = validate_staged_screenshots(stage)
    backup = Path(tempfile.mkdtemp(prefix=PUBLISH_BACKUP_PREFIX, dir=OUT))
    journal_created = False
    original_files: dict[str, bool] = {}
    try:
        for filename in README_SCREENSHOTS:
            destination = OUT / filename
            original_files[filename] = destination.exists()
            if not original_files[filename]:
                continue
            if not destination.is_file():
                raise RuntimeError(f"README screenshot destination is not a file: {filename}")
            shutil.copy2(destination, backup / filename)

        journal: dict[str, object] = {
            "backup_dir": backup.name,
            "in_progress": None,
            "original_files": original_files,
            "published": [],
            "staged_hashes": staged_hashes,
            "version": 1,
        }
        write_publication_journal(journal)
        journal_created = True

        for filename in README_SCREENSHOTS:
            journal["in_progress"] = filename
            write_publication_journal(journal)
            os.replace(stage / filename, OUT / filename)
            journal["published"] = [*journal["published"], filename]
            journal["in_progress"] = None
            write_publication_journal(journal)
            print(f"published {(OUT / filename).relative_to(ROOT)}")
    except Exception:
        if not journal_created:
            shutil.rmtree(backup)
            raise
        try:
            restore_previous_screenshots(backup, original_files)
        except Exception as rollback_error:
            raise RuntimeError(
                "Screenshot publication failed and rollback was incomplete. "
                f"Keep {PUBLISH_JOURNAL.relative_to(ROOT)} and its backup directory for recovery."
            ) from rollback_error
        remove_publication_artifacts(backup)
        raise
    else:
        remove_publication_artifacts(backup)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    recover_incomplete_publication()
    admin_username, admin_password = read_admin_credentials()
    try:
        with tempfile.TemporaryDirectory(prefix=".readme-capture-", dir=OUT) as stage_dir:
            stage = Path(stage_dir)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    context = browser.new_context(viewport=VIEWPORT, locale="ko-KR")
                    page = context.new_page()

                    login_response = context.request.post(
                        f"{API}/api/v1/auth/login",
                        data={"username": admin_username, "password": admin_password},
                    )
                    login_status = login_response.status
                    admin_username = ""
                    admin_password = ""
                    if login_status != 200:
                        raise RuntimeError(
                            f"Screenshot administrator login failed with HTTP {login_status}. "
                            "Check the environment-provided credentials."
                        )

                    open_route(page, "/admin", page.get_by_role("heading", name="관리자 콘솔"))
                    open_route(page, "/", page.get_by_role("heading", name="Dashboard"))
                    stage_screenshot(page, stage, "dashboard.png")

                    open_route(page, "/newsletters", page.get_by_test_id("newsletters-reading"))
                    assert_newsletter_ready(page)
                    stage_screenshot(page, stage, "newsletter.png")

                    set_newsletter_theme(page, "dark")
                    stage_screenshot(page, stage, "newsletter-dark.png")
                finally:
                    browser.close()

            publish_screenshots(stage)
    finally:
        admin_username = ""
        admin_password = ""


if __name__ == "__main__":
    main()
