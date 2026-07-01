// =====================================================================
// tests/pages/LoginPage.js
// Page Object for the Login page
// =====================================================================

class LoginPage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    this.page = page;

    // Locators based on actual Login.js structure
    this.emailInput    = page.locator('#login');
    this.passwordInput = page.locator('#password');
    this.submitButton  = page.getByRole('button', { name: /sign in/i });
    this.errorAlert    = page.getByRole('alert');
    this.showPasswordBtn = page.getByRole('button', { name: /show password|hide password/i });
    this.capsLockWarning = page.locator('text=Caps Lock is on');
    this.forgotPasswordLink = page.getByRole('button', { name: /forgot password/i });
  }

  /** Navigate to the login page */
  async goto() {
    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
    await this.page.goto(`${base}/#/login`);
    await this.page.waitForLoadState('domcontentloaded');
  }

  /** Fill credentials and submit the form */
  async login(username, password) {
    await this.emailInput.waitFor({ state: 'visible', timeout: 15_000 });
    await this.emailInput.fill(username);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  /** Wait until the dashboard is reached after login */
  async waitForDashboard(timeout = 20_000) {
    await this.page.waitForURL(/\/#\/dashboard/, { timeout });
  }

  /** Get the text of the error alert */
  async getErrorMessage() {
    await this.errorAlert.waitFor({ state: 'visible', timeout: 5_000 });
    return this.errorAlert.textContent();
  }

  /** Check if login form is visible */
  async isVisible() {
    return this.emailInput.isVisible();
  }

  /** Toggle password visibility */
  async togglePasswordVisibility() {
    await this.showPasswordBtn.click();
  }

  /** Click forgot password link */
  async clickForgotPassword() {
    await this.forgotPasswordLink.click();
  }
}

module.exports = { LoginPage };
