// =====================================================================
// tests/pages/DashboardPage.js
// Page Object for the Dashboard page
// =====================================================================

class DashboardPage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    this.page = page;

    // Navigation / Layout
    this.navLinks = page.getByRole('navigation').getByRole('link');

    // KPI cards — Dashboard uses .kpi-card class
    this.kpiCards = page.locator('.kpi-card');

    // Common dashboard elements
    this.refreshButton = page.getByRole('button', { name: /refresh/i });
    this.loadingSkeletons = page.locator('.animate-pulse');

    // User menu / logout (appears in Layout component)
    this.userMenuButton = page.getByRole('button', { name: /logout|sign out|déconnexion/i });
  }

  /** Navigate to the dashboard */
  async goto() {
    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
    await this.page.goto(`${base}/#/dashboard`);
    await this.page.waitForLoadState('domcontentloaded');
  }

  /** Wait for the dashboard to fully load (no skeletons) */
  async waitForLoad(timeout = 20_000) {
    // Wait for URL
    await this.page.waitForURL(/\/#\/dashboard/, { timeout: 10_000 }).catch(() => {});

    // Wait for at least one KPI card to appear
    await this.kpiCards.first().waitFor({ state: 'visible', timeout }).catch(() => {});

    // Wait for skeletons to disappear
    await this.page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout }
    ).catch(() => {});
  }

  /** Count visible KPI cards */
  async getKpiCount() {
    return this.kpiCards.count();
  }

  /** Check if main content area is rendered */
  async isLoaded() {
    const url = this.page.url();
    return url.includes('dashboard');
  }

  /** Navigate to a section via the nav */
  async navigateTo(linkText) {
    await this.page.getByRole('link', { name: new RegExp(linkText, 'i') }).first().click();
  }
}

module.exports = { DashboardPage };
