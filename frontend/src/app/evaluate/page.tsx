'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Evaluate() {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
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

    const formData = new FormData();
    formData.append('file', file);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 min timeout

      const response = await fetch(`${API_URL}/api/evaluate`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || `Server error (${response.status})`);
      }

      const data = await response.json();
      
      localStorage.setItem('thesisData', JSON.stringify(data));
      
      router.push('/results');
    } catch (err: unknown) {
      const error = err as Error;
      console.error(error);
      if (error.name === 'AbortError') {
        setError('Evaluation timed out. Your document may be too large. Please try again.');
      } else if (error.message?.includes('Failed to fetch') || error.message?.includes('NetworkError')) {
        setError('Could not connect to the evaluation server. Please ensure the backend is running.');
      } else {
        setError(error.message || 'An unexpected error occurred during evaluation.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-slate-900 via-blue-950 to-indigo-950 text-white">
        <div className="flex flex-col items-center space-y-6">
          <div className="relative w-20 h-20">
            <div className="absolute inset-0 rounded-full border-4 border-blue-500/30"></div>
            <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-400 animate-spin"></div>
            <div className="absolute inset-2 rounded-full border-4 border-transparent border-t-indigo-400 animate-spin" style={{animationDirection: 'reverse', animationDuration: '1.5s'}}></div>
          </div>
          <h2 className="text-2xl font-semibold">Evaluating your thesis...</h2>
          <p className="text-blue-300/80 text-sm max-w-sm text-center">Parsing document, extracting sections, and grading against the NMCN rubric. This may take 1-2 minutes.</p>
          <div className="flex gap-1 mt-2">
            <div className="w-2 h-2 rounded-full bg-blue-400 animate-bounce" style={{animationDelay: '0ms'}}></div>
            <div className="w-2 h-2 rounded-full bg-blue-400 animate-bounce" style={{animationDelay: '150ms'}}></div>
            <div className="w-2 h-2 rounded-full bg-blue-400 animate-bounce" style={{animationDelay: '300ms'}}></div>
          </div>
        </div>
      </main>
    );
  }

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

      <div className="flex items-center justify-center px-4 py-16 md:py-24">
        <div className="max-w-2xl w-full">
          {/* Header */}
          <div className="text-center mb-10">
            <h1 className="text-3xl md:text-4xl font-bold mb-3">Upload Your Thesis</h1>
            <p className="text-blue-300/70">Upload your document and receive a detailed, rubric-based evaluation within seconds.</p>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start gap-3">
              <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <p className="text-red-300 text-sm font-medium">{error}</p>
                <button 
                  onClick={() => setError(null)}
                  className="text-red-400/70 text-xs mt-1 hover:text-red-300 transition-colors"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {/* Upload Card */}
          <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <label className={`flex flex-col items-center justify-center w-full h-56 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-300 ${dragActive ? 'border-blue-400 bg-blue-500/10' : 'border-white/20 hover:border-blue-400/50 hover:bg-white/5'}`}>
                <div className="flex flex-col items-center justify-center py-6">
                  <div className="w-14 h-14 rounded-full bg-blue-500/20 flex items-center justify-center mb-4">
                    <svg className="w-7 h-7 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
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
                  <span className="font-medium text-blue-200 truncate">{file.name}</span>
                </div>
                <button 
                  onClick={() => setFile(null)}
                  className="text-red-400 hover:text-red-300 text-sm font-medium transition-colors"
                >
                  Remove
                </button>
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
          <div className="flex justify-center gap-8 mt-8 text-xs text-blue-300/50">
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
