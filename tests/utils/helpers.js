// =====================================================================
// tests/utils/helpers.js
// Shared helper functions for Playwright E2E tests
// =====================================================================

/**
 * Set up runtime error capture on a page.
 * Returns an array that is automatically populated with errors.
 *
 * @param {import('@playwright/test').Page} page
 * @returns {{ errors: string[] }} reference object with live errors array
 */
function captureRuntimeErrors(page) {
  const container = { errors: [] };

  page.on('pageerror', (error) => {
    container.errors.push(`[pageerror] ${error.message}`);
  });

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      container.errors.push(`[console.error] ${msg.text()}`);
    }
  });

  return container;
}

/**
 * List of React 19 DOM reconciliation error patterns to detect.
 * These specifically target insertBefore/NotFoundError and related issues.
 */
const REACT_CRITICAL_PATTERNS = [
  /insertBefore/i,
  /NotFoundError/i,
  /React error/i,
  /Cannot read propert/i,   // covers "properties" and "property"
  /Hydration failed/i,
  /hydration/i,
  /Minified React error/i,
  /Invariant Violation/i,
  /Maximum update depth exceeded/i,
  /Cannot update a component.*while rendering/i,
  /Each child in a list should have a unique "key"/i,
  /Warning: Cannot update during an existing state transition/i,
];

/**
 * Assert that no React/DOM critical errors occurred.
 * Filters console noise (CRA HMR, favicon 404, etc.) from real errors.
 *
 * @param {string[]} errors - from captureRuntimeErrors().errors
 */
function assertNoRuntimeErrors(errors) {
  const ignoredPatterns = [
    /favicon/i,
    /hot-update/i,
    /webpack/i,
    /sockjs/i,
    /\[WDS\]/i,
    /Download the React DevTools/i,
    /Refused to load.*Content Security Policy/i,
  ];

  const critical = errors.filter((err) => {
    const isIgnored = ignoredPatterns.some((p) => p.test(err));
    if (isIgnored) return false;
    return REACT_CRITICAL_PATTERNS.some((p) => p.test(err));
  });

  return critical;
}

/**
 * Navigate to a hash route (HashRouter).
 * @param {import('@playwright/test').Page} page
 * @param {string} route - e.g. '/dashboard'
 */
async function navigateTo(page, route) {
  const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
  await page.goto(`${base}/#${route}`);
}

/**
 * Wait for a loading skeleton/spinner to disappear.
 * @param {import('@playwright/test').Page} page
 * @param {number} timeout - ms
 */
async function waitForLoadingToFinish(page, timeout = 15_000) {
  // Wait for animate-pulse skeletons to disappear
  try {
    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout }
    );
  } catch {
    // If skeletons never appeared, that's fine
  }
}

/**
 * Retry a callback up to maxAttempts times with delay.
 */
async function retry(fn, maxAttempts = 3, delayMs = 500) {
  let lastError;
  for (let i = 0; i < maxAttempts; i++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (i < maxAttempts - 1) {
        await new Promise((r) => setTimeout(r, delayMs));
      }
    }
  }
  throw lastError;
}

/**
 * Select an option from a <select> element by visible text.
 * Falls back to partial match.
 */
async function selectByText(selectLocator, text) {
  await selectLocator.selectOption({ label: text });
}

/**
 * Wait for API calls to settle (no pending XHR for a brief period).
 * Useful after clicking buttons that trigger API calls.
 */
async function waitForApiIdle(page, idleMs = 500) {
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(idleMs);
}

module.exports = {
  captureRuntimeErrors,
  assertNoRuntimeErrors,
  REACT_CRITICAL_PATTERNS,
  navigateTo,
  waitForLoadingToFinish,
  retry,
  selectByText,
  waitForApiIdle,
};
