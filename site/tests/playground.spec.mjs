// The playground in real browsers: asking, waiting, Stop, files, problems and the web.
import { expect, test } from "@playwright/test";

async function ready(page) {
  await page.goto("/");
  await expect(page.locator("#run")).toBeEnabled({ timeout: 45_000 });
}

async function runCode(page, code) {
  await page.locator("#code").fill(code);
  await page.locator("#run").click();
}

test("the page is cross-origin isolated", async ({ page }) => {
  const response = await page.goto("/");
  expect(response.headers()["cross-origin-opener-policy"]).toBe("same-origin");
  expect(response.headers()["cross-origin-embedder-policy"]).toBe("require-corp");
  expect(await page.evaluate(() => self.crossOriginIsolated)).toBe(true);
});

test("ask waits for an answer typed in place", async ({ page }) => {
  await ready(page);
  await runCode(page, 'ask "Your name?" and call it name\nshow "Hello, {name}!"');
  const box = page.locator("#output input.answer-box");
  await box.fill("Ann");
  await box.press("Enter");
  await expect(page.locator("#output")).toContainText("Hello, Ann!");
});

test("wait pauses without freezing the page", async ({ page }) => {
  await ready(page);
  await runCode(page, 'show "a"\nwait 1 second\nshow "b"');
  await expect(page.locator("#output")).toContainText("b", { timeout: 5_000 });
});

test("Stop ends a program that is asking", async ({ page }) => {
  await ready(page);
  await runCode(page, 'ask "Guess?" and call it guess');
  await expect(page.locator("#output input.answer-box")).toBeVisible();
  await page.locator("#stop").click();
  await expect(page.locator("#output")).toContainText("Stopped.");
  await expect(page.locator("#run")).toBeEnabled();
});

test("Stop ends repeat forever, and the page keeps only the last lines", async ({ page }) => {
  await ready(page);
  await runCode(page, "set n to 0\nrepeat forever\n    add 1 to n\n    show n");
  await page.waitForTimeout(1500);
  await page.locator("#stop").click();
  await expect(page.locator("#output")).toContainText("Stopped.");
  const lines = (await page.locator("#output").innerText()).trim().split("\n");
  expect(lines.length).toBeLessThanOrEqual(2002);
});

test("a problem offers a fix you can use", async ({ page }) => {
  await ready(page);
  await runCode(page, "show Hello there");
  await expect(page.locator("#output .problem")).toContainText("Put the text in double quotes.");
  await page.locator("#output .idea").first().click();
  await expect(page.locator("#code")).toHaveValue('show "Hello there"');
});

test("files a program saves show up in the Files tab", async ({ page }) => {
  await ready(page);
  await runCode(page, 'save a list of "a" and "b" to "letters.txt"\nread the lines of "letters.txt" and call it letters\nshow letters');
  await expect(page.locator("#output")).toContainText("a and b");
  await page.locator("#tab-files").click();
  await expect(page.locator("#file-list")).toContainText("letters.txt");
});

test("a website that blocks browser pages gets an honest message", async ({ page }) => {
  await ready(page);
  await runCode(page, 'read "https://example.com" and call it page');
  await expect(page.locator("#output .problem")).toContainText("Check your internet connection");
});

test.describe("local time", () => {
  test.use({ timezoneId: "America/New_York" });
  test("the time now uses your own clock", async ({ page }) => {
    await ready(page);
    await runCode(page, "show the time now");
    const expected = await page.evaluate(() => {
      const d = new Date();
      return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
    });
    await expect(page.locator("#output")).toContainText(expected.slice(0, 3));
  });
});
