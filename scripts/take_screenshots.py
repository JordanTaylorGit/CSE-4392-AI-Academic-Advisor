"""Capture one screenshot per demo step from the running app (Person E, deliverable).

    uv run streamlit run app.py                                     # in one terminal
    uv run --with playwright python scripts/take_screenshots.py     # in another

Drives the app in headless Google Chrome (your installed Chrome, no browser
download) through the DEMO_GUIDE.md walk-through for Sam Martinez and saves PNGs
to deliverables/screenshots/. Playwright is not a project dependency; `--with`
pulls it in for this one run. Needs Ollama for the chat steps (see the guide).
"""

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAT_TIMEOUT_MS = 240_000  # first local-LLM answer can take a minute or more


def settle(page: Page, extra: float = 0.8) -> None:
    """Wait for Streamlit to finish its rerun, then for animations to end."""
    page.wait_for_timeout(300)
    page.wait_for_function(
        "() => !document.querySelector('[data-testid=\"stStatusWidget\"] [data-testid=\"stStatusWidgetRunningIcon\"]')"
        " && !document.querySelector('[data-testid=\"stSpinner\"]')",
        timeout=CHAT_TIMEOUT_MS)
    time.sleep(extra)


def section(page: Page, name: str) -> None:
    page.locator(".st-key-section button", has_text=name).first.click()
    settle(page)


def choose(page: Page, key: str, option: str) -> None:
    """Pick an option in the st.selectbox with this key."""
    box = page.locator(f".st-key-{key} [role='combobox']")
    box.click()
    box.fill(option)  # long lists render lazily; typing filters to the option
    page.get_by_role("option", name=option, exact=False).first.click()
    settle(page)


def ask(page: Page, text: str) -> None:
    before = page.locator("[data-testid='stChatMessage']").count()
    box = page.locator("[data-testid='stChatInputTextArea']")
    box.fill(text)
    box.press("Enter")
    # Done = the reply bubble exists, has text, and no spinner is left. The bubble
    # appears a beat before its spinner, so require the state to hold for a moment.
    answered = ("(n) => { const ms = document.querySelectorAll('[data-testid=\"stChatMessage\"]');"
                " return ms.length >= n && !document.querySelector('[data-testid=\"stSpinner\"]')"
                " && ms[ms.length - 1].innerText.trim().length > 0; }")
    for _ in range(3):
        page.wait_for_function(answered, arg=before + 2, timeout=CHAT_TIMEOUT_MS)
        time.sleep(1.5)
        if page.evaluate(answered, before + 2):
            break
    settle(page, 1.5)
    # Show the question and the start of its answer, not the tail of a long reply.
    page.evaluate("(i) => document.querySelectorAll('[data-testid=\"stChatMessage\"]')[i]"
                  ".scrollIntoView({block: 'start'})", before)
    time.sleep(0.6)


def shot(page: Page, out: Path, name: str, full: bool = False) -> None:
    """Save a PNG. full=True grows the window to the content first: Streamlit scrolls
    inside its own container, so Playwright's full_page alone only sees one screen."""
    path = out / f"{name}.png"
    if full:
        height = page.evaluate(
            "() => Math.max(document.body.scrollHeight, ...[...document.querySelectorAll("
            "'[data-testid=\"stMain\"], [data-testid=\"stAppViewContainer\"]')].map(e => e.scrollHeight))")
        page.set_viewport_size({"width": 1440, "height": min(int(height) + 40, 4200)})
        time.sleep(0.8)
    page.screenshot(path=str(path))
    if full:
        page.set_viewport_size({"width": 1440, "height": 900})
        time.sleep(0.3)
    print("saved", path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path)


def run(url: str, out: Path, scheme: str, student: str, skip_chat: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900},
                                device_scale_factor=2, color_scheme=scheme)
        page.goto(url)
        page.wait_for_selector(".st-key-section", timeout=60_000)
        settle(page, 1.5)

        # Team switches: preview off, traces on.
        page.get_by_role("button", name="More").click()
        page.wait_for_timeout(400)
        traces = page.get_by_role("switch", name="Show execution traces")
        if not traces.is_checked():
            traces.locator("xpath=ancestor::label").click()
            settle(page)
        page.keyboard.press("Escape")
        settle(page)

        choose(page, "student", student)
        section(page, "Plan")
        shot(page, out, "01_overview_rings")

        page.get_by_role("button", name="Build plan").click()
        settle(page, 2.5)
        shot(page, out, "02_plan_timeline", full=True)

        years = page.locator(".st-key-plan_view button", has_text="Years")
        if years.count():
            years.first.click()
            settle(page, 2)
            shot(page, out, "03_plan_years", full=True)
            page.locator(".st-key-plan_view button", has_text="Timeline").first.click()
            settle(page)

        add = page.get_by_role("button", name="Add a course")
        if add.count():
            add.first.click()
            page.wait_for_selector("[role='dialog']", timeout=30_000)
            settle(page, 1.5)
            shot(page, out, "04_add_dialog_checks")
            page.keyboard.press("Escape")
            settle(page)

        section(page, "Check a course")
        choose(page, "check_course", "CSE 4344")
        choose(page, "check_term", "Spring 2027")
        page.get_by_role("button", name="Run checks").click()
        settle(page, 2)
        shot(page, out, "05_six_checks", full=True)

        if not skip_chat:
            section(page, "Ask")
            ask(page, "What are the prerequisites for CSE 3310?")
            shot(page, out, "06_ask_exact_sql")
            ask(page, "Which courses cover machine learning or AI topics?")
            shot(page, out, "07_ask_semantic_rag")
            ask(page, "Generate my degree plan.")
            ask(page, "What about taking only 3 classes next semester instead?")
            shot(page, out, "08_ask_followup_memory")

        section(page, "Switch major")
        page.wait_for_timeout(500)
        compare = page.get_by_role("button", name="Compare plans")
        if compare.count():
            compare.first.click()
        settle(page, 2.5)
        shot(page, out, "09_switch_major_compare", full=True)

        section(page, "Traces")
        settle(page, 1.5)
        shot(page, out, "10_execution_traces", full=True)

        page.get_by_role("button", name="More").click()
        page.wait_for_timeout(800)
        shot(page, out, "11_transcript_download")
        browser.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "deliverables" / "screenshots")
    ap.add_argument("--scheme", choices=["light", "dark"], default="light",
                    help="light reads best on a projector")
    ap.add_argument("--student", default="Sam Martinez")
    ap.add_argument("--skip-chat", action="store_true", help="no LLM steps (fast layout check)")
    args = ap.parse_args(argv)
    run(args.url, args.out, args.scheme, args.student, args.skip_chat)
    return 0


if __name__ == "__main__":
    sys.exit(main())
