// =====================================================================
// tests/regression/react-rendering.spec.js
//
// COMPREHENSIVE React 19 Rendering & DOM Reconciliation Regression Suite
//
// Every test in this file:
//   1. Attaches createMonitor() — captures pageerror, console, requestfailed
//   2. Fails immediately if any critical pattern is matched:
//        insertBefore · NotFoundError · removeChild · appendChild
//        React · Hydration · Cannot read properties
//        Maximum update depth exceeded · Too many re-renders
//        Duplicate key warnings
//   3. Flushes all logs to playwright-report/runtime-errors.log
//   4. Takes a screenshot automatically on failure (via playwright.config.js)
//   5. Is fully CI/Jenkins compatible (no interactive prompts, no open=always)
//
// PAGES UNDER TEST:
//   Evidence Intelligence  — heaviest React reconciliation risk
//   Dashboard              — rapid navigation stress
//   Documents              — detail open / back / repeat
//
// =====================================================================

'use strict';

const { test, expect } = require('@playwright/test');
const { createMonitor }  = require('../utils/runtime-logger');
const { LoginPage }      = require('../pages/LoginPage');
const { EvidencePage }   = require('../pages/EvidencePage');
const { DashboardPage }  = require('../pages/DashboardPage');
const { DocumentPage }   = require('../pages/DocumentPage');

// ── Credentials (override via env for CI) ───────────────────────────
const USER = process.env.TEST_USERNAME || 'admin';
const PASS = process.env.TEST_PASSWORD || 'admin123';
const BASE = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';

// ── Helpers ──────────────────────────────────────────────────────────

/** Navigate using the HashRouter convention. */
async function go(page, route) {
  await page.goto(`${BASE}/#${route}`);
  await page.waitForLoadState('domcontentloaded');
}

/** Login once and land on dashboard. */
async function loginAs(page, user = USER, pass = PASS) {
  const lp = new LoginPage(page);
  await lp.goto();
  await lp.login(user, pass);
  await lp.waitForDashboard();
}

/**
 * Wait for skeletons / spinners to clear, then assert body is visible.
 * Also runs monitor.assertClean() so the test fails fast on any error.
 */
async function settle(page, monitor, label = '') {
  // Skeletons
  await page.waitForFunction(
    () => document.querySelectorAll('.animate-pulse').length === 0,
    { timeout: 20_000 }
  ).catch(() => {});

  // Network quiet
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});

  // DOM integrity — body must always be visible
  await expect(page.locator('body')).toBeVisible();

  // Fail-fast on any critical runtime error collected so far
  monitor.assertClean(label);
}

/**
 * Safe click: only clicks if the locator is visible; otherwise skips.
 * Returns true if clicked, false if skipped.
 */
async function safeClick(locator) {
  const visible = await locator.isVisible({ timeout: 2_000 }).catch(() => false);
  if (visible) { await locator.click(); return true; }
  return false;
}

/**
 * Safe select: selects option by index, skips if unavailable.
 */
async function safeSelectIndex(selectLocator, index) {
  const options = await selectLocator.locator('option').all();
  if (options.length > index) {
    await selectLocator.selectOption({ index }).catch(() => {});
  }
}


// =====================================================================
// SECTION 1 — Evidence Intelligence: Initial Load & DOM Integrity
// =====================================================================

test.describe('React Rendering — Evidence Intelligence Load', () => {

  test.beforeEach(async ({ page }) => {
    await loginAs(page);
  });

  // ------------------------------------------------------------------
  test('EI-01: page loads without any runtime errors', async ({ page }, testInfo) => {
    const mon = createMonitor(page);
    try {
      const ei = new EvidencePage(page);
      await ei.goto();
      await settle(page, mon, 'EI-01 initial load');

      await expect(ei.pageHeading).toBeVisible();
      await expect(ei.kbHeader).toBeVisible();
      await expect(page.locator('body')).toBeVisible();

      mon.assertClean('EI-01');
    } finally {
      mon.flush(testInfo.title);
    }
  });

  // ------------------------------------------------------------------
  test('EI-02: no insertBefore / NotFoundError on first render of evidence cards', async ({ page }, testInfo) => {
    const mon = createMonitor(page);
    try {
      const ei = new EvidencePage(page);
      await ei.goto();
      await settle(page, mon, 'EI-02 card render');

      // Cards grid must be present (even if empty)
      await expect(page.locator('body')).toBeVisible();

      const insertBeforeHits = mon.runtimeErrors
        .concat(mon.consoleErrors)
        .filter(m => /insertBefore|NotFoundError/i.test(m));

      expect(
        insertBeforeHits,
        `insertBefore / NotFoundError on card render:\n${insertBeforeHits.join('\n')}`
      ).toHaveLength(0);
    } finally {
      mon.flush(testInfo.title);
    }
  });

  // ------------------------------------------------------------------
  test('EI-03: no duplicate React key warnings in evidence card list', async ({ page }, testInfo) => {
    const mon = createMonitor(page);
    try {
      const ei = new EvidencePage(page);
      await ei.goto();
      await settle(page, mon, 'EI-03 key warnings');

      const keyWarnings = mon.consoleWarnings
        .concat(mon.consoleErrors)
        .filter(m =>
          /Each child in a list should have a unique.*key/i.test(m) ||
          /Encountered two children with the same key/i.test(m)
        );

      expect(
        keyWarnings,
        `Duplicate React key warnings:\n${keyWarnings.join('\n')}`
      ).toHaveLength(0);
    } finally {
      mon.flush(testInfo.title);
    }
  });

});

