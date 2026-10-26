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
  await expect(page.locator("#output .problem")).toContainText("doesn't let pages in a browser read it");
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

test("Enter moves the steps under a line like if in, and Backspace moves them back out", async ({ page }) => {
  await page.goto("/");
  const code = page.locator("#code");
  await code.fill("");
  await code.pressSequentially("if 1 is 1");
  await code.press("Enter");
  await code.pressSequentially('show "yes"');
  await code.press("Enter");
  await code.press("Backspace");
  await code.pressSequentially("otherwise");
  await code.press("Enter");
  await code.pressSequentially('show "no"');
  await expect(code).toHaveValue('if 1 is 1\n    show "yes"\notherwise\n    show "no"');
});

// Phones, tablets and computers -----------------------------------------------------------

const LONG = "a long line, much wider than a phone screen and even wider than the editor on a big computer screen, so that it has to wrap onto the next rows";
const PROGRAM = [`set note to "${LONG}"`, "if note is not empty", `    show "${LONG}"`,
  ...Array.from({ length: 12 }, (_, i) => `show ${i + 1}`)].join("\n");

for (const width of [280, 375, 768, 1280]) {
  test.describe(`a screen ${width} pixels wide`, () => {
    test.use({ viewport: { width, height: 700 } });

    test("nothing sticks out sideways, and long lines wrap beside their line numbers", async ({ page }) => {
      await page.goto("/");
      await page.locator("#code").fill(PROGRAM);
      const layout = await page.evaluate(() => {
        const code = document.getElementById("code");
        const lines = [...document.getElementById("lines").children];
        const top = parseFloat(getComputedStyle(code).paddingTop);
        const bottom = parseFloat(getComputedStyle(code).paddingBottom);
        const last = lines[lines.length - 1];
        return {
          pageWidth: document.documentElement.scrollWidth,
          // The playground clips what sticks out, so check its buttons and boxes one by one.
          controlsFit: [...document.querySelectorAll(".playground button, .playground select, .tabs")]
            .every((e) => e.getBoundingClientRect().right <= innerWidth + 0.5),
          cutOff: code.scrollWidth - code.clientWidth,
          numbers: lines.length,
          wrapped: lines[0].offsetHeight > lines[1].offsetHeight,
          editorText: code.scrollHeight - top - bottom,
          besideNumbers: last.offsetTop + last.offsetHeight - top,
        };
      });
      expect(layout.pageWidth).toBeLessThanOrEqual(width);
      expect(layout.controlsFit).toBe(true);
      expect(layout.cutOff).toBeLessThanOrEqual(0);
      expect(layout.numbers).toBe(15);
      expect(layout.wrapped).toBe(true);
      // The copy that holds the numbers wraps each line the same way as the editor.
      expect(Math.abs(layout.editorText - layout.besideNumbers)).toBeLessThanOrEqual(1);
    });

    test("Run brings the output into view, Run and Stop stay in view, and messages keep their shape", async ({ page }) => {
      await ready(page);
      await runCode(page, PROGRAM.replace("show 1\n", "show a random number from 1 to 6 plus 1\n"));
      const marks = page.locator("#output .problem pre").first();
      await expect(marks).toContainText("^^^^");
      // The line and the ^ marks under it are 2 rows: they scroll sideways rather than wrap.
      const rows = await marks.evaluate((e) => Math.round(e.clientHeight / parseFloat(getComputedStyle(e).lineHeight)));
      expect(rows).toBe(2);
      const run = await page.locator("#run").boundingBox();
      expect(run.y).toBeGreaterThanOrEqual(0);
      expect(run.y + run.height).toBeLessThanOrEqual(700);
      const output = await page.locator("#output").boundingBox();
      expect(output.y).toBeGreaterThan(run.y + run.height);
      expect(output.y).toBeLessThan(700);
      if (width < 640) {
        // On a phone the output has a fixed height, so all of it fits on the screen.
        const status = await page.locator("#status").boundingBox();
        expect(status.y + status.height).toBeLessThanOrEqual(701);
      }
    });
  });
}
