import React, { useEffect, useMemo, useRef, useState } from 'react';
import { UploadCloud, FileText, File, FileImage, Trash2, CheckCircle2, ArrowUpRight } from 'lucide-react';

const acceptedExtensions = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'];
const acceptedTypesLabel = 'PDF, DOC, DOCX, JPG, PNG';

const formatBytes = (bytes) => {
  if (bytes === 0) return '0 bytes';
  const k = 1024;
  const sizes = ['bytes', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

const getFileIcon = (fileName) => {
  const ext = fileName.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return <FileText className="h-6 w-6 text-rose-600" />;
  if (ext === 'jpg' || ext === 'jpeg' || ext === 'png') return <FileImage className="h-6 w-6 text-sky-600" />;
  if (ext === 'doc' || ext === 'docx') return <FileText className="h-6 w-6 text-indigo-600" />;
  return <File className="h-6 w-6 text-slate-600" />;
};

const UploadBox = ({
  normes,
  selectedNorme,
  onNormeChange,
  file,
  onFileChange,
  onFileRemove,
  uploading,
  error,
  onError,
  onSubmit,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const previousUploading = useRef(false);

  const validationError = useMemo(() => {
    if (!file) return '';
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!acceptedExtensions.includes(ext)) {
      return `Unsupported format. Please upload ${acceptedTypesLabel}.`;
    }
    return '';
  }, [file]);

  const handleFileSelection = (selectedFile) => {
    onError('');
    setShowSuccess(false);
    if (!selectedFile) return;

    const ext = selectedFile.name.split('.').pop()?.toLowerCase();
    if (!acceptedExtensions.includes(ext)) {
      onError(`Unsupported file type. Accept ${acceptedTypesLabel}.`);
      onFileChange(null);
      return;
    }

    onFileChange(selectedFile);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    const droppedFile = event.dataTransfer.files?.[0];
    if (droppedFile) {
      handleFileSelection(droppedFile);
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    const preventWindowDrag = (event) => {
      event.preventDefault();
      event.stopPropagation();
    };

    window.addEventListener('dragenter', preventWindowDrag);
    window.addEventListener('dragover', preventWindowDrag);
    window.addEventListener('dragleave', preventWindowDrag);
    window.addEventListener('drop', preventWindowDrag);

    return () => {
      window.removeEventListener('dragenter', preventWindowDrag);
      window.removeEventListener('dragover', preventWindowDrag);
      window.removeEventListener('dragleave', preventWindowDrag);
      window.removeEventListener('drop', preventWindowDrag);
    };
  }, []);

  useEffect(() => {
    if (previousUploading.current && !uploading) {
      if (!error && !file) {
        setShowSuccess(true);
      }
    }

    if (uploading) {
      setShowSuccess(false);
    }

    previousUploading.current = uploading;
  }, [uploading, error, file]);

  return (
    <form onSubmit={onSubmit} className="w-full space-y-6">
      <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
        <label className="space-y-2 text-sm text-slate-700">
          Norme
          <select
            value={selectedNorme}
            onChange={(e) => onNormeChange(e.target.value)}
            className="w-full rounded-[1.5rem] border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            required
          >
            <option value="">Select a norme</option>
            {normes.map((norme) => (
              <option key={norme.id} value={norme.id}>{norme.name}</option>
            ))}
          </select>
        </label>

        <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 shadow-sm">
          <p className="font-semibold text-slate-900">Accepted files</p>
          <p className="mt-2 leading-6 text-slate-600">{acceptedTypesLabel} • Up to 25MB</p>
        </div>
      </div>

      {!file ? (
        <label
          htmlFor="document-upload"
          className={`group block rounded-[2rem] border-2 border-dashed px-8 py-16 text-center transition-all duration-200 ${
            isDragging ? 'border-sky-400 bg-sky-50 shadow-[0_20px_60px_rgba(14,116,226,0.08)]' : 'border-slate-300 bg-white hover:border-slate-400'
          } cursor-pointer`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <input
            id="document-upload"
            type="file"
            accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
            className="hidden"
            onChange={(e) => handleFileSelection(e.target.files?.[0])}
          />

          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-[1.5rem] bg-slate-100 text-slate-700 transition duration-200 group-hover:bg-slate-200">
            <UploadCloud className="h-8 w-8" />
          </div>

          <div className="space-y-3">
            <div className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-100 px-4 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-slate-500 shadow-sm">
              File upload
            </div>
            <p className="text-xl font-semibold text-slate-900">Drag & drop your document</p>
            <p className="mx-auto max-w-xl text-sm text-slate-500">or click anywhere in this area to browse files. Supported formats: {acceptedTypesLabel}.</p>
            <p className="text-sm text-slate-400">{isDragging ? 'Drop it here to upload' : 'Click to select a file'}</p>
          </div>
        </label>
      ) : (
        <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-[1.5rem] bg-slate-100 text-slate-700">
                {getFileIcon(file.name)}
              </div>
              <div className="min-w-0">
                <p className="truncate text-base font-semibold text-slate-900">{file.name}</p>
                <p className="mt-1 text-sm text-slate-500">{formatBytes(file.size)}</p>
                <span className="mt-2 inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-slate-600">
                  Ready to upload
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:items-end">
              <button
                type="button"
                onClick={() => {
                  onFileRemove();
                  onError('');
                }}
                className="inline-flex items-center gap-2 rounded-[1.5rem] border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-100"
              >
                <Trash2 className="h-4 w-4" />
                Replace file
              </button>
              <p className="text-sm text-slate-500">Selected file will stay until upload or replacement.</p>
            </div>
          </div>
        </div>
      )}

      {uploading && (
        <div className="overflow-hidden rounded-3xl border border-slate-200 bg-slate-100">
          <div className="h-2 bg-slate-300">
            <div className="h-2 w-full animate-pulse bg-sky-500" />
          </div>
          <div className="px-4 py-3 text-sm text-slate-600">Uploading…</div>
        </div>
      )}

      {(error || validationError) && (
        <div className="rounded-3xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error || validationError}
        </div>
      )}

      {showSuccess && (
        <div className="rounded-3xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-700 shadow-sm">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <div>
              <p className="font-semibold text-emerald-900">Upload complete</p>
              <p className="text-sm text-emerald-700">Your document was uploaded successfully.</p>
            </div>
          </div>
        </div>
      )}

      <button
        type="submit"
        disabled={uploading}
        className="inline-flex w-full items-center justify-center gap-2 rounded-[1.5rem] bg-slate-900 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-slate-900/10 transition duration-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {uploading ? 'Uploading your file…' : 'Submit document'}
        <ArrowUpRight className="h-4 w-4" />
      </button>
    </form>
  );
};

export default UploadBox;
