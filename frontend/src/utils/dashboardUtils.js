/**
 * dashboardUtils.js
 * -----------------
 * Utility functions for ML Dashboard.
 *
 * Rules enforced here:
 *  - No fallbacks that produce fake values (no `accuracy || 0`, etc.)
 *  - A model is "trained" only when it has REAL metrics (accuracy > 0 from
 *    an actual training run).  A file existing on disk without metrics is
 *    NOT considered trained — it may be a stale artifact.
 *  - Best model selection uses the priority order specified in the brief:
 *    F1 → Accuracy → Recall → Precision → Training Time.
 *    Ties produce "Tie" — RandomForest is never selected as a default.
 *  - Status labels are derived from real metric values only.
 *    "Excellent", "Best Model", "Trained" are NEVER shown without evidence.
 */

// ── Safe numeric helpers ──────────────────────────────────────────────────────

/**
 * Safe percentage calculation — never divides by zero.
 * Returns a numeric percentage (0–100) or 0.
 */
export const safePercent = (value, total) => {
  if (!total || total === 0 || Number.isNaN(total)) return 0;
  if (value === undefined || value === null || Number.isNaN(value)) return 0;
  const percent = (value / total) * 100;
  if (!Number.isFinite(percent) || Number.isNaN(percent)) return 0;
  return Math.round(percent * 100) / 100;
};

/**
 * Format a metric value (0–1 float or 0–100) for display.
 *
 * Returns "—" instead of "0%" when the value is absent/null so the UI
 * never shows a fake zero.
 *
 * @param {number|null|undefined} percent - Metric value
 * @param {boolean} showSign - Whether to append %
 * @returns {string} "—" | "X%" | "X"
 */
export const formatPercent = (percent, showSign = true) => {
  // Explicitly absent or invalid → show dash, not a fake zero
  if (percent === undefined || percent === null || Number.isNaN(percent) || !Number.isFinite(percent)) {
    return '—';
  }

  let value = Number(percent);

  // Normalise: if value is in [0, 1] range treat as fraction → multiply
  if (Math.abs(value) <= 1) {
    value = value * 100;
  }

  value = Math.round(value * 100) / 100;
  return showSign ? `${value}%` : `${value}`;
};

/**
 * Safe count display.
 * Returns placeholder when count is invalid.
 */
export const safeCount = (count, placeholder = '0') => {
  if (count === undefined || count === null || Number.isNaN(count)) return placeholder;
  if (!Number.isFinite(count)) return placeholder;
  return count;
};

/**
 * Safe division with fallback.
 */
export const safeDivide = (a, b, fallback = 0) => {
  if (!b || b === 0 || Number.isNaN(b) || !Number.isFinite(b)) return fallback;
  if (a === undefined || a === null || Number.isNaN(a)) return fallback;
  const result = a / b;
  if (!Number.isFinite(result) || Number.isNaN(result)) return fallback;
  return result;
};

// ── Model quality helpers ─────────────────────────────────────────────────────

/**
 * A model is "trained" only when:
 *   - it has a real accuracy value > 0 AND
 *   - it does NOT carry an error flag.
 *
 * A model whose accuracy is 0 (failed training) or whose accuracy is
 * undefined (no training run) is NOT trained.
 */
export const isModelTrained = (model) => {
  if (!model) return false;
  // If training produced an error, the model is not usable
  if (model.error) return false;
  // Must have a positive accuracy from a real run
  if (model.accuracy !== undefined && model.accuracy !== null && model.accuracy > 0) return true;
  return false;
};

/**
 * Select the best model using the priority order:
 *   1. F1 Score (primary)
 *   2. Accuracy
 *   3. Recall
 *   4. Precision
 *   5. (lower) Training time — not available in current payload, skip
 *
 * Returns null when no model qualifies.
 * Returns a model object with `is_best: true` injected.
 * When there is a tie, returns an object with `is_tie: true`.
 *
 * NOTE: RandomForest is NEVER selected as a default tiebreaker.
 */
