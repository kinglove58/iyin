import { expect, test } from "@playwright/test";

test("public research journeys are navigable", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /evidence stays visible/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /lessons for people building the next africa/i })).toBeVisible();
  await page.getByRole("link", { name: /Ask Iyin's public ideas/i }).first().click();
  await expect(page.getByRole("heading", { name: /What would you like to understand/i })).toBeVisible();
  await expect(page.getByLabel(/Ask a research question/i)).toBeVisible();
  await expect(page.getByText(/links to the original moment/i)).toBeVisible();
});

test("correction form exposes accountability categories", async ({ page }) => {
  await page.goto("/corrections");
  await expect(page.getByRole("option", { name: "Wrong attribution" })).toBeAttached();
  await expect(page.getByRole("option", { name: "Removal request" })).toBeAttached();
});

test("administrator can authenticate and approve a fictional fixture candidate", async ({ page }) => {
  await page.goto("/admin/login");
  await page.getByLabel("Email").fill(process.env.E2E_ADMIN_EMAIL ?? "admin@example.com");
  await page
    .locator('input[name="password"]')
    .fill(process.env.E2E_ADMIN_PASSWORD ?? "change-this-development-password");
  await page.getByRole("button", { name: /sign in securely/i }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await page.goto("/admin/chunks");
  await expect(page.getByRole("heading", { name: /Reconstruct questions and answers/i })).toBeVisible();
  await page.goto("/admin/candidates");

  const candidate = page.getByRole("heading", {
    name: /fictional archivist follow-up/i,
  });
  const emptyQueue = page.getByText("No pending candidates.");
  await expect(candidate.or(emptyQueue)).toBeVisible();
  if (await candidate.isVisible()) {
    page.once("dialog", (dialog) => dialog.accept("Approved by deterministic browser test."));
    await candidate.locator("xpath=ancestor::article").getByRole("button", { name: "Approve" }).click();
    await expect(candidate).not.toBeVisible();
  } else {
    await expect(emptyQueue).toBeVisible();
  }
});
