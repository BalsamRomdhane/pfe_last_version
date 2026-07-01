// =====================================================================
// playwright.config.js — Enterprise ISO Compliance Platform
// E2E testing configuration for React 19 + Django REST Framework
// =====================================================================

const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  // Root test directory
  testDir: './tests',

  // Default timeout for all tests.
  // Stress / regression tests override this via test.setTimeout().
  timeout: 60_000,

  // Expect timeout for individual assertions
  expect: {
    timeout: 10_000,
  },

  // Run tests in parallel files
  fullyParallel: false,

  // Fail the build on CI if test.only is left in source
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Number of parallel workers
  workers: process.env.CI ? 1 : 2,

  // Global reporter configuration
  reporter: [
    // HTML report — open manually after run
    ['html', {
      outputFolder: 'playwright-report',
      open: 'never',
    }],
    // Human-readable list in terminal
    ['list'],
    // Machine-readable JSON for dashboards
    ['json', { outputFile: 'playwright-report/results.json' }],
    // JUnit XML for Jenkins archiving
    ['junit', { outputFile: 'playwright-report/junit-results.xml' }],
    // Custom runtime-error log — written by the test suite itself via
    // the RuntimeLogger helper (see tests/utils/runtime-logger.js)
  ],

  // Shared settings for all projects
  use: {
    // Base URL — frontend runs on http://localhost:3000 with HashRouter
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',

    // Always collect trace (regression tests need it for diagnosis)
    trace: 'on-first-retry',

    // Screenshot on every failure
    screenshot: 'only-on-failure',

    // Video on first retry so CI captures replay of flaky failures
    video: 'on-first-retry',

    // Viewport
    viewport: { width: 1280, height: 800 },

    // Navigation timeout
    navigationTimeout: 30_000,

    // Action timeout
    actionTimeout: 15_000,

    // Ignore HTTPS errors (dev env)
    ignoreHTTPSErrors: true,

    // Locale
    locale: 'fr-FR',

    // Timezone
    timezoneId: 'Europe/Paris',
  },

  // Test projects — Chromium only as specified
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Output directory for test artifacts (screenshots, videos, traces)
  outputDir: './playwright-results',
});
