import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import fs from "node:fs";

async function register(page: Page) {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page
    .getByLabel("Username", { exact: true })
    .fill(`test_${Date.now()}_${Math.floor(Math.random() * 10000)}`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("test-password-for-browser-verified");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Your brain, in perspective." }),
  ).toBeVisible();
}

test("disconnected overview remains honest and recording unavailable", async ({
  page,
}) => {
  await register(page);
  await expect(
    page.getByText("Waiting for your signal", { exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: "/tmp/cortia-overview.png", fullPage: true });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Live EEG", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Start recording", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText("No hardware data", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Quality assessment pending")).toBeVisible();
});

test("all analytic pages show real empty states and methods", async ({
  page,
}) => {
  await register(page);
  for (const [name, text] of [
    ["Brainwaves", "No brainwave analysis available"],
    ["Baselines", "A baseline needs your recordings"],
    ["History & reports", "No recordings yet"],
    ["AI Insights", "Measurements come first"],
  ]) {
    await page
      .getByRole("navigation")
      .getByRole("button", { name, exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: text, exact: true }),
    ).toBeVisible();
  }
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Methods", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Metric reference" }),
  ).toBeVisible();
});

test("invalid MRI never produces prediction", async ({ page }) => {
  await register(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "MRI Analysis", exact: true })
    .click();
  await expect(page.getByText("Model ready", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await page.getByLabel("MRI image", { exact: true }).setInputFiles({
    name: "broken.png",
    mimeType: "image/png",
    buffer: Buffer.from("invalid image data"),
  });
  await page
    .getByRole("button", { name: "Run model analysis", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Invalid or oversized image",
  );
  await expect(
    page.getByRole("heading", { name: "No MRI predictions yet" }),
  ).toBeVisible();
});

test("actual MRI model upload persists real classification", async ({
  page,
}) => {
  const source = "/home/vinay/brain_health_monitor/dataset/no/N1.JPG";
  test.skip(
    !fs.existsSync(source),
    "Original repository real MRI fixture absent",
  );
  await register(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "MRI Analysis", exact: true })
    .click();
  await expect(page.getByText("Model ready", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await page.getByLabel("MRI image", { exact: true }).setInputFiles(source);
  await page
    .getByRole("button", { name: "Run model analysis", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Classification result" }),
  ).toBeVisible({ timeout: 45000 });
  await expect(
    page.getByText("Model prediction · not diagnosis", { exact: true }),
  ).toBeVisible();
  if (process.env.CORTIA_EXPECT_GRADCAM === "1") {
    await expect(
      page.getByRole("img", { name: "Actual classifier Grad-CAM saliency overlay" }),
    ).toBeVisible();
  }
  await page.reload();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "MRI Analysis", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Classification result" }),
  ).toBeVisible();
  if (process.env.CORTIA_EXPECT_GRADCAM === "1") {
    await expect(
      page.getByRole("img", { name: "Actual classifier Grad-CAM saliency overlay" }),
    ).toBeVisible();
  }
});

test("mobile navigation and logout preserve account boundary", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await register(page);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Baselines", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "A baseline needs your recordings" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome to CORTIA." }),
  ).toBeVisible();
  const response = await page.request.get("/api/sessions");
  expect(response.status()).toBe(401);
});

test("interactive API docs load entirely from local assets", async ({
  page,
}) => {
  const remote: string[] = [];
  page.on("request", (request) => {
    if (
      !request.url().startsWith("http://127.0.0.1:8011/") &&
      !request.url().startsWith("data:")
    )
      remote.push(request.url());
  });
  await page.goto("/docs");
  await expect(page.getByRole("heading", { name: /CORTIA API/ })).toBeVisible();
  await expect(
    page.getByText("/api/auth/register", { exact: true }),
  ).toBeVisible();
  expect(remote).toEqual([]);
});
