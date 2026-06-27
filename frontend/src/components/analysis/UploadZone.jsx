import React, { useCallback, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, X, CheckCircle2 } from 'lucide-react';

const ACCEPTED = ['.pdf', '.doc', '.docx'];
const MAX_MB = 50;

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function extColor(name) {
  const ext = name.split('.').pop().toLowerCase();
  if (ext === 'pdf') return 'bg-red-100 text-red-700';
  if (ext === 'docx' || ext === 'doc') return 'bg-blue-100 text-blue-700';
  return 'bg-slate-100 text-slate-700';
}

export default function UploadZone({ file, onFile, onRemove }) {
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef();

  const validate = useCallback((f) => {
    if (!f) return 'No file selected.';
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!ACCEPTED.includes(ext)) return `Unsupported format. Use PDF or DOCX.`;
    if (f.size > MAX_MB * 1024 * 1024) return `File too large (max ${MAX_MB} MB).`;
    return null;
  }, []);

  const handle = useCallback((f) => {
    const err = validate(f);
    if (err) { setError(err); return; }
    setError('');
    onFile(f);
  }, [validate, onFile]);

  const onDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    handle(e.dataTransfer.files?.[0]);
  };

  const onInputChange = (e) => handle(e.target.files?.[0]);

  if (file) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4"
      >
        <div className="flex items-center gap-4">
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${extColor(file.name)}`}>
            {file.name.split('.').pop().toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-slate-900">{file.name}</p>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-xs text-slate-500">{formatBytes(file.size)}</span>
              <span className="h-1 w-1 rounded-full bg-slate-300" />
              <span className="flex items-center gap-1 text-xs font-medium text-emerald-600">
                <CheckCircle2 size={12} /> Ready to analyze
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onRemove}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-200 hover:text-slate-700"
            aria-label="Remove file"
          >
            <X size={16} />
          </button>
        </div>
      </motion.div>
    );
  }

  return (
    <div>
      <motion.div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        animate={drag ? { scale: 1.01 } : { scale: 1 }}
        className={`relative cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed p-8 text-center transition-all duration-200 ${
          drag
            ? 'border-sky-400 bg-sky-50'
            : 'border-slate-200 bg-slate-50/50 hover:border-sky-300 hover:bg-sky-50/40'
        }`}
      >
        {/* Animated border gradient when dragging */}
        <AnimatePresence>
          {drag && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="pointer-events-none absolute inset-0 rounded-2xl"
              style={{
                background: 'linear-gradient(90deg, #38bdf8, #818cf8, #38bdf8)',
                backgroundSize: '200% 100%',
                animation: 'shimmer 1.5s linear infinite',
                opacity: 0.15,
              }}
            />
          )}
        </AnimatePresence>

        <motion.div
          animate={drag ? { y: -4 } : { y: 0 }}
          className="flex flex-col items-center gap-3"
        >
          <div className={`flex h-14 w-14 items-center justify-center rounded-2xl transition-colors ${drag ? 'bg-sky-100 text-sky-600' : 'bg-slate-100 text-slate-500'}`}>
            <UploadCloud size={28} />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">
              {drag ? 'Drop your file here' : 'Drag & drop or click to upload'}
            </p>
            <p className="mt-1 text-xs text-slate-500">PDF, DOC, DOCX — max {MAX_MB} MB</p>
          </div>
          <div className="flex items-center gap-2">
            {['PDF', 'DOCX', 'DOC'].map((fmt) => (
              <span key={fmt} className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-sm ring-1 ring-slate-200">
                {fmt}
              </span>
            ))}
          </div>
        </motion.div>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.doc,.docx"
          onChange={onInputChange}
          className="hidden"
        />
      </motion.div>

      <AnimatePresence>
        {error && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-2 text-xs font-medium text-red-600"
          >
            {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}
