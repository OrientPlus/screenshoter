from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    BrowserType,
    ElementHandle,
    Page,
    Playwright,
    async_playwright,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
)

_BROWSER_LAUNCH_ARGS = [
    "--no-sandbox",                 # обязательно в Docker (нет привилегированного режима)
    "--disable-dev-shm-usage",      # /dev/shm в Docker часто мал → использовать /tmp
    "--disable-gpu",                # GPU недоступен в headless-контейнере
    "--disable-setuid-sandbox",
    "--disable-extensions",
    "--mute-audio",
]

# Параметры отображения страницы
_VIEWPORT = {"width": 1920, "height": 1080}

# Таймауты (мс)
_PAGE_LOAD_TIMEOUT_MS    = 30_000   # максимум на goto() + networkidle
_SELECTOR_WAIT_TIMEOUT_MS = 10_000  # максимум на появление элемента
_SCREENSHOT_TIMEOUT_MS   = 20_000   # максимум на сам захват изображения


class ScreenshotCapture:
    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser:    Optional[Browser]    = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=_BROWSER_LAUNCH_ARGS,
        )

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def _ensure_started(self) -> None:
        if self._browser is None:
            raise RuntimeError(
                "ScreenshotCapture is not running."
            )

    async def take(
        self,
        url: str,
        selector: Optional[str] = None,
    ) -> bytes:
        self._ensure_started()

        context = await self._new_context()
        try:
            page = await context.new_page()
            await self._navigate(page, url)

            if selector:
                return await self._screenshot_element(page, selector)
            else:
                return await self._screenshot_full_page(page)

        finally:
            await context.close()

    async def _new_context(self) -> BrowserContext:
        return await self._browser.new_context(
            viewport=_VIEWPORT,
            java_script_enabled=True,
            ignore_https_errors=True,
            accept_downloads=False,
        )

    @staticmethod
    async def _navigate(page: Page, url: str) -> None:
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT_MS)
        try:
            await page.goto(url, wait_until="networkidle")
        except PlaywrightTimeoutError:
            # networkidle не наступил — страница всё равно может быть видна.
            # Делаем второй шанс с более мягким критерием.
            await page.goto(url, wait_until="domcontentloaded")

    @staticmethod
    async def _screenshot_full_page(page: Page) -> bytes:
        return await page.screenshot(
            full_page=True,
            type="png",
            timeout=_SCREENSHOT_TIMEOUT_MS,
        )

    @staticmethod
    async def _screenshot_element(page: Page, selector: str) -> bytes:
        element: Optional[ElementHandle] = await page.wait_for_selector(
            selector,
            state="visible",
            timeout=_SELECTOR_WAIT_TIMEOUT_MS,
        )

        if element is None:
            raise PlaywrightError(f"Элемент не найден: '{selector}'")

        await element.scroll_into_view_if_needed()

        return await element.screenshot(
            type="png",
            timeout=_SCREENSHOT_TIMEOUT_MS,
        )

    async def __aenter__(self) -> "ScreenshotCapture":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()
