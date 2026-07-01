// =====================================================================
// tests/regression/react-dom-reconciliation.spec.js
//
// REGRESSION SUITE — React 19 DOM Reconciliation Issues
//
// Specifically targets:
//   - insertBefore / NotFoundError
//   - React reconciliation errors during rapid state changes
//   - AnimatePresence (framer-motion) unmount/mount race conditions
//   - Concurrent rendering issues with multiple tabs
//   - React 19 Strict Mode double-invocation issues
//
// HIGH-RISK PAGES IDENTIFIED:
//
//   1. EvidenceIntelligence.jsx
//      - Multiple simultaneous API calls + state updates
//      - AnimatePresence is NOT used but rapid filter changes
//        can cause stale closures in loadKB()
//      - EvidenceCard expand/collapse toggle (setOpen) while parent re-renders
//      - Pagination + filter combination
//
//   2. AIInsights.jsx
//      - AnimatePresence mode="wait" on tab content (line ~1240)
//        This is the #1 source of insertBefore errors in React 19
//        when the exiting component removes its DOM node before the
//        entering component inserts after it.
//      - 10 tabs, each with complex sub-trees
//      - DriftTab has its own internal state + useEffect chains
//      - AssistantTab uses AnimatePresence for history sidebar
//
//   3. Login.js
//      - AnimatePresence mode="wait" on error alert
//      - AnimatePresence mode="wait" on submit button states
//      - Bg() component: 22 particles, 5 orbital rings (key stability)
//
// =====================================================================

const { test, expect } = require('@playwright/test');
const { LoginPage } = require('../pages/LoginPage');
const { EvidencePage } = require('../pages/EvidencePage');
const {
  captureRuntimeErrors,
  assertNoRuntimeErrors,
  REACT_CRITICAL_PATTERNS,
  waitForApiIdle,
} = require('../utils/helpers');

const VALID_USER = process.env.TEST_USERNAME || 'admin';
const VALID_PASS = process.env.TEST_PASSWORD || 'admin123';

// ── Helper: strict error checker including insertBefore ──────────────
function checkForReconciliationErrors(errors) {
  return errors.filter((e) =>
    REACT_CRITICAL_PATTERNS.some((p) => p.test(e))
  );
}

