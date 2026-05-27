/**
 * Utility functions for ML Dashboard
 * Ensures NO NaN, undefined, Infinity, or null values are displayed
 * ALWAYS returns safe, real values
 */

/**
 * Safe percentage calculation - never divide by zero
 * @param {number} value - Numerator
 * @param {number} total - Denominator
 * @returns {number} Percentage (0-100) or 0 if total is 0 or undefined
 */
export const safePercent = (value, total) => {
  if (!total || total === 0 || isNaN(total)) return 0;
  if (value === undefined || value === null || isNaN(value)) return 0;
  const percent = (value / total) * 100;
  if (!isFinite(percent) || isNaN(percent)) return 0;
  return Math.round(percent * 100) / 100; // Round to 2 decimal places
};

/**
 * Format a percentage value safely
 * @param {number} percent - Percentage value
 * @param {boolean} showSign - Add % sign
 * @returns {string} Formatted percentage or "0%"
 */
export const formatPercent = (percent, showSign = true) => {
  if (percent === undefined || percent === null || isNaN(percent) || !isFinite(percent)) {
    return showSign ? "0%" : "0";
  }

  let value = Number(percent);
  if (Math.abs(value) <= 1) {
    value = value * 100;
  }

  value = Math.round(value * 100) / 100;
  return showSign ? `${value}%` : `${value}`;
};

/**
 * Safe count display
 * @param {number} count - Count value
 * @param {string} placeholder - Default display if count is invalid
 * @returns {string|number} Safe count or placeholder
 */
export const safeCount = (count, placeholder = "0") => {
  if (count === undefined || count === null || isNaN(count)) return placeholder;
  if (!isFinite(count)) return placeholder;
  return count;
};

/**
 * Check if model is adequately trained
 * A model is considered trained if it has been saved to disk (exists=true)
 * OR if it has accuracy metrics from a training run.
 * @param {object} model - Model object
 * @returns {boolean} True if model has been trained
 */
export const isModelTrained = (model) => {
  if (!model) return false;
  // Model file exists on disk — it was trained
  if (model.exists === true) return true;
  // Legacy: model has accuracy metrics
  if (model.accuracy !== undefined && model.accuracy > 0) return true;
  return false;
};

/**
 * Get best model from list
 * Prefers models with highest accuracy; falls back to any existing model.
 * @param {array} models - Array of model objects
 * @returns {object|null} Best model or null if none qualify
 */
export const getBestModel = (models) => {
  if (!models || !Array.isArray(models) || models.length === 0) {
    return null;
  }

  // Filter to only trained/existing models
  const trainedModels = models.filter((m) => isModelTrained(m));

  if (trainedModels.length === 0) return null;

  // Prefer models with accuracy metrics; sort by accuracy descending
  const withAccuracy = trainedModels.filter((m) => m.accuracy !== undefined && m.accuracy > 0);
  if (withAccuracy.length > 0) {
    withAccuracy.sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0));
    return withAccuracy[0];
  }

  // No accuracy data — return first existing model (prefer RandomForest as default)
  const preferred = trainedModels.find((m) => m.name === 'RandomForest' || m.algorithm === 'RandomForest');
  return preferred || trainedModels[0];
};

/**
 * Get training readiness info
 * @param {number} totalSamples - Total training samples
 * @returns {object} Status and message
 */
export const getDatasetReadiness = (totalSamples) => {
  totalSamples = safeCount(totalSamples, 0);
  
  if (totalSamples < 1) {
    return {
      status: "insufficient",
      message: "No validated documents yet",
      icon: "AlertCircle",
      canTrain: false,
    };
  }
  
  if (totalSamples < 10) {
    return {
      status: "insufficient",
      message: `Need at least 10 samples (${totalSamples}/10)`,
      icon: "AlertCircle",
      canTrain: false,
    };
  }
  
  if (totalSamples < 20) {
    return {
      status: "warning",
      message: `${totalSamples} samples (20+ recommended)`,
      icon: "AlertCircle",
      canTrain: true,
    };
  }
  
  return {
    status: "sufficient",
    message: `${totalSamples} samples ready`,
    icon: "CheckCircle2",
    canTrain: true,
  };
};

/**
 * Get model status display
 * @param {object} model - Model object
 * @returns {object} Status and display info
 */
export const getModelStatus = (model) => {
  if (!model) {
    return { status: "NOT_TRAINED", label: "Not Trained", color: "bg-slate-100 text-slate-600" };
  }

  if (!isModelTrained(model)) {
    return { status: "NOT_TRAINED", label: "Not Trained", color: "bg-slate-100 text-slate-600" };
  }

  // No accuracy data but model exists
  if (model.accuracy === undefined || model.accuracy === null) {
    return { status: "TRAINED", label: "Trained", color: "bg-sky-100 text-sky-700" };
  }

  if (model.accuracy >= 0.9) {
    return { status: "EXCELLENT", label: "Excellent", color: "bg-emerald-100 text-emerald-700" };
  }
  if (model.accuracy >= 0.75) {
    return { status: "GOOD", label: "Good", color: "bg-blue-100 text-blue-700" };
  }
  if (model.accuracy >= 0.6) {
    return { status: "ADEQUATE", label: "Adequate", color: "bg-amber-100 text-amber-700" };
  }
  return { status: "POOR", label: "Poor", color: "bg-red-100 text-red-700" };
};

/**
 * Check if prediction is available
 * @param {object} bestModel - Best model object
 * @returns {boolean} True if model is ready for prediction
 */
export const canPredict = (bestModel) => {
  return isModelTrained(bestModel);
};

/**
 * Safe division with fallback
 * @param {number} a - Numerator
 * @param {number} b - Denominator
 * @param {*} fallback - Value if division not possible
 * @returns {*} Result or fallback
 */
export const safeDivide = (a, b, fallback = 0) => {
  if (!b || b === 0 || isNaN(b) || !isFinite(b)) return fallback;
  if (a === undefined || a === null || isNaN(a)) return fallback;
  const result = a / b;
  if (!isFinite(result) || isNaN(result)) return fallback;
  return result;
};
