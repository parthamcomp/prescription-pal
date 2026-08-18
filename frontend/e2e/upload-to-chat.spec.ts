import { expect, test } from "@playwright/test";

/**
 * TIER 3 (E2E) REFERENCE IMPLEMENTATION.
 *
 * One test, one critical path, driven through the real stack end to end:
 * register -> add a record -> ask a question -> get an answer. Permutations
 * of that path (multi-page upload, OCR accuracy, every prompt-classification
 * branch) belong in Tier 1/2 - this test exists to prove the seams between
 * frontend, API, and DB actually connect, not to re-verify branch logic
 * already covered elsewhere.
 *
 * Deliberately run with OPENAI_API_KEY unset/invalid in the E2E environment
 * (see backend/tests/README or the E2E CI job env) so this test exercises
 * the app's own documented graceful-degradation path (rag.py's "LLM
 * unavailable" branch) instead of depending on a real, non-deterministic,
 * costly third-party call. That degradation path is itself a critical
 * behavior worth covering at this level - a real user is what happens if
 * OpenAI has a bad day.
 */
test("a new user can register, save a record, and get a chat answer", async ({
  page,
}) => {
  const email = `e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByPlaceholder("Optional").fill("E2E Test");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill("Str0ng!Passw0rd");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page).toHaveURL(/\/ask$/);

  await page.getByRole("button", { name: "Upload a prescription" }).click();
  await page.getByRole("button", { name: "Enter manually" }).click();

  await page.getByPlaceholder("e.g. Amoxicillin").fill("E2E Test Medicine");
  await page.getByPlaceholder("e.g. 250mg").fill("100mg");
  await page.getByPlaceholder("e.g. 3 times a day").fill("once daily");
  await page.getByPlaceholder("e.g. 7 days").fill("5 days");

  await page.getByRole("button", { name: "Save record" }).click();

  await expect(page).toHaveURL(/\/ask$/);

  await page
    .getByPlaceholder(/Ask about a dose/)
    .fill("What was E2E Test Medicine prescribed for?");
  await page.getByRole("button", { name: "Ask" }).click();

  // The record-grounded half of the answer must appear regardless of
  // whether the general-knowledge half came from a real model or the
  // degraded fallback - that's the one thing this journey actually
  // promises the user.
  await expect(page.getByText(/E2E Test Medicine/)).toBeVisible({
    timeout: 15_000,
  });
});
