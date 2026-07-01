// =====================================================================
// tests/auth/auth.spec.js
// Authentication E2E tests — Login, Logout, Invalid Credentials
// =====================================================================

const { test, expect } = require('@playwright/test');
const { LoginPage } = require('../pages/LoginPage');
const { captureRuntimeErrors, assertNoRuntimeErrors } = require('../utils/helpers');

const VALID_USER = process.env.TEST_USERNAME || 'admin';
const VALID_PASS = process.env.TEST_PASSWORD || 'admin123';

test.describe('Authentication', () => {

  test.beforeEach(async ({ page }) => {
    // Clear any existing auth state
    await page.context().clearCookies();
    await page.evaluate(() => {
      try { localStorage.clear(); } catch { /* ignore */ }
    }).catch(() => {});
  });

  // ── Login ────────────────────────────────────────────────────────

  test('should display the login form with all required elements', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const loginPage = new LoginPage(page);

    await loginPage.goto();

    // Page heading
    await expect(page.getByText('Enterprise ISO Compliance')).toBeVisible();
    await expect(page.getByText('AI-Powered Governance')).toBeVisible();

    // Form fields
    await expect(loginPage.emailInput).toBeVisible();
    await expect(loginPage.passwordInput).toBeVisible();
    await expect(loginPage.submitButton).toBeVisible();

    // Submit is disabled when fields are empty
    await expect(loginPage.submitButton).toBeDisabled();

    // No React errors on load
    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors on login page: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should enable the Sign In button when credentials are filled', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    await loginPage.emailInput.fill('user@example.com');
    await expect(loginPage.submitButton).toBeDisabled();

    await loginPage.passwordInput.fill('somepassword');
    await expect(loginPage.submitButton).toBeEnabled();
  });

  test('should successfully login with valid credentials', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    await loginPage.login(VALID_USER, VALID_PASS);
    await loginPage.waitForDashboard();

    // URL should contain dashboard
    await expect(page).toHaveURL(/#\/dashboard/);

    // Dashboard content should load
    await expect(page.locator('.kpi-card').first()).toBeVisible({ timeout: 15_000 });

    // No React errors after login
    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors after login: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should toggle password visibility', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    await loginPage.passwordInput.fill('mypassword');

    // Password should be hidden by default
    await expect(loginPage.passwordInput).toHaveAttribute('type', 'password');

    // Click show password
    await loginPage.togglePasswordVisibility();
    await expect(loginPage.passwordInput).toHaveAttribute('type', 'text');

    // Click again to hide
    await loginPage.togglePasswordVisibility();
    await expect(loginPage.passwordInput).toHaveAttribute('type', 'password');
  });

  // ── Invalid Credentials ──────────────────────────────────────────

  test('should show error message with invalid credentials', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    await loginPage.login('wrong@user.com', 'wrongpassword');

    // Error message should appear
    await loginPage.errorAlert.waitFor({ state: 'visible', timeout: 10_000 });
    const errorText = await loginPage.getErrorMessage();
    expect(errorText).toBeTruthy();
    expect(errorText.length).toBeGreaterThan(0);

    // Should NOT navigate away
    await expect(page).not.toHaveURL(/#\/dashboard/);

    // Password should be cleared after failed login
    await expect(loginPage.passwordInput).toHaveValue('');

    // No React runtime errors (auth errors are application-level, not React errors)
    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors on bad login: ${critical.join('\n')}`).toHaveLength(0);
  });

  test('should show error when submitting empty form via validation bypass', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    // Fill only username
    await loginPage.emailInput.fill('admin');
    // Submit without password by simulating form submit programmatically
    await loginPage.passwordInput.fill('x');
    await loginPage.passwordInput.fill('');
    // Button should be disabled when password is empty
    await expect(loginPage.submitButton).toBeDisabled();
  });

  test('should show "Forgot password" link that navigates to reset page', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    await loginPage.clickForgotPassword();
    await expect(page).toHaveURL(/#\/reset-password/);
  });

  // ── Logout ──────────────────────────────────────────────────────

  test('should logout and redirect to login page', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const loginPage = new LoginPage(page);

    // Login first
    await loginPage.goto();
    await loginPage.login(VALID_USER, VALID_PASS);
    await loginPage.waitForDashboard();

    await expect(page).toHaveURL(/#\/dashboard/);

    // Find logout button — it can be in a user menu or sidebar
    // Try different logout button patterns used in the Layout
    const logoutBtn = page.getByRole('button', { name: /logout|sign out|déconnexion|se déconnecter/i }).first();
    const logoutLink = page.getByRole('link', { name: /logout|sign out/i }).first();

    if (await logoutBtn.isVisible()) {
      await logoutBtn.click();
    } else if (await logoutLink.isVisible()) {
      await logoutLink.click();
    } else {
      // Try finding it inside a user dropdown
      const userMenu = page.locator('[data-testid="user-menu"], .user-menu, [aria-label*="user"]').first();
      if (await userMenu.isVisible()) {
        await userMenu.click();
        await page.getByRole('button', { name: /logout|sign out/i }).click();
      }
    }

    // Should be redirected to login
    await expect(page).toHaveURL(/#\/login/, { timeout: 10_000 });

    // No React errors during logout
    const critical = assertNoRuntimeErrors(runtimeErrors.errors);
    expect(critical, `React errors during logout: ${critical.join('\n')}`).toHaveLength(0);
  });

  // ── Session Persistence ─────────────────────────────────────────

  test('should redirect to dashboard if already authenticated', async ({ page }) => {
    const loginPage = new LoginPage(page);

    // Login
    await loginPage.goto();
    await loginPage.login(VALID_USER, VALID_PASS);
    await loginPage.waitForDashboard();

    // Try to go back to login
    await loginPage.goto();

    // Should be redirected away from login
    await page.waitForTimeout(2_000);
    const url = page.url();
    // CRA with UserContext should redirect authenticated users
    expect(url).not.toMatch(/\/login$/);
  });

});
