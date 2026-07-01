// =====================================================================
// tests/fixtures/auth.fixture.js
// Reusable Playwright fixtures for authenticated sessions
// =====================================================================

const { test: base } = require('@playwright/test');
const { LoginPage } = require('../pages/LoginPage');

/**
 * Authenticated fixture: extends the base test with a pre-logged-in page.
 * Uses storageState to persist authentication across tests when possible.
 */
const test = base.extend({
  /**
   * authenticatedPage — provides a page already logged in as ADMIN.
   * Usage in tests: test('name', async ({ authenticatedPage }) => { ... })
   */
  authenticatedPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(
      process.env.TEST_USERNAME || 'admin',
      process.env.TEST_PASSWORD || 'admin123'
    );
    await loginPage.waitForDashboard();
    await use(page);
  },
});

module.exports = { test };
