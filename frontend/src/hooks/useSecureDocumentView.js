/**
 * useSecureDocumentView — hook for opening/downloading encrypted/protected documents.
 *
 * Problem
 * -------
 * The secure view/download endpoints (/api/security/documents/<id>/view|download/)
 * require a JWT Bearer token. A plain <a href="..."> opens the URL without the
 * Authorization header — the browser will get a 403.
 *
 * Solution
 * --------
 * 1. Fetch the document bytes via api.js (which injects the Bearer token).
 * 2. Create a temporary Blob URL from the response bytes.
 * 3a. VIEW:     Open the Blob URL in a new tab — the browser renders it inline.
 * 3b. DOWNLOAD: Simulate an <a download="..."> click — browser saves the file.
 * 4. Revoke the Blob URL after a short delay to free memory.
 *
 * Usage
 * -----
 *   const { openDocument, downloadDocument, loading, error } = useSecureDocumentView();
 *
 *   // View inline:
 *   <button onClick={() => openDocument(doc.id)}>Ouvrir</button>
 *
 *   // Download with watermark:
 *   <button onClick={() => downloadDocument(doc.id, doc.file_name)}>Télécharger</button>
 *
 *   // Download without watermark:
 *   <button onClick={() => downloadDocument(doc.id, 'doc.pdf', false)}>Télécharger (brut)</button>
 */
import { useState, useCallback } from 'react';
import api from '../services/api';

export function useSecureDocumentView() {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');

  /**
   * Build the relative API path from a document ID or URL string.
   * api.js baseURL is already '/api', so we strip that prefix when present.
   */
  const _toRelativePath = (source) => {
    if (typeof source === 'number') {
      return `/security/documents/${source}/view/`;
    }
    const str = String(source);
    const apiIdx = str.indexOf('/api/');
    if (apiIdx !== -1) {
      return str.slice(apiIdx + 4);
    }
    return str;
  };

  const _toDownloadPath = (source, watermark = true) => {
    if (typeof source === 'number') {
      const wm = watermark ? '' : '?watermark=false';
      return `/security/documents/${source}/download/${wm}`;
    }
    // If a full URL is given, convert /view/ to /download/
    const str = String(source).replace('/view/', '/download/');
    const apiIdx = str.indexOf('/api/');
    const base = apiIdx !== -1 ? str.slice(apiIdx + 4) : str;
    return watermark ? base : `${base}${base.includes('?') ? '&' : '?'}watermark=false`;
  };

  const _handleError = (err) => {
    const status = err?.response?.status;
    if (status === 403) {
      setError('Accès refusé : vous n\'avez pas la permission d\'accéder à ce document.');
    } else if (status === 404) {
      setError('Document introuvable.');
    } else if (status === 422) {
      setError('Ce document ne possède pas de fichier joint.');
    } else {
      setError(
        err?.response?.data?.error ||
        err?.message ||
        'Une erreur est survenue lors de l\'accès au document.'
      );
    }
  };

  /**
   * Open a document inline in a new browser tab.
   */
  const openDocument = useCallback(async (source) => {
    setLoading(true);
    setError('');
    try {
      const path     = _toRelativePath(source);
      const response = await api.get(path, { responseType: 'blob' });
      const mime     = response.headers['content-type'] || 'application/octet-stream';
      const blob     = new Blob([response.data], { type: mime });
      const blobUrl  = URL.createObjectURL(blob);
      window.open(blobUrl, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch (err) {
      _handleError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Download a document with an optional watermark.
   *
   * Parameters
   * ----------
   * source    : number | string — document ID or secure_download_url
   * filename  : string          — suggested filename for the download dialog
   * watermark : boolean         — apply watermark (default: true)
   */
  const downloadDocument = useCallback(async (source, filename = 'document', watermark = true) => {
    setLoading(true);
    setError('');
    try {
      const path     = _toDownloadPath(source, watermark);
      const response = await api.get(path, { responseType: 'blob' });
      const mime     = response.headers['content-type'] || 'application/octet-stream';
      const blob     = new Blob([response.data], { type: mime });
      const blobUrl  = URL.createObjectURL(blob);

      // Simulate <a download="..."> click
      const a    = document.createElement('a');
      a.href     = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      setTimeout(() => URL.revokeObjectURL(blobUrl), 10_000);
    } catch (err) {
      _handleError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  return { openDocument, downloadDocument, loading, error, setError };
}

export default useSecureDocumentView;
