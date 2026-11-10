import base64
from playwright.async_api import Page

SOM_INJECT_JS = """
() => {
    const existing = document.getElementById('ai-som-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'ai-som-overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:2147483647;';
    document.body.appendChild(overlay);

    const selectors = 'a, button, input, textarea, select, [role="button"], [onclick]';
    const elements = Array.from(document.querySelectorAll(selectors));
    const items = [];
    let idCounter = 1;

    elements.forEach((el) => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (
            rect.width > 8 && rect.height > 8 &&
            rect.top >= 0 && rect.left >= 0 &&
            rect.bottom <= window.innerHeight && rect.right <= window.innerWidth &&
            style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0'
        ) {
            const somId = idCounter++;
            const box = document.createElement('div');
            box.style.cssText = `
                position: fixed; left: ${rect.left}px; top: ${rect.top}px;
                width: ${rect.width}px; height: ${rect.height}px;
                border: 2px solid #f43f5e; background-color: rgba(244, 63, 94, 0.08);
                box-sizing: border-box; border-radius: 3px;
            `;
            const badge = document.createElement('span');
            badge.textContent = somId;
            badge.style.cssText = `
                position: absolute; top: -18px; left: -2px;
                background-color: #e11d48; color: #ffffff;
                font-size: 11px; font-weight: bold; font-family: monospace;
                padding: 1px 5px; border-radius: 3px;
            `;
            box.appendChild(badge);
            overlay.appendChild(box);

            const labelText = (el.innerText || el.value || el.placeholder || '').trim().slice(0, 40);
            items.push({
                id: somId, tag: el.tagName.toLowerCase(), text: labelText,
                x: Math.round(rect.left + rect.width / 2),
                y: Math.round(rect.top + rect.height / 2)
            });
        }
    });
    return items;
}
"""

async def capture_som_screenshot(page: Page) -> tuple[str, list[dict]]:
    elements_meta = await page.evaluate(SOM_INJECT_JS)
    screenshot_bytes = await page.screenshot(type="jpeg", quality=75)
    b64_encoded = base64.b64encode(screenshot_bytes).decode("utf-8")
    await page.evaluate("() => { const el = document.getElementById('ai-som-overlay'); if (el) el.remove(); }")
    return f"data:image/jpeg;base64,{b64_encoded}", elements_meta
