import { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

/**
 * Dataset stats hook — used by MLDashboard and TrainingDataset.
 *
 * Classification mode → /dataset-stats/ (RuleTrainingSample counts)
 * Evidence mode       → /evidence/status/ (FAISS / evidence index status)
 */
export default function useDatasetStats(normId, datasetType = 'classification') {
  const [stats, setStats]     = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchStats = useCallback(async () => {
    if (!normId) return;
    setLoading(true);
    try {
      if (datasetType === 'evidence') {
        // Use evidence/status with norm_id for accurate real counts
        const res = await api.get(`/evidence/status/?norm_id=${normId}`);
        const d   = res.data || {};
        // Normalise field names so DatasetStats can render them
        setStats({
          total_samples:      d.total_evidences ?? d.total ?? 0,
          indexed_vectors:    d.indexed_evidences ?? d.indexed_count ?? 0,
          vector_count:       d.indexed_evidences ?? d.indexed_count ?? 0,
          document_count:     d.total_evidences ?? 0,
          indexed_documents:  d.total_evidences ?? 0,
          embedding_dim:      d.vector_dim ?? d.embedding_dim ?? null,
          approved_samples:   d.approved_patterns ?? d.approved ?? 0,
          rejected_samples:   d.rejected_patterns ?? d.rejected ?? 0,
          rules_covered:      d.rules_covered ?? 0,
          total_rules:        d.total_rules ?? 0,
          coverage_pct:       d.coverage_percent ?? 0,
          embedding_model:    d.embedding_model || 'tfidf-fallback',
          train_status:       d.train_status || 'UNKNOWN',
          // Pass through for DatasetStats evidence cards
          _raw: d,
        });
      } else {
        // Classification — use dataset-stats endpoint backed by RuleTrainingSample
        const res = await api.get(`/dataset-stats/?norm_id=${normId}&dataset_type=classification`);
        setStats(res.data);
      }
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [normId, datasetType]);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  return { stats, loading, refetch: fetchStats };
}
