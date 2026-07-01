// =====================================================================
// tests/pages/DocumentPage.js
// Page Object for the Documents page
// =====================================================================

const path = require('path');

class DocumentPage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    this.page = page;

    // Upload area
    this.uploadInput     = page.locator('input[type="file"]');
    this.uploadBox       = page.locator('.upload-box, [data-testid="upload-box"]').first();

    // Document table / list
    this.documentRows    = page.locator('table tbody tr').filter({ hasNot: page.locator('.skeleton') });
    this.documentLinks   = page.locator('table tbody tr a, table tbody tr [role="link"]');

    // Filter / search
    this.statusFilter    = page.locator('select').filter({ hasText: /all status|tous|pending|approved/i }).first();
    this.searchInput     = page.getByPlaceholder(/search|rechercher/i).first();

    // Action buttons
    this.refreshButton   = page.getByRole('button', { name: /refresh|actualiser/i }).first();
    this.analyzeButton   = page.getByRole('button', { name: /analyze|analyser|brain/i }).first();

    // KPI stat cards
    this.statCards       = page.locator('.kpi-card');

    // Analyze modal
    this.analyzeModal    = page.locator('[role="dialog"]');

    // Pagination
    this.nextBtn         = page.getByRole('button', { name: /next|suivant/i }).last();
    this.prevBtn         = page.getByRole('button', { name: /previous|précédent/i }).last();

    // Loading
    this.loadingRow      = page.locator('.skeleton').first();
  }

  /** Navigate to the Documents page */
  async goto() {
    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
    await this.page.goto(`${base}/#/documents`);
    await this.page.waitForLoadState('domcontentloaded');
  }

  /** Wait for the documents page to load */
  async waitForLoad(timeout = 20_000) {
    // Wait for URL
    await this.page.waitForURL(/\/#\/documents/, { timeout: 10_000 }).catch(() => {});

    // Wait for skeletons to clear
    await this.page.waitForFunction(
      () => document.querySelectorAll('.skeleton').length === 0,
      { timeout }
    ).catch(() => {});
  }

  /**
   * Upload a document via the file input.
   * @param {string} filePath - Absolute path to the test file
   */
  async uploadDocument(filePath) {
    await this.uploadInput.waitFor({ state: 'attached', timeout: 10_000 });
    await this.uploadInput.setInputFiles(filePath);
    // Wait for upload to process
    await this.page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {});
  }

  /**
   * Click the first document's Analyze button.
   */
  async analyzeFirstDocument() {
    const analyzeBtn = this.documentRows
      .first()
      .getByRole('button', { name: /analyze|analyser/i });
    if (await analyzeBtn.isVisible()) {
      await analyzeBtn.click();
    } else {
      // Fallback: try the main analyze button
      await this.analyzeButton.click();
    }
    await this.page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  }

  /**
   * Open the first document's detail view.
   */
  async openFirstDocument() {
    const firstLink = this.page.locator('table tbody tr').first()
      .locator('a, button').first();
    if (await firstLink.isVisible()) {
      await firstLink.click();
      await this.page.waitForLoadState('domcontentloaded', { timeout: 10_000 }).catch(() => {});
    }
  }

  /**
   * Filter documents by status.
   * @param {string} status - e.g. 'pending', 'approved', 'rejected'
   */
  async filterByStatus(status) {
    await this.statusFilter.selectOption({ value: status });
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  /** Count the visible document rows */
  async getDocumentCount() {
    return this.documentRows.count();
  }

  /** Get total documents from KPI card */
  async getTotalFromKpi() {
    const card = this.statCards.first();
    const valueEl = card.locator('.kpi-value, .text-3xl, .text-2xl').first();
    return valueEl.textContent().catch(() => '—');
  }
}

module.exports = { DocumentPage };