export const getBestModel = (models) => {
  if (!models || !Array.isArray(models) || models.length === 0) return null;

  // Only consider models that were actually trained successfully
  const trained = models.filter(isModelTrained);
  if (trained.length === 0) return null;

  // Sort by priority: F1 desc → Accuracy desc → Recall desc → Precision desc
  const sorted = [...trained].sort((a, b) => {
    const f1Diff = (b.f1_score ?? 0) - (a.f1_score ?? 0);
    if (Math.abs(f1Diff) > 0.0001) return f1Diff;

    const accDiff = (b.accuracy ?? 0) - (a.accuracy ?? 0);
    if (Math.abs(accDiff) > 0.0001) return accDiff;

    const recDiff = (b.recall ?? 0) - (a.recall ?? 0);
    if (Math.abs(recDiff) > 0.0001) return recDiff;

    const precDiff = (b.precision ?? 0) - (a.precision ?? 0);
    return precDiff;
  });

  const top = sorted[0];

  // Check for a tie: are there other models with identical F1 AND accuracy?
  const ties = sorted.filter(
    (m) =>
      Math.abs((m.f1_score ?? 0) - (top.f1_score ?? 0)) <= 0.0001 &&
      Math.abs((m.accuracy ?? 0) - (top.accuracy ?? 0)) <= 0.0001 &&
      m.name !== top.name,
  );

  if (ties.length > 0) {
    // True tie — do not pick one arbitrarily
    return { ...top, is_best: true, is_tie: true, tied_with: ties.map((m) => m.name) };
  }

  return { ...top, is_best: true, is_tie: false };
};

/**
 * Compute status label from real metric values.
 *
 * Status rules:
 *   error present           → FAILED
 *   no accuracy (null/undef)→ NOT_TRAINED
 *   accuracy = 0            → FAILED  (training ran but produced nothing useful)
 *   accuracy > 0            → label based on value thresholds
 *
 * "Excellent" / "Good" / etc. labels are DERIVED from actual accuracy —
 * they are never applied as defaults.
 */
export const getModelStatus = (model) => {
  if (!model) {
    return { status: 'NOT_TRAINED', label: 'Not Trained', color: 'bg-slate-100 text-slate-600' };
  }

  // Training produced an error
  if (model.error) {
    return { status: 'FAILED', label: 'Failed', color: 'bg-red-100 text-red-700' };
  }

  // No metrics at all
  if (model.accuracy === undefined || model.accuracy === null) {
    return { status: 'NOT_TRAINED', label: 'Not Trained', color: 'bg-slate-100 text-slate-600' };
  }

  // Accuracy is exactly 0 → training ran but produced no useful result
  if (model.accuracy === 0) {
    return { status: 'FAILED', label: 'Failed (0%)', color: 'bg-red-100 text-red-700' };
  }

  // Real accuracy-based labels
  if (model.accuracy >= 0.9) {
    return { status: 'EXCELLENT', label: 'Excellent', color: 'bg-emerald-100 text-emerald-700' };
  }
  if (model.accuracy >= 0.75) {
    return { status: 'GOOD', label: 'Good', color: 'bg-blue-100 text-blue-700' };
  }
  if (model.accuracy >= 0.6) {
    return { status: 'ADEQUATE', label: 'Adequate', color: 'bg-amber-100 text-amber-700' };
  }
  return { status: 'POOR', label: 'Poor', color: 'bg-red-100 text-red-700' };
};

/**
 * Dataset readiness check.
 */
export const getDatasetReadiness = (totalSamples) => {
  totalSamples = safeCount(totalSamples, 0);

  if (totalSamples < 1) {
    return { status: 'insufficient', message: 'No validated documents yet', icon: 'AlertCircle', canTrain: false };
  }
  if (totalSamples < 10) {
    return { status: 'insufficient', message: `Need at least 10 samples (${totalSamples}/10)`, icon: 'AlertCircle', canTrain: false };
  }
  if (totalSamples < 20) {
    return { status: 'warning', message: `${totalSamples} samples (20+ recommended)`, icon: 'AlertCircle', canTrain: true };
  }
  return { status: 'sufficient', message: `${totalSamples} samples ready`, icon: 'CheckCircle2', canTrain: true };
};

/**
 * Prediction readiness.
 */
export const canPredict = (bestModel) => isModelTrained(bestModel);
