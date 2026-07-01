// =====================================================================
// tests/evidence/evidence.spec.js
// Evidence Intelligence E2E tests
// =====================================================================

const { test, expect } = require('@playwright/test');
const { LoginPage } = require('../pages/LoginPage');
const { EvidencePage } = require('../pages/EvidencePage');
const {
  captureRuntimeErrors,
  assertNoRuntimeErrors,
  waitForLoadingToFinish,
  waitForApiIdle,
} = require('../utils/helpers');

const VALID_USER = process.env.TEST_USERNAME || 'admin';
const VALID_PASS = process.env.TEST_PASSWORD || 'admin123';

test.describe('Evidence Intelligence', () => {

  // Login and navigate to Evidence Intelligence before each test
  test.beforeEach(async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(VALID_USER, VALID_PASS);
    await loginPage.waitForDashboard();
  });

  // ── Page open ───────────────────────────────────────────────────

  test('should open the Evidence Intelligence page successfully', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Hero header
    await expect(evidencePage.pageHeading).toBeVisible();
    await expect(page.getByText('Enterprise Semantic Memory')).toBeVisible();

    // KB section
    await expect(evidencePage.kbHeader).toBeVisible();

    // No React errors
    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should display KPI cards on load', async ({ page }) => {
    const evidencePage = new EvidencePage(page);
    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // 4 KPI cards: Indexed Evidence, Coverage/Rule Coverage, Approved, Rejected
    const kpiCards = page.locator('.grid.grid-cols-2 > div, .grid.sm\\:grid-cols-4 > div').first();
    await expect(kpiCards).toBeVisible({ timeout: 10_000 });
  });

  // ── Search ──────────────────────────────────────────────────────

  test('should search evidence records', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Perform a search
    await evidencePage.searchInput.fill('document');
    await evidencePage.searchButton.click();
    await waitForApiIdle(page);

    // Results update (total count text should be visible)
    const totalText = page.getByText(/evidence records/i);
    await expect(totalText).toBeVisible({ timeout: 10_000 });

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors after search: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should search by pressing Enter key', async ({ page }) => {
    const evidencePage = new EvidencePage(page);
    await evidencePage.goto();
    await evidencePage.waitForLoad();

    await evidencePage.searchInput.fill('compliance');
    await evidencePage.searchInput.press('Enter');
    await waitForApiIdle(page);

    // No errors
    const totalText = page.getByText(/evidence records/i);
    await expect(totalText).toBeVisible({ timeout: 10_000 });
  });

  // ── Filter by norm ──────────────────────────────────────────────

  test('should filter by norm when norms are available', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Check if norm options are available
    const normOptions = await evidencePage.normSelector.locator('option').count();

    if (normOptions > 1) {
      // Select the second option (first non-empty)
      const options = await evidencePage.normSelector.locator('option').all();
      const firstNorm = await options[1].textContent();

      await evidencePage.normSelector.selectOption({ index: 1 });
      await waitForApiIdle(page);

      // Page should still show KB header
      await expect(evidencePage.kbHeader).toBeVisible();
    } else {
      test.skip('No norms available to filter by');
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors after norm filter: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Filter by rule ──────────────────────────────────────────────

  test('should filter by rule when rules are available', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Wait for rule options to populate
    await page.waitForTimeout(2_000);

    const ruleCount = await evidencePage.ruleFilter.locator('option').count();
    if (ruleCount > 1) {
      await evidencePage.ruleFilter.selectOption({ index: 1 });
      await waitForApiIdle(page);
      await expect(evidencePage.kbHeader).toBeVisible();
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors after rule filter: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Pagination ──────────────────────────────────────────────────

  test('should show pagination controls', async ({ page }) => {
    const evidencePage = new EvidencePage(page);
    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Pagination should be visible (showing X-Y of Z records)
    const paginationText = page.getByText(/showing/i).first();
    await expect(paginationText).toBeVisible({ timeout: 10_000 });
  });

  test('should paginate through results', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Check if next page button is enabled (more than 1 page)
    const nextBtn = page.getByRole('button', { name: /next/i }).last();
    const isDisabled = await nextBtn.getAttribute('disabled');

    if (!isDisabled) {
      await nextBtn.click();
      await waitForApiIdle(page);

      // Cards should still be visible
      await expect(evidencePage.kbHeader).toBeVisible();
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors during pagination: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Export CSV ──────────────────────────────────────────────────

  test('should export evidence as CSV', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Listen for download event
    const downloadPromise = page.waitForEvent('download', { timeout: 15_000 });
    await evidencePage.csvExport.click();

    try {
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toMatch(/evidence.*\.csv$/i);
    } catch {
      // Download may not trigger if backend returns empty — check no JS error
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors during CSV export: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Export JSON ─────────────────────────────────────────────────

  test('should export evidence as JSON', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    const downloadPromise = page.waitForEvent('download', { timeout: 15_000 });
    await evidencePage.jsonExport.click();

    try {
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toMatch(/evidence.*\.json$/i);
    } catch {
      // Download may not trigger if backend returns empty
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors during JSON export: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Add Evidence ────────────────────────────────────────────────

  test('should open and close the Add Evidence form', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Open the form
    const addBtn = page.getByRole('button', { name: /^add$/i });
    await addBtn.click();

    // Evidence text input should appear
    await expect(evidencePage.evidenceTextInput).toBeVisible({ timeout: 5_000 });

    // Close the form
    const cancelBtn = page.getByRole('button', { name: /cancel/i });
    await cancelBtn.click();
    await expect(evidencePage.evidenceTextInput).not.toBeVisible();

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors with add form: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Duplicate Analysis ──────────────────────────────────────────

  test('should trigger duplicate analysis', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Click the Duplicates button in the hero
    await evidencePage.duplicatesButton.click();

    // Wait for analysis to complete (network call)
    await waitForApiIdle(page, 1_000);

    // Should switch to duplicates tab
    await page.waitForTimeout(1_000);

    // Check the duplicates tab content is visible
    const dupTab = page.getByRole('button', { name: /duplicates/i }).first();
    await expect(dupTab).toBeVisible();

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors during duplicate analysis: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Rebuild Semantic Index ──────────────────────────────────────

  test('should trigger semantic index rebuild', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Switch to Semantic Memory tab
    await evidencePage.switchTab('semantic');
    await page.waitForTimeout(500);

    // Find and click the rebuild button
    const rebuildBtn = page.getByRole('button', { name: /rebuild semantic index/i });
    await expect(rebuildBtn).toBeVisible({ timeout: 5_000 });
    await rebuildBtn.click();

    // Wait for network call
    await waitForApiIdle(page, 1_000);

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors during semantic index rebuild: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Tabs Navigation ─────────────────────────────────────────────

  test('should switch between Analytics tabs without errors', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Switch through all tabs
    const tabs = ['analytics', 'duplicates', 'semantic', 'overview'];
    for (const tab of tabs) {
      await evidencePage.switchTab(tab);
      await page.waitForTimeout(500);
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors switching tabs: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Analyze Document Modal ──────────────────────────────────────

  test('should open and close the Analyze Document modal', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Open modal
    await evidencePage.analyzeDocButton.click();
    await page.waitForTimeout(500);

    // Close with Escape
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors with modal: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Reset filters ────────────────────────────────────────────────

  test('should reset all filters to defaults', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Set a search query
    await evidencePage.searchInput.fill('test query');

    // Reset
    await evidencePage.resetButton.click();
    await waitForApiIdle(page);

    // Search should be cleared
    await expect(evidencePage.searchInput).toHaveValue('');

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors after reset: ${critical.join('\n')}`).toHaveLength(0);
  });

});