// ─────────────────────────────────────────────────────────────────────
// GROUP 1: Login Page — AnimatePresence race conditions
// ─────────────────────────────────────────────────────────────────────
test.describe('Regression: Login AnimatePresence', () => {

  test('should NOT produce insertBefore errors when showing/hiding error message', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const loginPage = new LoginPage(page);

    await loginPage.goto();

    // Trigger error (bad credentials)
    await loginPage.login('bad@user.com', 'badpassword');

    // Wait for error alert to animate in
    await loginPage.errorAlert.waitFor({ state: 'visible', timeout: 10_000 });

    // Fill correct credentials (error should animate out, loading should animate in)
    await loginPage.login(VALID_USER, VALID_PASS);

    // Wait for navigation or next state
    await page.waitForTimeout(2_000);

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `insertBefore/React reconciliation errors on Login AnimatePresence:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('should NOT produce errors when rapidly toggling password visibility', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    await loginPage.passwordInput.fill('testpassword');

    // Rapidly toggle password visibility 10 times
    for (let i = 0; i < 10; i++) {
      await loginPage.togglePasswordVisibility();
      await page.waitForTimeout(50);
    }

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors during rapid toggle:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('login background particles should render with stable keys (no duplicate key warnings)', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const loginPage = new LoginPage(page);

    await loginPage.goto();

    // Wait for framer-motion animations to settle
    await page.waitForTimeout(2_000);

    const keyErrors = runtimeErrors.errors.filter(e =>
      /unique.*key|duplicate.*key/i.test(e)
    );
    expect(keyErrors, `Duplicate key warnings in Login Bg: ${keyErrors.join('\n')}`).toHaveLength(0);

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(reconciliationErrors, `Reconciliation errors: ${reconciliationErrors.join('\n')}`).toHaveLength(0);
  });

});

// ─────────────────────────────────────────────────────────────────────
// GROUP 2: AI Insights — Tab AnimatePresence (HIGHEST RISK)
// AIInsights uses: <AnimatePresence mode="wait"><motion.div key={activeTab}>
// This is the canonical React 19 insertBefore trigger pattern.
// ─────────────────────────────────────────────────────────────────────
test.describe('Regression: AIInsights AnimatePresence Tab Switch', () => {

  test.beforeEach(async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(VALID_USER, VALID_PASS);
    await loginPage.waitForDashboard();
  });

  test('should NOT produce insertBefore errors when switching all 10 AI Insight tabs', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);

    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
    await page.goto(`${base}/#/ai-insights`);
    await page.waitForLoadState('domcontentloaded');

    // Wait for initial load
    await page.waitForTimeout(2_000);

    // All 10 tab IDs matching TABS array in AIInsights.jsx
    const tabLabels = [
      'AI Overview',
      'AI Health',
      'Drift Detection',
      'Explainable AI',
      'Dataset Quality',
      'AI Recommendations',
      'Model Comparison',
      'AI Timeline',
      'Semantic Analytics',
      'AI Assistant',
    ];

    for (const label of tabLabels) {
      // Click by button text (first word match for mobile)
      const tabBtn = page.getByRole('button', { name: new RegExp(label.split(' ')[0], 'i') })
        .first();

      if (await tabBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await tabBtn.click();
        // Wait for AnimatePresence exit/enter cycle to complete
        await page.waitForTimeout(300);
      }
    }

    // Check for insertBefore specifically
    const insertBeforeErrors = runtimeErrors.errors.filter(e => /insertBefore/i.test(e));
    expect(
      insertBeforeErrors,
      `insertBefore errors during AI tab switch:\n${insertBeforeErrors.join('\n')}`
    ).toHaveLength(0);

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `React reconciliation errors:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('should NOT produce errors when rapidly switching AI tabs back and forth', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);

    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
    await page.goto(`${base}/#/ai-insights`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1_500);

    // Rapid tab switching — stress test AnimatePresence mode="wait"
    const tabPattern = ['overview', 'health', 'overview', 'drift', 'overview', 'assistant'];
    for (const tab of tabPattern) {
      const btn = page.getByRole('button', { name: new RegExp(tab, 'i') }).first();
      if (await btn.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await btn.click();
        await page.waitForTimeout(150); // Faster than animation — stress test
      }
    }

    await page.waitForTimeout(1_000); // Let animations settle

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Rapid tab switch reconciliation errors:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('should NOT produce errors when the AI Assistant chat messages animate', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);

    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
    await page.goto(`${base}/#/ai-insights`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1_000);

    // Navigate to AI Assistant tab
    const assistantTab = page.getByRole('button', { name: /assistant/i }).first();
    if (await assistantTab.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await assistantTab.click();
      await page.waitForTimeout(500);

      // Try clicking a suggestion (triggers message animation)
      const suggestion = page.getByRole('button', { name: /Pourquoi|Montre|Compare/i }).first();
      if (await suggestion.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await suggestion.click();
        await page.waitForTimeout(3_000); // Wait for API + animation
      }
    }

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors in AI Assistant: ${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

});

// ─────────────────────────────────────────────────────────────────────
// GROUP 3: Evidence Intelligence — Rapid filter changes
// ─────────────────────────────────────────────────────────────────────
test.describe('Regression: Evidence Intelligence DOM Reconciliation', () => {

  test.beforeEach(async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(VALID_USER, VALID_PASS);
    await loginPage.waitForDashboard();
  });

  test('should NOT produce insertBefore errors when evidence cards render/re-render', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Wait for cards to render
    await page.waitForTimeout(1_500);

    const insertBeforeErrors = runtimeErrors.errors.filter(e => /insertBefore/i.test(e));
    expect(
      insertBeforeErrors,
      `insertBefore errors on Evidence page load:\n${insertBeforeErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('should NOT produce errors when EvidenceCard detail expand/collapse triggers', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Find cards that have a Details toggle (ones with comment/recommendation)
    const detailButtons = page.getByRole('button', { name: /details|details|▼/i });
    const count = await detailButtons.count();

    if (count > 0) {
      // Toggle the first 3 detail buttons
      for (let i = 0; i < Math.min(3, count); i++) {
        await detailButtons.nth(i).click().catch(() => {});
        await page.waitForTimeout(200);
        await detailButtons.nth(i).click().catch(() => {});
        await page.waitForTimeout(200);
      }
    }

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors during card toggle:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('should NOT produce errors when Pagination numbers change the DOM rapidly', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Rapid page navigation
    const pageButtons = page.locator(
      'button.flex.h-8.w-8.items-center.justify-center.rounded-lg.border'
    );
    const count = await pageButtons.count();

    if (count > 2) {
      // Click several page buttons rapidly
      for (let i = 0; i < Math.min(count, 4); i++) {
        await pageButtons.nth(i).click().catch(() => {});
        await page.waitForTimeout(300);
      }
    }

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors during pagination:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('should NOT produce errors when Analyze Doc modal opens and closes repeatedly', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Open and close the modal 5 times
    for (let i = 0; i < 5; i++) {
      await evidencePage.analyzeDocButton.click();
      await page.waitForTimeout(400);
      await page.keyboard.press('Escape');
      await page.waitForTimeout(400);
    }

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors during modal open/close:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

});

// ─────────────────────────────────────────────────────────────────────
// GROUP 4: STRESS TEST
// Reproduces React DOM reconciliation issues by performing:
//   - 20 norm filter changes
//   - 20 rule filter changes
//   - Multiple searches
//   - Tab switches
//   - Repeated modal open/close
// ─────────────────────────────────────────────────────────────────────
test.describe('Regression: Evidence Intelligence Stress Test', () => {

  test.beforeEach(async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(VALID_USER, VALID_PASS);
    await loginPage.waitForDashboard();
  });

  test('stress — 20 norm filter changes should not cause React errors', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    const normSelector = evidencePage.normSelector;
    const optionCount = await normSelector.locator('option').count();

    if (optionCount <= 1) {
      // Only "All norms" available — skip norm cycling but still test select changes
      for (let i = 0; i < 20; i++) {
        await normSelector.selectOption({ index: 0 });
        await page.waitForTimeout(100);
      }
    } else {
      // Cycle through available norms 20 times
      for (let i = 0; i < 20; i++) {
        const idx = (i % (optionCount - 1)) + 1; // skip "all" option
        await normSelector.selectOption({ index: idx }).catch(() => {});
        await page.waitForTimeout(200);
      }
    }

    // Final state should be stable
    await page.waitForTimeout(1_000);

    const insertBeforeErrors = runtimeErrors.errors.filter(e => /insertBefore/i.test(e));
    expect(
      insertBeforeErrors,
      `insertBefore after 20 norm changes:\n${insertBeforeErrors.join('\n')}`
    ).toHaveLength(0);

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors after 20 norm changes:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('stress — 20 rule filter changes should not cause React errors', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Wait for rule options to load
    await page.waitForTimeout(2_000);

    const ruleFilter = evidencePage.ruleFilter;
    const optionCount = await ruleFilter.locator('option').count();

    if (optionCount <= 1) {
      // No rule options — still test repeated "All rules" selection
      for (let i = 0; i < 20; i++) {
        await ruleFilter.selectOption({ index: 0 });
        await page.waitForTimeout(100);
      }
    } else {
      for (let i = 0; i < 20; i++) {
        const idx = i % optionCount;
        await ruleFilter.selectOption({ index: idx }).catch(() => {});
        await page.waitForTimeout(200);
      }
    }

    await page.waitForTimeout(1_000);

    const insertBeforeErrors = runtimeErrors.errors.filter(e => /insertBefore/i.test(e));
    expect(
      insertBeforeErrors,
      `insertBefore after 20 rule changes:\n${insertBeforeErrors.join('\n')}`
    ).toHaveLength(0);

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors after 20 rule changes:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('stress — search + norm filter + label filter combined mutations', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();
    await page.waitForTimeout(2_000);

    const searchTerms = ['ISO', 'document', 'compliance', 'security', 'risk'];
    const labelOptions = ['', 'approved', 'rejected'];

    // Interleave searches, label filters, and resets
    for (let i = 0; i < 10; i++) {
      const term = searchTerms[i % searchTerms.length];
      const label = labelOptions[i % labelOptions.length];

      // Search
      await evidencePage.searchInput.fill(term);
      await evidencePage.searchInput.press('Enter');
      await page.waitForTimeout(300);

      // Label filter
      await evidencePage.labelFilter
        .selectOption({ value: label })
        .catch(() => {});
      await page.waitForTimeout(300);

      // Reset every 3 iterations
      if (i % 3 === 2) {
        await evidencePage.resetButton.click();
        await page.waitForTimeout(300);
      }
    }

    await page.waitForTimeout(1_000);

    const insertBeforeErrors = runtimeErrors.errors.filter(e => /insertBefore/i.test(e));
    expect(
      insertBeforeErrors,
      `insertBefore during combined stress test:\n${insertBeforeErrors.join('\n')}`
    ).toHaveLength(0);

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors during combined stress:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('stress — rapid tab switches + modal open/close reproducing reconciliation', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const evidencePage = new EvidencePage(page);

    await evidencePage.goto();
    await evidencePage.waitForLoad();

    // Alternating tab switches and modal open/close
    const tabSequence = ['overview', 'analytics', 'duplicates', 'semantic', 'overview'];

    for (let round = 0; round < 4; round++) {
      // Switch tabs
      for (const tab of tabSequence) {
        const btn = page.getByRole('button', { name: new RegExp(tab, 'i') }).first();
        if (await btn.isVisible({ timeout: 1_000 }).catch(() => false)) {
          await btn.click();
          await page.waitForTimeout(200);
        }
      }

      // Open/close modal twice per round
      for (let m = 0; m < 2; m++) {
        await evidencePage.analyzeDocButton.click().catch(() => {});
        await page.waitForTimeout(300);
        await page.keyboard.press('Escape');
        await page.waitForTimeout(300);
      }
    }

    await page.waitForTimeout(1_000);

    const insertBeforeErrors = runtimeErrors.errors.filter(e => /insertBefore/i.test(e));
    expect(
      insertBeforeErrors,
      `insertBefore in tab+modal stress test:\n${insertBeforeErrors.join('\n')}`
    ).toHaveLength(0);

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors in stress test:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('stress — AIInsights: 20-iteration multi-tab mutation stress test', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);

    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
    await page.goto(`${base}/#/ai-insights`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2_000);

    const tabWords = ['Overview', 'Health', 'Drift', 'Explainable', 'Dataset',
      'Reco', 'Comparison', 'Timeline', 'Semantic', 'Assistant'];

    // Perform 20 rapid tab changes
    for (let i = 0; i < 20; i++) {
      const word = tabWords[i % tabWords.length];
      const btn = page.getByRole('button', { name: new RegExp(word, 'i') }).first();
      if (await btn.isVisible({ timeout: 1_000 }).catch(() => false)) {
        await btn.click();
        await page.waitForTimeout(150); // Intentionally fast — stress test
      }
    }

    await page.waitForTimeout(1_500);

    const insertBeforeErrors = runtimeErrors.errors.filter(e => /insertBefore/i.test(e));
    expect(
      insertBeforeErrors,
      `insertBefore in AIInsights 20-tab stress:\n${insertBeforeErrors.join('\n')}`
    ).toHaveLength(0);

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors in AIInsights stress:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

});

// ─────────────────────────────────────────────────────────────────────
// GROUP 5: Cross-page navigation DOM stability
// ─────────────────────────────────────────────────────────────────────
test.describe('Regression: Cross-page Navigation DOM Stability', () => {

  test.beforeEach(async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(VALID_USER, VALID_PASS);
    await loginPage.waitForDashboard();
  });

  test('should NOT produce insertBefore errors navigating between all major pages', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';

    const routes = [
      '/#/dashboard',
      '/#/documents',
      '/#/evidence-intelligence',
      '/#/ai-insights',
      '/#/document-analysis',
      '/#/compliance-dashboard',
      '/#/dashboard', // Return to dashboard
    ];

    for (const route of routes) {
      await page.goto(`${base}${route}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(800);
    }

    // Wait for final page to settle
    await page.waitForTimeout(1_500);

    const insertBeforeErrors = runtimeErrors.errors.filter(e => /insertBefore/i.test(e));
    expect(
      insertBeforeErrors,
      `insertBefore during page navigation:\n${insertBeforeErrors.join('\n')}`
    ).toHaveLength(0);

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `React errors during page navigation:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

  test('should maintain clean DOM after rapid back-forward navigation', async ({ page }) => {
    const runtimeErrors = captureRuntimeErrors(page);
    const base = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';

    // Navigate forward then back repeatedly
    await page.goto(`${base}/#/evidence-intelligence`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1_000);

    await page.goto(`${base}/#/ai-insights`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1_000);

    await page.goBack();
    await page.waitForTimeout(800);

    await page.goForward();
    await page.waitForTimeout(800);

    await page.goBack();
    await page.waitForTimeout(800);

    const reconciliationErrors = checkForReconciliationErrors(runtimeErrors.errors);
    expect(
      reconciliationErrors,
      `Reconciliation errors after back/forward navigation:\n${reconciliationErrors.join('\n')}`
    ).toHaveLength(0);
  });

});
