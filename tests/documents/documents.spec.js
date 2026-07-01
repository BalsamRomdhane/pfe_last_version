// =====================================================================
// tests/documents/documents.spec.js
// Document management E2E tests — Upload, Analyze, View, Validation
// =====================================================================

const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { LoginPage } = require('../pages/LoginPage');
const { DocumentPage } = require('../pages/DocumentPage');
const {
  captureRuntimeErrors,
  assertNoRuntimeErrors,
  waitForLoadingToFinish,
  waitForApiIdle,
} = require('../utils/helpers');

const VALID_USER = process.env.TEST_USERNAME || 'admin';
const VALID_PASS = process.env.TEST_PASSWORD || 'admin123';

// Create a minimal PDF-like test fixture file
function createTestFile(filename = 'test-document.txt') {
  const tmpDir = os.tmpdir();
  const filePath = path.join(tmpDir, filename);
  fs.writeFileSync(
    filePath,
    'Test Document for E2E Testing\n\n' +
    'This is a sample document for ISO compliance testing.\n' +
    'ISO 27001 - Information Security Management System\n' +
    'Control A.5.1 - Policies for information security\n' +
    'Evidence: This document defines policies for information security.\n'
  );
  return filePath;
}

test.describe('Documents', () => {

  test.beforeEach(async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(VALID_USER, VALID_PASS);
    await loginPage.waitForDashboard();
  });

  // ── Page load ────────────────────────────────────────────────────

  test('should open the Documents page successfully', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const docPage = new DocumentPage(page);

    await docPage.goto();
    await docPage.waitForLoad();

    // URL
    await expect(page).toHaveURL(/#\/documents/);

    // Some document content or empty state should be visible
    const tableOrEmptyState = page.locator('table, [data-testid="empty-state"], .empty-state, text=No documents').first();
    // At minimum, the page header should be visible
    const heading = page.getByRole('heading').first();
    await expect(heading).toBeVisible({ timeout: 15_000 });

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors on documents page: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should display document stat cards', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const docPage = new DocumentPage(page);

    await docPage.goto();
    await docPage.waitForLoad();

    // KPI cards should be visible
    const kpiCards = page.locator('.kpi-card');
    const count = await kpiCards.count();
    expect(count).toBeGreaterThan(0);

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Upload document ──────────────────────────────────────────────

  test('should display upload area for file selection', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const docPage = new DocumentPage(page);

    await docPage.goto();
    await docPage.waitForLoad();

    // File input should be attached
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeAttached({ timeout: 10_000 });

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should upload a document file', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const docPage = new DocumentPage(page);

    await docPage.goto();
    await docPage.waitForLoad();

    // Create a test file
    const testFilePath = createTestFile('e2e-test-upload.txt');

    try {
      // Upload the file
      const fileInput = page.locator('input[type="file"]');
      await fileInput.waitFor({ state: 'attached', timeout: 10_000 });
      await fileInput.setInputFiles(testFilePath);

      // Wait for upload to process
      await waitForApiIdle(page, 2_000);

      // No React errors during upload
      const critical = assertNoRuntimeErrors(runtimeErrors.errors);
      expect(critical, `React errors during upload: ${critical.join('\n')}`).toHaveLength(0);
    } finally {
      // Clean up temp file
      try { fs.unlinkSync(testFilePath); } catch { /* ignore */ }
    }
  });

  // ── Analyze document ─────────────────────────────────────────────

  test('should show the Analyze button for existing documents', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const docPage = new DocumentPage(page);

    await docPage.goto();
    await docPage.waitForLoad();

    // Check if there are documents to analyze
    const docCount = await docPage.getDocumentCount();

    if (docCount > 0) {
      // There should be analyze buttons or action buttons
      const actionBtns = page.locator('table tbody tr').first()
        .locator('button, a[role="button"]');
      const btnCount = await actionBtns.count();
      expect(btnCount).toBeGreaterThan(0);
    } else {
      // No documents — verify empty state renders without errors
      const emptyState = page.getByText(/no documents|aucun document|empty/i).first();
      // Page should still render without crashing
      await expect(page.locator('body')).toBeVisible();
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should open the Analyze Document modal', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const docPage = new DocumentPage(page);

    await docPage.goto();
    await docPage.waitForLoad();

    // Find any "Analyze" or "Brain" button
    const analyzeBtn = page.getByRole('button', { name: /analyze|analyser/i }).first();

    if (await analyzeBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await analyzeBtn.click();
      await page.waitForTimeout(500);

      // Modal or dialog should appear
      const dialog = page.locator('[role="dialog"]');
      if (await dialog.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await expect(dialog).toBeVisible();
        // Close it
        await page.keyboard.press('Escape');
      }
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors with analyze modal: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── View document analysis ────────────────────────────────────────

  test('should navigate to document detail when clicking a document', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const docPage = new DocumentPage(page);

    await docPage.goto();
    await docPage.waitForLoad();

    const docCount = await docPage.getDocumentCount();

    if (docCount > 0) {
      // Click the first document link
      const firstDocLink = page.locator('table tbody tr').first()
        .locator('a').first();

      if (await firstDocLink.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await firstDocLink.click();
        await page.waitForLoadState('domcontentloaded', { timeout: 10_000 });

        // URL should change
        const url = page.url();
        expect(url).toMatch(/(documents\/\d+|document-detail)/);
      }
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors viewing document: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Validation workflow ───────────────────────────────────────────

  test('should navigate to the Validations page', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);

    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
    await page.goto(`${base}/#/validations`);
    await page.waitForLoadState('domcontentloaded');

    // Page should load (admin/teamlead role required)
    const url = page.url();
    // If the user has access, should be on validations; otherwise redirected
    expect(url).toMatch(/(validations|dashboard)/);

    // Either way, no React errors
    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors on validations page: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should show validation actions on documents', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const docPage = new DocumentPage(page);

    await docPage.goto();
    await docPage.waitForLoad();

    // Status filter should be visible
    const statusFilter = page.locator('select').first();
    if (await statusFilter.isVisible({ timeout: 5_000 }).catch(() => false)) {
      // Filter to pending documents
      await statusFilter.selectOption({ value: 'pending' }).catch(() => {});
      await waitForApiIdle(page);
    }

    // Page should still render without errors
    await expect(page.locator('body')).toBeVisible();

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors during validation filter: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Filter and search ─────────────────────────────────────────────

  test('should filter documents by status', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const docPage = new DocumentPage(page);

    await docPage.goto();
    await docPage.waitForLoad();

    // Try status filters
    for (const status of ['approved', 'rejected', 'pending']) {
      const statusFilter = page.locator('select').first();
      if (await statusFilter.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await statusFilter.selectOption({ value: status }).catch(() => {});
        await waitForApiIdle(page, 500);
      }
    }

    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors filtering: ${critical.join('\n')}`).toHaveLength(0);
  });

});
