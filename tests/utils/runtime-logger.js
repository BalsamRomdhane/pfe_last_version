// =====================================================================
// tests/utils/runtime-logger.js
//
// Centralised collector for:
//   • page runtime errors  (page.on('pageerror'))
//   • console messages     (page.on('console'))
//   • failed network requests (page.on('requestfailed'))
//
// Every call to createMonitor() returns a Monitor object that:
//   1. Registers all three listeners on the given page.
//   2. Exposes typed arrays: runtimeErrors, consoleErrors,
//      consoleWarnings, allLogs, failedRequests.
//   3. Exposes assertClean() — throws immediately if any critical
//      pattern is found (use anywhere mid-test for fail-fast).
//   4. Exposes flush(testTitle) — writes everything to
//      playwright-report/runtime-errors.log (appended, CI-safe).
//
// CRITICAL PATTERNS — test fails on any match:
//   insertBefore, NotFoundError, removeChild, appendChild (DOM ops)
//   React, Hydration                                       (React)
//   Cannot read properties                                 (null deref)
//   Maximum update depth exceeded                          (inf loop)
//   Too many re-renders                                    (inf loop)
//   Each child in a list should have a unique key          (key dup)
//   Encountered two children with the same key             (key dup)
// =====================================================================

'use strict';

const fs   = require('fs');
const path = require('path');

