// =====================================================================
// tests/pages/EvidencePage.js
// Page Object for the Evidence Intelligence page
// =====================================================================

class EvidencePage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    this.page = page;

    // Hero header
    this.pageHeading   = page.getByText('Enterprise Semantic Memory');
    this.normSelector  = page.locator('select').filter({ hasText: /toutes les normes|all/i }).first();

    // Action buttons (in hero)
    this.refreshButton       = page.getByRole('button', { name: /refresh/i });
    this.duplicatesButton    = page.getByRole('button', { name: /duplicates/i });
    this.analyzeDocButton    = page.getByRole('button', { name: /analyze doc/i });
    this.trainMemoryButton   = page.getByRole('button', { name: /train memory/i });

    // Knowledge Base section
    this.kbHeader    = page.getByText('Knowledge Base', { exact: true });
    this.addButton   = page.getByRole('button', { name: /^add$/i });
    this.csvExport   = page.getByRole('button', { name: /csv/i });
    this.jsonExport  = page.getByRole('button', { name: /json/i });

    // Filters
    this.searchInput  = page.getByPlaceholder(/search evidence/i);
    this.searchButton = page.getByRole('button', { name: /^search$/i });
    this.resetButton  = page.getByRole('button', { name: /reset/i });
    this.ruleFilter   = page.locator('select').filter({ hasText: /all rules/i });
    this.labelFilter  = page.locator('select').filter({ hasText: /all labels/i });
    this.sortSelect   = page.locator('select').filter({ hasText: /newest/i });

    // Evidence cards grid
    this.evidenceCards = page.locator('.rounded-2xl.border.bg-white.shadow-sm').filter({
      hasNot: page.locator('.kpi-card'),
    });

    // Pagination
    this.nextPageButton = page.getByRole('button', { name: /next/i }).last();
    this.prevPageButton = page.getByRole('button', { name: /previous/i }).last();

    // Analytics tabs
    this.overviewTab   = page.getByRole('button', { name: /overview/i });
    this.analyticsTab  = page.getByRole('button', { name: /analytics/i });
    this.duplicatesTab = page.getByRole('button', { name: /duplicates/i });
    this.semanticTab   = page.getByRole('button', { name: /semantic memory/i });

    // Analyze modal (opened via Analyze Doc button)
    this.analyzeModal = page.locator('[role="dialog"]');

    // Add form
    this.evidenceTextInput = page.getByPlaceholder(/evidence text/i);
    this.addToKbButton     = page.getByRole('button', { name: /add to kb/i });

    // Rebuild semantic index button (in Semantic Memory tab)
    this.rebuildIndexButton = page.getByRole('button', { name: /rebuild semantic index/i });
  }

  /** Navigate to Evidence Intelligence page */
  async goto() {
    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
    await this.page.goto(`${base}/#/evidence-intelligence`);
    await this.page.waitForLoadState('domcontentloaded');
  }

  /** Wait for the page to load (KPI cards visible) */
  async waitForLoad(timeout = 20_000) {
    await this.pageHeading.waitFor({ state: 'visible', timeout });
    // Wait for loading states to clear
    await this.page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout }
    ).catch(() => {});
  }

  /** Select a norm from the norm dropdown */
  async selectNorm(normName) {
    await this.normSelector.selectOption({ label: normName });
    // Wait for data to reload
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  /** Clear norm filter */
  async clearNorm() {
    const clearBtn = this.page.getByRole('button', { name: /✕ clear|clear/i });
    if (await clearBtn.isVisible()) {
      await clearBtn.click();
    } else {
      await this.normSelector.selectOption('');
    }
  }

  /** Perform a search */
  async search(query) {
    await this.searchInput.fill(query);
    await this.searchButton.click();
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  /** Filter by rule */
  async filterByRule(ruleName) {
    await this.ruleFilter.selectOption({ label: ruleName });
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  /** Filter by label */
  async filterByLabel(label) {
    await this.labelFilter.selectOption({ label });
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  /** Reset all filters */
  async resetFilters() {
    await this.resetButton.click();
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  /** Go to next page */
  async goToNextPage() {
    const isDisabled = await this.nextPageButton.getAttribute('disabled');
    if (!isDisabled) {
      await this.nextPageButton.click();
      await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
    }
  }

  /** Go to previous page */
  async goToPrevPage() {
    const isDisabled = await this.prevPageButton.getAttribute('disabled');
    if (!isDisabled) {
      await this.prevPageButton.click();
      await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
    }
  }

  /** Switch to a tab by id */
  async switchTab(tabName) {
    const tabMap = {
      overview:   this.overviewTab,
      analytics:  this.analyticsTab,
      duplicates: this.duplicatesTab,
      semantic:   this.semanticTab,
    };
    const tab = tabMap[tabName.toLowerCase()];
    if (tab) {
      await tab.click();
      await this.page.waitForTimeout(300);
    }
  }

  /** Open the Add Evidence form */
  async openAddForm() {
    await this.addButton.click();
    await this.evidenceTextInput.waitFor({ state: 'visible', timeout: 5_000 });
  }

  /** Close the Add Evidence form */
  async closeAddForm() {
    const cancelBtn = this.page.getByRole('button', { name: /cancel/i });
    if (await cancelBtn.isVisible()) {
      await cancelBtn.click();
    }
  }

  /** Open the Analyze Document modal */
  async openAnalyzeModal() {
    await this.analyzeDocButton.click();
    await this.analyzeModal.waitFor({ state: 'visible', timeout: 5_000 }).catch(() => {});
  }

  /** Close the Analyze Document modal */
  async closeAnalyzeModal() {
    const closeBtn = this.page.locator('[role="dialog"] button').filter({ hasText: /×|close|✕/i }).first();
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
    } else {
      await this.page.keyboard.press('Escape');
    }
  }

  /** Trigger duplicate analysis */
  async analyzeDuplicates() {
    await this.duplicatesButton.click();
    await this.page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await this.switchTab('duplicates');
  }

  /** Trigger rebuild semantic index */
  async rebuildSemanticIndex() {
    await this.switchTab('semantic');
    await this.rebuildIndexButton.waitFor({ state: 'visible', timeout: 5_000 });
    await this.rebuildIndexButton.click();
    await this.page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  }

  /** Export evidence as CSV */
  async exportCSV() {
    const [download] = await Promise.all([
      this.page.waitForEvent('download', { timeout: 15_000 }),
      this.csvExport.click(),
    ]);
    return download;
  }

  /** Export evidence as JSON */
  async exportJSON() {
    const [download] = await Promise.all([
      this.page.waitForEvent('download', { timeout: 15_000 }),
      this.jsonExport.click(),
    ]);
    return download;
  }

  /** Get count of visible evidence cards */
  async getCardCount() {
    // Use the evidence cards in the KB grid
    const grid = this.page.locator('.grid.grid-cols-1.gap-3 .rounded-2xl');
    return grid.count();
  }

  /** Get the total records text */
  async getTotalRecordsText() {
    return this.page.getByText(/\d+ evidence records/).textContent();
  }
}

module.exports = { EvidencePage };
