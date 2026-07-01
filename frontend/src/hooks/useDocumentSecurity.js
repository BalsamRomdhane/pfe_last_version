/**
 * useDocumentSecurity — fetches the security analysis for a document.
 *
 * Strategy
 * --------
 * 1. GET /security/documents/<id>/analysis/
 *    - Success → done.
 *    - 404     → analysis record doesn't exist yet. Automatically POST to
 *                /reanalyze/ to create it (once), then use the response.
 *                This avoids repeated 404 polling spam in the console.
 *    - Other error → surface silently (non-blocking UI).
 *
 * Usage
 * -----
 *   const { analysis, loading, error, refetch } = useDocumentSecurity(docId);
 *
 * Parameters
 * ----------
 *   docId       : number | null — document PK; null = hook is idle
 *   autoFetch   : bool — start fetch immediately (default: true)
 *   maxAttempts : number — kept for API compat; no longer used for polling
 *   interval    : number — kept for API compat; no longer used for polling
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import api from '../services/api';

export function useDocumentSecurity({
  docId       = null,
  autoFetch   = true,
  maxAttempts = 10, // eslint-disable-line no-unused-vars
  interval    = 3000, // eslint-disable-line no-unused-vars
} = {}) {
  const [analysis,  setAnalysis]  = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState('');
  const reanalyzedRef = useRef(false); // prevent duplicate reanalyze calls

  const fetchAnalysis = useCallback(async () => {
    if (!docId) return;

    setLoading(true);
    setError('');
    reanalyzedRef.current = false;

    try {
      // Step 1: try to load an existing analysis
      const res = await api.get(`/security/documents/${docId}/analysis/`);
      setAnalysis(res.data);
    } catch (err) {
      const httpStatus = err?.response?.status;

      if (httpStatus === 404 && !reanalyzedRef.current) {
        // Step 2: no record exists — trigger creation via reanalyze
        reanalyzedRef.current = true;
        try {
          const reRes = await api.post(`/security/documents/${docId}/reanalyze/`, { force: false });
          setAnalysis(reRes.data);
        } catch (reErr) {
          // reanalyze failed (e.g. 403, 500) — stay silent, panel shows pending state
          const reStatus = reErr?.response?.status;
          if (reStatus && reStatus !== 403 && reStatus !== 404) {
            setError(''); // non-blocking: don't disrupt the page
          }
        }
      }
      // 403 or other errors: stay silent — panel handles the no-analysis state
    } finally {
      setLoading(false);
    }
  }, [docId]);

  useEffect(() => {
    if (autoFetch && docId) {
      fetchAnalysis();
    }
  }, [docId, autoFetch, fetchAnalysis]);

  const refetch = useCallback(() => {
    fetchAnalysis();
  }, [fetchAnalysis]);

  return { analysis, loading, error, refetch };
}

export default useDocumentSecurity;
