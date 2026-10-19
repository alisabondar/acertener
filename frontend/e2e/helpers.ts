import { expect, type Page } from "@playwright/test";

/** Opens the app as the default persona (Dr. Chen) and waits for the shell. */
export async function openApp(page: Page, path = "/") {
  await page.goto(path);
  await expect(identity(page)).toBeVisible();
}

export function identity(page: Page) {
  return page.getByRole("button", { name: /^(Viewing as|Switching to)/ });
}

/** Switches persona through the "View as" menu, the way a reviewer would. */
export async function viewAs(page: Page, name: string) {
  await identity(page).click();
  await page.getByRole("menuitemradio", { name: new RegExp(name) }).click();
  await expect(identity(page)).toContainText(`Viewing as ${name}`);
}

/** Opens a seeded patient's chart by MRN through the patient search. */
export async function openChartByMrn(page: Page, mrn: string) {
  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Patients" })
    .click();
  const search = page.getByRole("searchbox", { name: "Search patients" });
  await expect(search).toBeVisible();
  // Only roles with a care team get the My patients / All patients toggle.
  const allPatients = page.getByRole("radio", { name: "All patients" });
  if (await allPatients.isVisible()) await allPatients.click();
  await search.fill(mrn);
  await page.getByRole("row", { name: new RegExp(mrn) }).click();
  await expect(page.getByRole("region", { name: "Patient" })).toContainText(mrn);
}
