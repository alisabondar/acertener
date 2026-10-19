import { expect, test } from "@playwright/test";

import { identity, openApp, openChartByMrn, viewAs } from "./helpers.ts";

// A seeded patient on Dr. Chen's care team (the seed is deterministic).
const MRN = "MRN-100000";

test("starts as Dr. Chen, and switching persona changes what the app offers", async ({ page }) => {
  await openApp(page);
  await expect(identity(page)).toContainText("Viewing as Dr. Wei Chen (Provider, MD)");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link")).toHaveText(["My day", "Patients", "New patient"]);

  await viewAs(page, "Practice Admin");

  await expect(nav.getByRole("link")).toHaveText(["Patients", "Admin"]);
  await expect(page).toHaveURL(/\/admin\/audit$/);
});

test("My day lists today's schedule, and a visit card opens the chart", async ({ page }) => {
  await openApp(page);
  const schedule = page.getByRole("list", { name: "Today's schedule" });

  await schedule.getByRole("link").first().click();

  await expect(page).toHaveURL(/\/patients\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("region", { name: "Patient" })).toBeVisible();
});

test("patient search never puts what was typed in the URL", async ({ page }) => {
  await openApp(page, "/patients");
  await page.getByRole("radio", { name: "All patients" }).click();

  await page.getByRole("searchbox", { name: "Search patients" }).fill("garc");
  await expect(page.getByRole("row", { name: /Garcia/ }).first()).toBeVisible();
  await page.getByRole("button", { name: /^Inactive/ }).click();

  await expect(page).toHaveURL(/status=inactive/);
  expect(page.url().toLowerCase()).not.toContain("garc");
});

test("a provider finalizes a note, which locks it and refreshes the AI summary", async ({
  page,
}) => {
  // The summary waits out its 15 s debounce before regenerating.
  test.setTimeout(90_000);
  await openApp(page);
  await openChartByMrn(page, MRN);
  await page.getByRole("tab", { name: "Notes" }).click();
  const text = `E2E check ${Date.now()}: BP recheck in 4 weeks.`;

  await page.getByRole("button", { name: "New note" }).click();
  await page.getByRole("textbox", { name: "Note" }).fill(text);
  await page.getByRole("button", { name: "Finalize" }).click();

  const note = page
    .getByRole("list", { name: "Notes" })
    .getByRole("listitem")
    .filter({ hasText: text });
  await expect(note).toBeVisible();
  await expect(note).not.toContainText("Draft");
  await expect(note.getByRole("button", { name: "Delete draft" })).toHaveCount(0);
  await expect(note.getByRole("button", { name: "Continue editing" })).toHaveCount(0);

  // The finalized note makes the summary stale; it regenerates on its own after the debounce.
  await page.getByRole("tab", { name: "Overview" }).click();
  const summary = page.getByRole("region", { name: "AI summary" });
  await expect(summary).toContainText(/New changes, refreshing in|Updating…|Generating…/);
  await expect(summary).toContainText(/Updated (just now|\d+ (second|min))/, { timeout: 60_000 });
});

test("a nurse records vitals and a note, and a provider adds the diagnosis she can't", async ({
  page,
}) => {
  test.setTimeout(60_000);
  await openApp(page);
  await viewAs(page, "Sam Okafor");
  await openChartByMrn(page, MRN);

  await page.getByRole("tab", { name: "Vitals" }).click();
  await page.getByRole("button", { name: "Record vitals" }).click();
  await page.getByLabel("Systolic").fill("1200");
  await page.getByRole("button", { name: "Save vitals" }).click();
  await expect(page.getByLabel("Systolic")).toHaveAttribute("aria-invalid", "true");
  await page.getByLabel("Systolic").fill("124");
  await page.getByRole("button", { name: "Save vitals" }).click();
  await expect(page.getByText("Vitals recorded")).toBeVisible();

  await page.getByRole("tab", { name: "Notes" }).click();
  const text = `Nurse intake ${Date.now()}: patient reports mild cough.`;
  await page.getByRole("button", { name: "New note" }).click();
  await page.getByRole("textbox", { name: "Note" }).fill(text);
  await page.getByRole("button", { name: "Finalize" }).click();
  await expect(page.getByRole("list", { name: "Notes" })).toContainText(text);

  await page.getByRole("tab", { name: "Allergies & conditions" }).click();
  await expect(page.getByRole("button", { name: "Edit allergies" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit conditions" })).toHaveCount(0);
  await expect(page.getByLabel("Requires a provider role")).toBeVisible();

  await viewAs(page, "Dr. Wei Chen");
  await openChartByMrn(page, MRN);
  await page.getByRole("tab", { name: "Allergies & conditions" }).click();
  await page.getByRole("button", { name: "Edit conditions" }).click();
  const diagnosis = `Acute cough ${Date.now()}`;
  const form = page.getByRole("form", { name: "Add condition" });
  await form.getByLabel("ICD-10 code").fill("R05.1");
  await form.getByLabel("Condition").fill(diagnosis);
  await form.getByRole("button", { name: "Add condition" }).click();
  await expect(page.getByText("Condition added")).toBeVisible();
  await expect(page.getByText(diagnosis)).toBeVisible();
});

test("front desk sees contact details only, and no audit log", async ({ page }) => {
  await openApp(page);
  await viewAs(page, "Taylor Brooks");
  await openChartByMrn(page, MRN);

  await expect(page.getByRole("tab")).toHaveText(["Contact"]);
  await expect(page.getByRole("alert", { name: "Severe allergies" })).toHaveCount(0);

  // Navigate inside the app (a reload would reset the demo persona to Dr. Chen).
  await page.evaluate(() => {
    window.history.pushState({}, "", "/admin/audit");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await expect(
    page.getByRole("heading", { name: "You don't have access to this page" }),
  ).toBeVisible();
  await expect(identity(page)).toContainText("Taylor Brooks");
});

test("access history records each persona, marked as demo access", async ({ page }) => {
  await openApp(page);
  await viewAs(page, "Sam Okafor");
  await openChartByMrn(page, MRN);
  await viewAs(page, "Dr. Wei Chen");

  await page.getByRole("tab", { name: "Access history" }).click();

  const history = page.getByRole("table", { name: "Access history" });
  await expect(history).toContainText("Sam Okafor");
  await expect(history).toContainText("(demo)");
});

test("the chart opens on an AI summary labelled for verification", async ({ page }) => {
  await openApp(page);
  await openChartByMrn(page, MRN);

  const summary = page.getByRole("region", { name: "AI summary" });
  await expect(summary).toContainText("AI-generated: verify before clinical use");
});
