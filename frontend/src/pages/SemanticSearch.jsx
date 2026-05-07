import React, { useContext, useState } from 'react';
import { Search, ArrowRight, Activity, Layers } from 'lucide-react';
import Layout from '../components/Layout';
import { UserContext } from '../context/UserContext';
import api from '../services/api';

const standards = [
  { value: 'ISO9001', label: 'ISO 9001' },
  { value: 'ISO27001', label: 'ISO 27001' },
];

export default function SemanticSearch() {
  const { user } = useContext(UserContext);
  const [query, setQuery] = useState('');
  const [standard, setStandard] = useState('ISO9001');
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async (event) => {
    event.preventDefault();
    setError(null);
    setResults(null);

    if (!query.trim()) {
      setError('Veuillez saisir une requête de recherche.');
      return;
    }

    setLoading(true);

    try {
      const response = await api.post('/semantic-search/', {
        query,
        standard,
        top_k: topK,
      });
      setResults(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Impossible de lancer la recherche.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="space-y-6 px-4 pb-8 pt-6 sm:px-6 lg:px-8">
        <header className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 bg-gradient-to-r from-slate-950 via-purple-950 to-blue-900 px-6 py-7 text-white sm:px-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.35em] text-slate-300/75">Recherche sémantique</p>
                <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Recherche hybride ISO</h1>
                <p className="mt-3 text-sm leading-7 text-slate-200">
                  Recherchez des documents par similarité sémantique, concordance de règles et preuves locales.
                </p>
              </div>
              <button
                onClick={handleSearch}
                disabled={loading}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-6 py-3 font-semibold text-purple-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Search size={20} />
                {loading ? 'Recherche en cours...' : 'Lancer la recherche'}
              </button>
            </div>
          </div>

          <div className="grid gap-4 px-6 py-6 md:grid-cols-3 md:px-8">
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <p className="text-sm font-medium text-slate-500">Standard sélectionné</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{standards.find((item) => item.value === standard)?.label}</p>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <p className="text-sm font-medium text-slate-500">Nombre de résultats</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{results?.results?.length ?? 0}</p>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <p className="text-sm font-medium text-slate-500">Documents disponibles</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{results?.total_documents ?? '—'}</p>
            </div>
          </div>
        </header>

        <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
          <form className="space-y-6" onSubmit={handleSearch}>
            {error && <div className="rounded-3xl bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}

            <div className="grid gap-6 lg:grid-cols-3">
              <label className="space-y-2 text-sm text-slate-700">
                Requête
                <input
                  type="text"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  className="w-full rounded-3xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                  placeholder="Entrez le texte à rechercher..."
                />
              </label>

              <label className="space-y-2 text-sm text-slate-700">
                Norme
                <select
                  value={standard}
                  onChange={(event) => setStandard(event.target.value)}
                  className="w-full rounded-3xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                >
                  {standards.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-2 text-sm text-slate-700">
                Résultats
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={topK}
                  onChange={(event) => setTopK(Number(event.target.value))}
                  className="w-full rounded-3xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                />
              </label>
            </div>
          </form>
        </div>

        {results && (
          <section className="space-y-6">
            <div className="rounded-[2rem] border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-100 px-6 py-5 sm:px-8">
                <h2 className="text-lg font-semibold text-slate-900">Résultats de recherche hybride</h2>
                <p className="mt-1 text-sm text-slate-500">Classement par score hybride sémantique, BM25 et couverture de règles.</p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50/80">
                      <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Document</th>
                      <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Hybrid</th>
                      <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Sémantique</th>
                      <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">BM25</th>
                      <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Règles</th>
                      <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Statut</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {results.results.map((result) => (
                      <tr key={result.document_id} className="hover:bg-slate-50">
                        <td className="px-6 py-5">
                          <div className="font-semibold text-slate-900">{result.document_name || `Document ${result.document_id}`}</div>
                          <div className="text-xs text-slate-500">ID: {result.document_id}</div>
                        </td>
                        <td className="px-6 py-5 text-center font-semibold text-slate-900">{(result.hybrid_score * 100).toFixed(1)}%</td>
                        <td className="px-6 py-5 text-center text-slate-700">{(result.semantic_score * 100).toFixed(1)}%</td>
                        <td className="px-6 py-5 text-center text-slate-700">{(result.bm25_score * 100).toFixed(1)}%</td>
                        <td className="px-6 py-5 text-center text-slate-700">{(result.keyword_score * 100).toFixed(1)}%</td>
                        <td className="px-6 py-5 text-center text-slate-900 uppercase">{result.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {results.results.map((item) => (
              <div key={`explain-${item.document_id}`} className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h3 className="text-xl font-semibold text-slate-900">{item.document_name || `Document ${item.document_id}`}</h3>
                    <p className="text-sm text-slate-500">Statut: {item.status} · Norme: {item.standard}</p>
                  </div>
                  <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700">
                    <Activity size={16} />
                    Score hybride { (item.hybrid_score * 100).toFixed(1) }%
                  </div>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-3">
                  <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Sémantique</p>
                    <p className="mt-3 text-2xl font-semibold text-slate-900">{(item.semantic_score * 100).toFixed(1)}%</p>
                  </div>
                  <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">BM25</p>
                    <p className="mt-3 text-2xl font-semibold text-slate-900">{(item.bm25_score * 100).toFixed(1)}%</p>
                  </div>
                  <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Couverture règles</p>
                    <p className="mt-3 text-2xl font-semibold text-slate-900">{(item.keyword_score * 100).toFixed(1)}%</p>
                  </div>
                </div>

                <div className="mt-6 space-y-4">
                  <h4 className="text-lg font-semibold text-slate-900">Preuves de règles</h4>
                  {item.evidence.length === 0 ? (
                    <p className="text-sm text-slate-500">Aucune preuve automatique n'a été trouvée pour ce document.</p>
                  ) : (
                    <div className="grid gap-4 md:grid-cols-2">
                      {item.evidence.map((evidence, index) => (
                        <div key={index} className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                          <p className="text-sm font-semibold text-slate-900">{evidence.rule}</p>
                          <p className="text-xs text-slate-500">Mot-clé : {evidence.keyword}</p>
                          <p className="mt-3 text-sm text-slate-700">{evidence.snippet}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </section>
        )}
      </div>
    </Layout>
  );
}
