from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from browser_automation_skills.browser_launcher import BrowserLauncher


@pytest.mark.parametrize(
    ("failure_stage", "expected_calls"),
    [
        ("playwright_start", (False, False, False)),
        ("browser_launch", (False, False, True)),
        ("context_create", (False, True, True)),
        ("context_setup", (True, True, True)),
    ],
)
async def test_launch_failure_cleans_up_created_resources_and_reraises(
    failure_stage, expected_calls
):
    startup_error = RuntimeError(f"{failure_stage} failed")
    playwright = MagicMock()
    browser = MagicMock()
    context = MagicMock()
    playwright_manager = MagicMock()
    playwright_manager.start = AsyncMock(return_value=playwright)
    playwright.stop = AsyncMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    browser.close = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    context.close = AsyncMock()

    if failure_stage == "playwright_start":
        playwright_manager.start.side_effect = startup_error
    elif failure_stage == "browser_launch":
        playwright.chromium.launch.side_effect = startup_error
    elif failure_stage == "context_create":
        browser.new_context.side_effect = startup_error
    else:
        context.set_default_timeout = MagicMock(side_effect=startup_error)

    launcher = BrowserLauncher(default_timeout=1000)
    with patch(
        "browser_automation_skills.browser_launcher.async_playwright",
        return_value=playwright_manager,
    ):
        with pytest.raises(RuntimeError) as exc_info:
            await launcher.launch()

    assert exc_info.value is startup_error
    context_closed, browser_closed, playwright_stopped = expected_calls
    assert context.close.await_count == int(context_closed)
    assert browser.close.await_count == int(browser_closed)
    assert playwright.stop.await_count == int(playwright_stopped)
    assert launcher.context is None
    assert launcher.browser is None


async def test_cleanup_errors_do_not_replace_startup_error():
    startup_error = RuntimeError("context creation failed")
    playwright = MagicMock()
    browser = MagicMock()
    playwright_manager = MagicMock()
    playwright_manager.start = AsyncMock(return_value=playwright)
    playwright.stop = AsyncMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    browser.close = AsyncMock(side_effect=RuntimeError("browser close failed"))
    browser.new_context = AsyncMock(side_effect=startup_error)

    launcher = BrowserLauncher()
    with patch(
        "browser_automation_skills.browser_launcher.async_playwright",
        return_value=playwright_manager,
    ):
        with pytest.raises(RuntimeError) as exc_info:
            await launcher.launch()

    assert exc_info.value is startup_error
    browser.close.assert_awaited_once()
    playwright.stop.assert_awaited_once()
    assert launcher.browser is None
