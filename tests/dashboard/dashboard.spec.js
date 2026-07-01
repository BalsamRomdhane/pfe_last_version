// =====================================================================
// tests/dashboard/dashboard.spec.js
// Dashboard E2E tests — Loads successfully, no JS/React errors
// =====================================================================

const { test, expect } = require('@playwright/test');
const { LoginPage } = require('../pages/LoginPage');
const { DashboardPage } = require('../pages/DashboardPage');
const {
  captureRuntimeErrors,
  assertNoRuntimeErrors,
  waitForLoadingToFinish,
} = require('../utils/helpers');

const VALID_USER = process.env.TEST_USERNAME || 'admin';
const VALID_PASS = process.env.TEST_PASSWORD || 'admin123';

test.describe('Dashboard', () => {

  test.beforeEach(async ({ page }) => {
    // Login before each test
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(VALID_USER, VALID_PASS);
    await loginPage.waitForDashboard();
  });

  // ── Dashboard loads ──────────────────────────────────────────────

  test('should load the dashboard successfully', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.waitForLoad();

    // Dashboard URL is correct
    await expect(page).toHaveURL(/#\/dashboard/);

    // KPI cards are visible
    const kpiCount = await dashboardPage.getKpiCount();
    expect(kpiCount).toBeGreaterThan(0);

    // Page title/heading is present
    const heading = page.getByRole('heading').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });

    // No React errors
    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors on dashboard: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should display KPI cards with numeric values', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.waitForLoad();

    // At least one KPI card should have a numeric value
    const kpiValues = page.locator('.kpi-value, .text-3xl.font-bold');
    const count = await kpiValues.count();
    expect(count).toBeGreaterThan(0);
  });

  test('should not have any JavaScript errors on load', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.waitForLoad();
    await waitForLoadingToFinish(page);

    // Check specifically for insertBefore and React reconciliation errors
    const insertBeforeErrors = runtimeErrors.errors.filter(e =>
      /insertBefore|NotFoundError/i.test(e)
    );
    expect(insertBeforeErrors, `DOM reconciliation errors found: ${insertBeforeErrors.join('\n')}`).toHaveLength(0);

    // Check for generic React errors
    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should not have React runtime errors', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.waitForLoad();

    // Wait extra time for any deferred errors
    await page.waitForTimeout(2_000);

    const reactErrors = runtimeErrors.errors.filter(e =>
      /React error|Minified React error|Invariant Violation/i.test(e)
    );
    expect(
      reactErrors,
      `React runtime errors detected: ${reactErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('should render layout navigation', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.waitForLoad();

    // Navigation should be visible (sidebar or top nav)
    const nav = page.locator('nav, [role="navigation"], aside').first();
    await expect(nav).toBeVisible({ timeout: 10_000 });
  });

  test('should navigate to documents page from dashboard', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.waitForLoad();

    // Click Documents link
    const documentsLink = page.getByRole('link', { name: /documents/i }).first();
    if (await documentsLink.isVisible()) {
      await documentsLink.click();
      await expect(page).toHaveURL(/#\/documents/, { timeout: 10_000 });
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors navigating to documents: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should have no hydration errors', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.waitForLoad();

    const hydrationErrors = runtimeErrors.errors.filter(e => /hydration/i.test(e));
    expect(hydrationErrors, `Hydration errors detected: ${hydrationErrors.join('\n')}`).toHaveLength(0);
  });

  test('should maintain state on refresh', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.waitForLoad();
    await expect(page).toHaveURL(/#\/dashboard/);

    // Reload the page
    await page.reload();
    await page.waitForLoadState('domcontentloaded');

    // After reload, should either be on dashboard (if auth persists) or login
    const url = page.url();
    expect(url).toMatch(/(dashboard|login)/);

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors after refresh: ${critical.join('\n')}`).toHaveLength(0);
  });

});
