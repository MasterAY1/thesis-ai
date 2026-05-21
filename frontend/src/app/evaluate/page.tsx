'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const FEEDBACK_STYLES = [
  { key: 'strict_supervisor',  label: '🎓 Strict Supervisor',  desc: 'Formal, demanding, full rubric compliance expected.' },
  { key: 'friendly_lecturer',  label: '😊 Friendly Lecturer',  desc: 'Supportive and constructive. Highlights what can be improved.' },
  { key: 'blunt_examiner',     label: '📋 Blunt Examiner',     desc: 'Direct. No softening — just the facts and the fix.' },
  { key: 'student_helper',     label: '🤝 Student Helper',     desc: 'Encouraging and simplified. Best for first-time researchers.' },
  { key: 'quick_summary',      label: '⚡ Quick Summary',      desc: 'Ultra-brief bullet points. Fast overview only.' },
];

const INSTITUTIONS = [
  { code: 'nmcn',   label: 'NMCN — Nursing & Midwifery Council of Nigeria' },
];

export default function Evaluate() {
  const [file, setFile]                   = useState<File | null>(null);
  const [isLoading, setIsLoading]         = useState(false);
  const [dragActive, setDragActive]       = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const [progressStatus, setProgressStatus] = useState<string>('');
  const [feedbackStyle, setFeedbackStyle] = useState('friendly_lecturer');
  const [institution, setInstitution]     = useState('nmcn');
  const router = useRouter();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsLoading(true);
    setError(null);
    setProgressStatus('Waking up server...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      // Wake up Render server
      try {
        await fetch(`${API_URL}/api/ping`, { signal: AbortSignal.timeout(30000) });
      } catch { /* already awake */ }

      // Upload — now passes institution and feedback_style as query params
      setProgressStatus('Uploading document...');
      const uploadResponse = await fetch(
        `${API_URL}/api/evaluate?institution=${institution}&feedback_style=${feedbackStyle}`,
        { method: 'POST', body: formData, signal: AbortSignal.timeout(30000) }
      );

      if (!uploadResponse.ok) {
        const errorData = await uploadResponse.json().catch(() => null);
        throw new Error(errorData?.detail || `Upload failed (${uploadResponse.status})`);
      }

      const uploadData = await uploadResponse.json();
      const jobId = uploadData.job_id;
      if (!jobId) throw new Error('Server did not return a job ID.');

      setProgressStatus('Starting AI evaluation...');

      // Poll for results
      const maxPolls = 120;
      for (let i = 0; i < maxPolls; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000));

        const statusResponse = await fetch(`${API_URL}/api/status/${jobId}`, {
          signal: AbortSignal.timeout(15000),
        });
        if (!statusResponse.ok) continue;

        const statusData = await statusResponse.json();
        if (statusData.progress) setProgressStatus(statusData.progress);

        if (statusData.status === 'completed') {
          localStorage.setItem('thesisData', JSON.stringify(statusData.results));
          router.push('/results');
          return;
        }
        if (statusData.status === 'failed') {
          throw new Error(statusData.error || 'Evaluation failed on the server.');
        }
      }

      throw new Error('Evaluation timed out after 10 minutes.');

    } catch (err: unknown) {
      const error = err as Error;
      console.error('Upload error:', error);
      if (error.name === 'AbortError' || error.name === 'TimeoutError') {
        setError('Request timed out. Please try again in a moment.');
      } else if (error.message?.includes('Failed to fetch') || error.message?.includes('NetworkError')) {
        setError('Could not connect to the evaluation server. Please try again.');
      } else {
        setError(error.message || 'An unexpected error occurred.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // ── Loading screen ─────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-slate-900 via-blue-950 to-indigo-950 text-white">
        <div className="flex flex-col items-center space-y-6 max-w-sm w-full px-4">
          <div className="relative w-20 h-20">
            <div className="absolute inset-0 rounded-full border-4 border-blue-500/30"></div>
            <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-400 animate-spin"></div>
            <div className="absolute inset-2 rounded-full border-4 border-transparent border-t-indigo-400 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }}></div>
          </div>
          <h2 className="text-2xl font-semibold text-center">Evaluating your thesis...</h2>
          <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl px-6 py-3 text-center w-full">
            <p className="text-blue-300 font-mono text-sm">{progressStatus}</p>
          </div>
          <p className="text-white/40 text-xs max-w-xs text-center">
            Checking structure, rubric alignment, academic rigor, and citation formatting.
          </p>
          <div className="flex gap-1 mt-2">
            {[0, 150, 300].map(delay => (
              <div key={delay} className="w-2 h-2 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: `${delay}ms` }}></div>
            ))}
          </div>
        </div>
      </main>
    );
  }

  // ── Main upload page ───────────────────────────────────────────────────────
  const selectedStyle = FEEDBACK_STYLES.find(s => s.key === feedbackStyle);

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-indigo-950 text-white">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 md:px-12 py-5">
        <Link href="/" className="text-xl font-bold tracking-tight">
          <span className="text-blue-400">Thesis</span>AI
        </Link>
        <Link href="/" className="text-sm text-blue-300 hover:text-white transition-colors">
          &larr; Back to Home
        </Link>
      </nav>

      <div className="flex items-center justify-center px-4 py-10 md:py-20">
        <div className="max-w-2xl w-full space-y-6">

          {/* Header */}
          <div className="text-center">
            <h1 className="text-3xl md:text-4xl font-bold mb-2">Upload Your Thesis</h1>
            <p className="text-blue-300/70 text-sm">
              Upload your document and receive a detailed, rubric-based evaluation.
            </p>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start gap-3">
              <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <p className="text-red-300 text-sm font-medium">{error}</p>
                <button onClick={() => setError(null)} className="text-red-400/70 text-xs mt-1 hover:text-red-300">Dismiss</button>
              </div>
            </div>
          )}

          {/* ── Settings Card ─────────────────────────────────────────── */}
          <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6 space-y-5">
            <h2 className="text-sm font-semibold text-blue-300 uppercase tracking-widest">Evaluation Settings</h2>

            {/* Institution */}
            <div>
              <label className="block text-xs font-medium text-white/60 mb-2">Institution</label>
              <select
                value={institution}
                onChange={e => setInstitution(e.target.value)}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-400 transition-colors"
              >
                {INSTITUTIONS.map(inst => (
                  <option key={inst.code} value={inst.code} className="bg-slate-800">
                    {inst.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Feedback Style */}
            <div>
              <label className="block text-xs font-medium text-white/60 mb-2">Feedback Style</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {FEEDBACK_STYLES.map(style => (
                  <button
                    key={style.key}
                    onClick={() => setFeedbackStyle(style.key)}
                    className={`text-left px-3 py-2.5 rounded-lg border text-sm transition-all duration-200 ${
                      feedbackStyle === style.key
                        ? 'border-blue-400 bg-blue-500/20 text-white'
                        : 'border-white/10 bg-white/5 text-white/60 hover:border-white/30 hover:text-white/80'
                    }`}
                  >
                    <div className="font-medium text-xs">{style.label}</div>
                    <div className="text-xs opacity-60 mt-0.5 leading-tight">{style.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* ── Upload Card ───────────────────────────────────────────── */}
          <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <label className={`flex flex-col items-center justify-center w-full h-48 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-300 ${dragActive ? 'border-blue-400 bg-blue-500/10' : 'border-white/20 hover:border-blue-400/50 hover:bg-white/5'}`}>
                <div className="flex flex-col items-center justify-center py-6">
                  <div className="w-14 h-14 rounded-full bg-blue-500/20 flex items-center justify-center mb-4">
                    <svg className="w-7 h-7 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                  </div>
                  <p className="text-sm text-blue-200"><span className="font-semibold text-blue-400">Click to upload</span> or drag and drop</p>
                  <p className="text-xs text-blue-300/50 mt-2">PDF or DOCX documents only</p>
                </div>
                <input type="file" className="hidden" accept=".pdf,.docx" onChange={handleFileChange} />
              </label>
            </div>

            {file && (
              <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center shrink-0">
                    <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <span className="font-medium text-blue-200 truncate text-sm">{file.name}</span>
                </div>
                <button onClick={() => setFile(null)} className="text-red-400 hover:text-red-300 text-sm font-medium transition-colors">Remove</button>
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={!file}
              className={`mt-6 w-full py-4 rounded-xl text-lg font-semibold transition-all duration-300 ${file ? 'bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-400 hover:to-indigo-400 text-white shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40' : 'bg-white/10 text-white/30 cursor-not-allowed'}`}
            >
              Evaluate Document
            </button>
          </div>

          {/* Trust Indicators */}
          <div className="flex justify-center gap-8 text-xs text-blue-300/50">
            <span className="flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
              Secure Upload
            </span>
            <span className="flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
              AI-Powered
            </span>
            <span className="flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              NMCN Standards
            </span>
          </div>

        </div>
      </div>
    </main>
  );
}