// ── Patterns that must NEVER appear ─────────────────────────────────
const CRITICAL_PATTERNS = [
  // DOM reconciliation
  { re: /insertBefore/i,   label: 'DOM:insertBefore'   },
  { re: /NotFoundError/i,  label: 'DOM:NotFoundError'  },
  { re: /removeChild/i,    label: 'DOM:removeChild'    },
  { re: /appendChild/i,    label: 'DOM:appendChild'    },
  // React internals
  { re: /Minified React error/i,                   label: 'React:MinifiedError'       },
  { re: /React error #\d+/i,                       label: 'React:Error'               },
  { re: /Hydration failed/i,                       label: 'React:HydrationFailed'     },
  { re: /hydration/i,                              label: 'React:Hydration'           },
  { re: /Maximum update depth exceeded/i,          label: 'React:MaxUpdateDepth'      },
  { re: /Too many re-renders/i,                    label: 'React:TooManyRerenders'    },
  { re: /Cannot update a component.*while rendering/i, label: 'React:StateWhileRender' },
  { re: /Invariant Violation/i,                    label: 'React:InvariantViolation'  },
  // JS runtime
  { re: /Cannot read propert(?:y|ies)/i,           label: 'JS:NullDeref'             },
  { re: /is not a function/i,                      label: 'JS:NotAFunction'           },
  { re: /is not defined/i,                         label: 'JS:NotDefined'             },
  { re: /Unexpected token/i,                       label: 'JS:SyntaxError'            },
  // React key duplicates (warnings promoted to errors here)
  { re: /Each child in a list should have a unique.*key/i, label: 'React:DuplicateKey' },
  { re: /Encountered two children with the same key/i,     label: 'React:SameKey'      },
];

// ── Noise that must be ignored (CRA dev-server chatter, etc.) ────────
const IGNORED_PATTERNS = [
  /favicon/i,
  /hot-update/i,
  /webpack/i,
  /sockjs/i,
  /\[WDS\]/i,
  /\[HMR\]/i,
  /Download the React DevTools/i,
  /Refused to load.*Content Security Policy/i,
  /net::ERR_ABORTED/i,                 // user navigating away mid-request
  /failed to fetch/i,                  // expected when backend is down in unit mode
  /NetworkError when attempting to fetch/i,
];

// ── Log file path ────────────────────────────────────────────────────
const LOG_DIR  = path.resolve(__dirname, '..', '..', 'playwright-report');
const LOG_FILE = path.join(LOG_DIR, 'runtime-errors.log');

function ensureLogDir() {
  if (!fs.existsSync(LOG_DIR)) {
    fs.mkdirSync(LOG_DIR, { recursive: true });
  }
}

/**
 * Format a log line with ISO timestamp.
 */
function stamp(tag, text) {
  return `[${new Date().toISOString()}] [${tag}] ${text}`;
}

// ─────────────────────────────────────────────────────────────────────
// createMonitor(page)
//
// Call once per test, right after you have the page object.
// Returns a Monitor that collects everything until flush() is called.
// ─────────────────────────────────────────────────────────────────────

/**
 * @typedef {Object} Monitor
 * @property {string[]} runtimeErrors   - Errors from page.on('pageerror')
 * @property {string[]} consoleErrors   - console.error messages
 * @property {string[]} consoleWarnings - console.warn messages
 * @property {string[]} allLogs         - Everything combined
 * @property {FailedRequest[]} failedRequests
 * @property {function(): void} assertClean   - Throws if critical pattern found
 * @property {function(string): void} flush   - Writes to log file
 * @property {function(): CriticalMatch[]} criticalMatches - Returns matches
 */

/**
 * @typedef {Object} FailedRequest
 * @property {string} url
 * @property {string} failure
 * @property {string} method
 */

/**
 * @typedef {Object} CriticalMatch
 * @property {string} label
 * @property {string} message
 */

/**
 * Creates and attaches a page monitor.
 * @param {import('@playwright/test').Page} page
 * @returns {Monitor}
 */
function createMonitor(page) {
  const runtimeErrors   = [];
  const consoleErrors   = [];
  const consoleWarnings = [];
  const allLogs         = [];
  const failedRequests  = [];

  // ── page.on('pageerror') ──────────────────────────────────────────
  page.on('pageerror', (error) => {
    const msg = `${error.message}${error.stack ? '\n' + error.stack : ''}`;
    const line = stamp('pageerror', msg);
    runtimeErrors.push(msg);
    allLogs.push(line);
  });

  // ── page.on('console') ────────────────────────────────────────────
  page.on('console', (msg) => {
    const text = msg.text();
    const type = msg.type();
    const line = stamp(`console.${type}`, text);

    allLogs.push(line);

    if (type === 'error') {
      consoleErrors.push(text);
    } else if (type === 'warning' || type === 'warn') {
      consoleWarnings.push(text);
    }
  });

  // ── page.on('requestfailed') ──────────────────────────────────────
  page.on('requestfailed', (request) => {
    const url     = request.url();
    const failure = request.failure()?.errorText ?? 'unknown';
    const method  = request.method();

    // Ignore expected dev-server noise
    if (IGNORED_PATTERNS.some((p) => p.test(url))) return;

    const entry = { url, failure, method };
    failedRequests.push(entry);
    allLogs.push(stamp('requestfailed', `${method} ${url} — ${failure}`));
  });

  // ── criticalMatches() ────────────────────────────────────────────
  function criticalMatches() {
    const sources = [...runtimeErrors, ...consoleErrors, ...consoleWarnings];
    const matches = [];

    for (const msg of sources) {
      // Skip if it matches an ignored pattern
      if (IGNORED_PATTERNS.some((p) => p.test(msg))) continue;

      for (const { re, label } of CRITICAL_PATTERNS) {
        if (re.test(msg)) {
          matches.push({ label, message: msg });
          break; // one label per message is enough
        }
      }
    }
    return matches;
  }

  // ── assertClean() ────────────────────────────────────────────────
  function assertClean(context = '') {
    const matches = criticalMatches();
    if (matches.length === 0) return;

    const report = matches
      .map((m) => `  [${m.label}] ${m.message.substring(0, 300)}`)
      .join('\n');

    throw new Error(
      `${matches.length} critical runtime error(s)${context ? ` in ${context}` : ''}:\n${report}`
    );
  }

  // ── flush(testTitle) ─────────────────────────────────────────────
  function flush(testTitle = 'unknown test') {
    if (allLogs.length === 0 && failedRequests.length === 0) return;

    ensureLogDir();

    const separator = `\n${'─'.repeat(72)}\n`;
    const header = `${separator}TEST: ${testTitle}\nTIME: ${new Date().toISOString()}\n${separator}`;

    let content = header;

    if (runtimeErrors.length > 0) {
      content += `\n── PAGE ERRORS (${runtimeErrors.length}) ──\n`;
      content += runtimeErrors.map((e) => `  ${e}`).join('\n') + '\n';
    }

    if (consoleErrors.length > 0) {
      content += `\n── CONSOLE ERRORS (${consoleErrors.length}) ──\n`;
      content += consoleErrors.map((e) => `  ${e}`).join('\n') + '\n';
    }

    if (consoleWarnings.length > 0) {
      content += `\n── CONSOLE WARNINGS (${consoleWarnings.length}) ──\n`;
      content += consoleWarnings.map((w) => `  ${w}`).join('\n') + '\n';
    }

    if (failedRequests.length > 0) {
      content += `\n── FAILED REQUESTS (${failedRequests.length}) ──\n`;
      content += failedRequests
        .map((r) => `  [${r.method}] ${r.url} — ${r.failure}`)
        .join('\n') + '\n';
    }

    const criticals = criticalMatches();
    if (criticals.length > 0) {
      content += `\n── CRITICAL MATCHES (${criticals.length}) ──\n`;
      content += criticals.map((m) => `  [${m.label}] ${m.message.substring(0, 400)}`).join('\n') + '\n';
    }

    fs.appendFileSync(LOG_FILE, content, 'utf8');
  }

  return {
    runtimeErrors,
    consoleErrors,
    consoleWarnings,
    allLogs,
    failedRequests,
    criticalMatches,
    assertClean,
    flush,
  };
}

module.exports = { createMonitor, CRITICAL_PATTERNS, IGNORED_PATTERNS, LOG_FILE };
