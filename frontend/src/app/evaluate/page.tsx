'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const FEEDBACK_STYLES = [
  { key: 'strict_supervisor', label: '🎓 Strict Supervisor',  desc: 'Formal, demanding, full rubric compliance expected.' },
  { key: 'friendly_lecturer', label: '😊 Friendly Lecturer',  desc: 'Supportive and constructive. Highlights what can be improved.' },
  { key: 'blunt_examiner',    label: '📋 Blunt Examiner',     desc: 'Direct. No softening — just the facts and the fix.' },
  { key: 'student_helper',    label: '🤝 Student Helper',     desc: 'Encouraging and simplified. Best for first-time researchers.' },
  { key: 'quick_summary',     label: '⚡ Quick Summary',      desc: 'Ultra-brief bullet points. Fast overview only.' },
];

const INSTITUTIONS = [
  { code: 'nmcn',            label: 'NMCN -- Nursing & Midwifery Council',       type: 'official' },
  { code: 'nigeria_general', label: 'General Nigerian University',                type: 'general' },
  { code: 'lasu',            label: 'LASU -- Lagos State University',             type: 'institutional' },
  { code: 'unilag',          label: 'UNILAG -- University of Lagos',              type: 'institutional' },
  { code: 'oau',             label: 'OAU -- Obafemi Awolowo University',          type: 'institutional' },
  { code: 'futa',            label: 'FUTA -- Federal Uni. of Technology, Akure',  type: 'institutional' },
];

const EVALUATION_MODES = [
  {
    key: 'fast',
    icon: '⚡',
    label: 'Fast Evaluation',
    time: '30–90 seconds',
    desc: 'Parallel AI evaluation of all sections. Core rubric scoring, structural analysis, citation checks, and missing section detection.',
    color: 'from-emerald-500 to-teal-500',
    borderColor: 'border-emerald-500/40',
    bgColor: 'bg-emerald-500/10',
    features: ['Rubric scoring', 'Structural analysis', 'Citation check', 'Missing sections', 'All chapters in parallel'],
  },
  {
    key: 'deep',
    icon: '🔬',
    label: 'Deep Evaluation',
    time: '2–4 minutes',
    desc: 'Full pipeline with cross-section consistency validation, contradiction analysis, and supervisor-level critique.',
    color: 'from-indigo-500 to-purple-500',
    borderColor: 'border-indigo-500/40',
    bgColor: 'bg-indigo-500/10',
    features: ['Everything in Fast', 'Cross-section validation', 'Contradiction analysis', 'Objectives ↔ Methodology', 'Findings ↔ Conclusions'],
  },
];

// Default section order — overridden dynamically when rubric is loaded
const DEFAULT_SECTION_ORDER = [
  'Preliminary Pages',
  'Chapter One',
  'Chapter Two',
  'Chapter Three',
  'Chapter Four',
  'Chapter Five',
  'References and Appendix',
  'References and Appendices',
  'References',
  'Typing Instructions',
  'General Formatting',
];

type SectionStatus = 'pending' | 'evaluating' | 'completed' | 'missing' | 'skipped' | 'error';

interface SectionProgress {
  [key: string]: SectionStatus;
}

function StatusIcon({ status }: { status: SectionStatus }) {
  if (status === 'completed') {
    return (
      <span className="w-5 h-5 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
        <svg className="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      </span>
    );
  }
  if (status === 'evaluating') {
    return (
      <span className="w-5 h-5 rounded-full border-2 border-blue-400 border-t-transparent animate-spin flex-shrink-0" />
    );
  }
  if (status === 'missing') {
    return (
      <span className="w-5 h-5 rounded-full bg-red-500/20 border border-red-500/40 flex items-center justify-center">
        <svg className="w-3 h-3 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </span>
    );
  }
  if (status === 'skipped') {
    return (
      <span className="w-5 h-5 rounded-full bg-yellow-500/20 border border-yellow-500/40 flex items-center justify-center">
        <svg className="w-3 h-3 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
        </svg>
      </span>
    );
  }
  if (status === 'error') {
    return (
      <span className="w-5 h-5 rounded-full bg-orange-500/20 border border-orange-500/40 flex items-center justify-center">
        <svg className="w-3 h-3 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v2m0 4h.01" />
        </svg>
      </span>
    );
  }
  // pending
  return (
    <span className="w-5 h-5 rounded-full border border-white/10 bg-white/5 flex-shrink-0" />
  );
}

function statusLabel(status: SectionStatus): string {
  switch (status) {
    case 'completed':  return 'Completed';
    case 'evaluating': return 'Evaluating…';
    case 'missing':    return 'Not found';
    case 'skipped':    return 'Skipped';
    case 'error':      return 'Error';
    default:           return 'Pending';
  }
}

function statusColor(status: SectionStatus): string {
  switch (status) {
    case 'completed':  return 'text-emerald-400';
    case 'evaluating': return 'text-blue-400';
    case 'missing':    return 'text-red-400';
    case 'skipped':    return 'text-yellow-400';
    case 'error':      return 'text-orange-400';
    default:           return 'text-white/30';
  }
}

export default function Evaluate() {
  const [file, setFile]               = useState<File | null>(null);
  const [isLoading, setIsLoading]     = useState(false);
  const [dragActive, setDragActive]   = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const [feedbackStyle, setFeedbackStyle] = useState('friendly_lecturer');
  const [institution, setInstitution] = useState('nmcn');
  const [evalMode, setEvalMode]       = useState<'fast' | 'deep'>('fast');

  // Live progress state
  const [progressMessage, setProgressMessage] = useState('');
  const [sectionProgress, setSectionProgress] = useState<SectionProgress>({});
  const [detectedSections, setDetectedSections] = useState<string[]>([]);
  const [elapsedSeconds, setElapsedSeconds]   = useState(0);
  const [earlySignals, setEarlySignals]       = useState<string[]>([]);

  // Guideline upload state
  const [guidelineFile, setGuidelineFile]     = useState<File | null>(null);
  const [customRubric, setCustomRubric]       = useState<any>(null);
  const [showRubricPreview, setShowRubricPreview] = useState(false);
  const [rubricExtracting, setRubricExtracting] = useState(false);
  const [rubricWarnings, setRubricWarnings]   = useState<string[]>([]);
  const [rubricConfidence, setRubricConfidence] = useState<number>(0);

  const router      = useRouter();
  const startTimeRef = useRef<number>(0);
  const timerRef    = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollingRef  = useRef<ReturnType<typeof setInterval> | null>(null);

  // Elapsed timer
  useEffect(() => {
    if (isLoading) {
      startTimeRef.current = Date.now();
      timerRef.current = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsedSeconds(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isLoading]);

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

  // Stop all polling intervals
  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsLoading(true);
    setError(null);
    setProgressMessage('Waking up server…');
    setSectionProgress({});
    setDetectedSections([]);
    setEarlySignals([]);

    const formData = new FormData();
    formData.append('file', file);

    try {
      // Wake up server
      try {
        await fetch(`${API_URL}/api/ping`, { signal: AbortSignal.timeout(30000) });
      } catch { /* already awake */ }

      setProgressMessage('Uploading document…');
      setEarlySignals(prev => [...prev, '✓ Connecting to server']);

      // Submit evaluation job — include custom_rubric if set
      let evalUrl = `${API_URL}/api/evaluate?institution=${institution}&feedback_style=${feedbackStyle}&evaluation_mode=${evalMode}`;
      if (customRubric) {
        formData.append('custom_rubric', JSON.stringify(customRubric));
      }
      const uploadResponse = await fetch(
        evalUrl,
        { method: 'POST', body: formData, signal: AbortSignal.timeout(60000) }
      );

      if (!uploadResponse.ok) {
        const errorData = await uploadResponse.json().catch(() => null);
        throw new Error(errorData?.detail || `Upload failed (${uploadResponse.status})`);
      }

      const uploadData = await uploadResponse.json();

      // Cache hit — result returned immediately
      if (uploadData.status === 'completed' && uploadData.cached) {
        setEarlySignals(prev => [...prev, '⚡ Cached result found — loading instantly']);
        localStorage.setItem('thesisData', JSON.stringify(uploadData.results));
        router.push('/results');
        return;
      }

      const jobId = uploadData.job_id;
      if (!jobId) throw new Error('Server did not return a job ID.');

      setEarlySignals(prev => [...prev, '✓ Document uploaded successfully']);
      setProgressMessage('Starting AI evaluation…');

      // ── Live progress polling every 2 seconds ─────────────────────────────
      pollingRef.current = setInterval(async () => {
        try {
          const progressResponse = await fetch(`${API_URL}/api/progress/${jobId}`, {
            signal: AbortSignal.timeout(10000),
          });
          if (!progressResponse.ok) return;

          const progressData = await progressResponse.json();

          if (progressData.progress) setProgressMessage(progressData.progress);
          if (progressData.section_progress) setSectionProgress(progressData.section_progress);
          if (progressData.detected_sections?.length > 0) {
            setDetectedSections(progressData.detected_sections);
            setEarlySignals(prev => {
              const signal = `✓ ${progressData.detected_sections.length} sections detected`;
              return prev.includes(signal) ? prev : [...prev, signal];
            });
          }
        } catch {
          // Ignore transient polling errors
        }
      }, 2000);

      // ── Status polling every 5 seconds for completion ─────────────────────
      const maxPolls = 120;
      for (let i = 0; i < maxPolls; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000));

        const statusResponse = await fetch(`${API_URL}/api/status/${jobId}`, {
          signal: AbortSignal.timeout(15000),
        });
        if (!statusResponse.ok) continue;

        const statusData = await statusResponse.json();
        if (statusData.progress) setProgressMessage(statusData.progress);
        if (statusData.section_progress) setSectionProgress(statusData.section_progress);

        if (statusData.status === 'completed') {
          stopPolling();
          localStorage.setItem('thesisData', JSON.stringify(statusData.results));
          router.push('/results');
          return;
        }
        if (statusData.status === 'failed') {
          stopPolling();
          throw new Error(statusData.error || 'Evaluation failed on the server.');
        }
      }

      stopPolling();
      throw new Error('Evaluation timed out after 10 minutes.');

    } catch (err: unknown) {
      stopPolling();
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

  // ── Computed stats ──────────────────────────────────────────────────────────
  const completedSections = Object.values(sectionProgress).filter(
    s => s === 'completed' || s === 'missing' || s === 'skipped'
  ).length;
  const totalSections = Object.keys(sectionProgress).length;
  const progressPercent = totalSections > 0
    ? Math.round((completedSections / totalSections) * 100)
    : 0;

  const estimatedTotal = evalMode === 'fast' ? 90 : 240;
  const remaining = Math.max(0, estimatedTotal - elapsedSeconds);
  const remainingLabel = remaining > 60
    ? `~${Math.ceil(remaining / 60)}m remaining`
    : `~${remaining}s remaining`;

  // ── Loading / progress screen ───────────────────────────────────────────────
  if (isLoading) {
    const modeInfo = EVALUATION_MODES.find(m => m.key === evalMode)!;
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-indigo-950 text-white flex items-center justify-center px-4">
        <div className="w-full max-w-lg space-y-6">

          {/* Header */}
          <div className="text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm mb-4">
              <span className="text-lg">{modeInfo.icon}</span>
              <span className="font-medium">{modeInfo.label}</span>
              <span className="text-white/40 text-xs">· {modeInfo.time}</span>
            </div>
            <h2 className="text-2xl font-bold">Evaluating your thesis…</h2>
            <p className="text-white/40 text-sm mt-1">{progressMessage}</p>
          </div>

          {/* Elapsed + estimated */}
          <div className="flex justify-between text-xs text-white/40 px-1">
            <span>⏱ {elapsedSeconds}s elapsed</span>
            {elapsedSeconds > 5 && <span>{remainingLabel}</span>}
          </div>

          {/* Progress bar */}
          {totalSections > 0 && (
            <div className="space-y-2">
              <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-700 ease-out"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              <p className="text-xs text-white/40 text-right">{completedSections}/{totalSections} sections complete</p>
            </div>
          )}

          {/* Early signals */}
          {earlySignals.length > 0 && (
            <div className="space-y-1.5">
              {earlySignals.map((signal, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-emerald-400/80">
                  <span className="font-mono text-xs">{signal}</span>
                </div>
              ))}
            </div>
          )}

          {/* Section progress tracker */}
          <div className="bg-white/[0.04] border border-white/10 rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/5">
              <p className="text-xs font-semibold text-white/50 uppercase tracking-widest">Section Progress</p>
            </div>
            {/* Use sections from API progress or fall back to default order */}
            {(Object.keys(sectionProgress).length > 0
              ? Object.keys(sectionProgress)
              : DEFAULT_SECTION_ORDER.filter(s => !['References and Appendix', 'References and Appendices', 'References'].includes(s) || s === 'References and Appendix')
            ).map(section => {
              const status = sectionProgress[section] ?? 'pending';
              return (
                <div key={section} className="flex items-center gap-3 px-4 py-3">
                  <StatusIcon status={status} />
                  <span className={`text-sm flex-1 font-medium ${
                    status === 'pending' ? 'text-white/30' : 'text-white/80'
                  }`}>
                    {section}
                  </span>
                  <span className={`text-xs font-mono ${statusColor(status)}`}>
                    {statusLabel(status)}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Animated dots */}
          <div className="flex justify-center gap-1.5">
            {[0, 150, 300].map(delay => (
              <div
                key={delay}
                className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce"
                style={{ animationDelay: `${delay}ms` }}
              />
            ))}
          </div>

        </div>
      </main>
    );
  }

  // ── Main upload page ────────────────────────────────────────────────────────
  const selectedStyle = FEEDBACK_STYLES.find(s => s.key === feedbackStyle);

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-indigo-950 text-white">

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 md:px-12 py-5">
        <Link href="/" className="text-xl font-bold tracking-tight">
          <span className="text-blue-400">Thesis</span>AI
        </Link>
        <Link href="/" className="text-sm text-blue-300 hover:text-white transition-colors">
          ← Back to Home
        </Link>
      </nav>

      <div className="flex items-center justify-center px-4 py-10 md:py-16">
        <div className="max-w-2xl w-full space-y-5">

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

          {/* ── EVALUATION MODE SELECTOR ──────────────────────────────────── */}
          <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6 space-y-3">
            <h2 className="text-sm font-semibold text-blue-300 uppercase tracking-widest">Evaluation Mode</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {EVALUATION_MODES.map(mode => (
                <button
                  key={mode.key}
                  onClick={() => setEvalMode(mode.key as 'fast' | 'deep')}
                  className={`relative text-left p-4 rounded-xl border-2 transition-all duration-200 ${
                    evalMode === mode.key
                      ? `${mode.borderColor} ${mode.bgColor}`
                      : 'border-white/10 bg-white/[0.03] hover:border-white/20'
                  }`}
                >
                  {evalMode === mode.key && (
                    <span className={`absolute top-3 right-3 w-2 h-2 rounded-full bg-gradient-to-r ${mode.color}`} />
                  )}
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">{mode.icon}</span>
                    <span className="font-semibold text-sm text-white">{mode.label}</span>
                  </div>
                  <p className={`text-xs font-mono mb-2 bg-gradient-to-r ${mode.color} bg-clip-text text-transparent`}>
                    ⏱ {mode.time}
                  </p>
                  <p className="text-xs text-white/50 leading-snug mb-3">{mode.desc}</p>
                  <ul className="space-y-1">
                    {mode.features.map(f => (
                      <li key={f} className="flex items-center gap-1.5 text-xs text-white/60">
                        <svg className="w-3 h-3 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                        </svg>
                        {f}
                      </li>
                    ))}
                  </ul>
                </button>
              ))}
            </div>
          </div>

          {/* ── SETTINGS CARD ────────────────────────────────────────────── */}
          <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6 space-y-5">
            <h2 className="text-sm font-semibold text-blue-300 uppercase tracking-widest">Evaluation Settings</h2>

            {/* Institution */}
            <div>
              <label className="block text-xs font-medium text-white/60 mb-2">Institution / Rubric</label>
              <select
                value={institution}
                onChange={e => { setInstitution(e.target.value); setCustomRubric(null); setGuidelineFile(null); }}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-400 transition-colors"
              >
                {INSTITUTIONS.map(inst => (
                  <option key={inst.code} value={inst.code} className="bg-slate-800">
                    {inst.type === 'official' ? '🏛 ' : inst.type === 'general' ? '🇳🇬 ' : '🎓 '}
                    {inst.label}
                  </option>
                ))}
              </select>
              {institution !== 'nmcn' && (
                <p className="text-xs text-white/30 mt-1.5">
                  {institution === 'nigeria_general'
                    ? 'Uses the standard Nigerian 5-chapter project rubric (100 marks)'
                    : `Inherits from General Nigerian rubric. Upload a department guideline below to customize.`}
                </p>
              )}
            </div>

            {/* Guideline Upload (non-NMCN institutions only) */}
            {institution !== 'nmcn' && (
              <div className="border border-dashed border-white/20 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-white/60">
                    📋 Department Guideline <span className="text-white/30">(Optional)</span>
                  </label>
                  {customRubric && (
                    <button
                      onClick={() => { setCustomRubric(null); setGuidelineFile(null); setRubricWarnings([]); }}
                      className="text-xs text-red-400 hover:text-red-300 transition-colors"
                    >
                      Clear
                    </button>
                  )}
                </div>

                {!customRubric ? (
                  <div>
                    <input
                      type="file"
                      accept=".pdf,.docx"
                      onChange={async (e) => {
                        const f = e.target.files?.[0];
                        if (!f) return;
                        setGuidelineFile(f);
                        setRubricExtracting(true);
                        setRubricWarnings([]);
                        try {
                          const formData = new FormData();
                          formData.append('file', f);
                          const res = await fetch(`${API_URL}/api/rubric/extract?institution_name=${encodeURIComponent(f.name)}`, {
                            method: 'POST',
                            body: formData,
                            signal: AbortSignal.timeout(30000),
                          });
                          if (!res.ok) {
                            const err = await res.json().catch(() => ({}));
                            throw new Error(err.detail || 'Extraction failed');
                          }
                          const data = await res.json();
                          setCustomRubric(data.rubric);
                          setRubricConfidence(data.confidence || 0);
                          setRubricWarnings(data.warnings || []);
                          setShowRubricPreview(true);
                        } catch (err: any) {
                          setRubricWarnings([err.message || 'Failed to extract rubric']);
                          setGuidelineFile(null);
                        } finally {
                          setRubricExtracting(false);
                        }
                      }}
                      className="w-full text-sm text-white/60 file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-white/10 file:text-white/80 hover:file:bg-white/20 file:cursor-pointer file:transition-colors"
                    />
                    <p className="text-xs text-white/30 mt-1.5">
                      Upload your department handbook or scoring guide (PDF/DOCX). We'll extract the rubric automatically.
                    </p>
                    {rubricExtracting && (
                      <div className="flex items-center gap-2 mt-2">
                        <div className="w-4 h-4 rounded-full border-2 border-transparent border-t-blue-400 animate-spin"></div>
                        <span className="text-xs text-blue-300/60">Extracting rubric...</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-emerald-400 font-semibold">✓ Custom rubric loaded</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                          rubricConfidence >= 0.75 ? 'bg-green-500/20 text-green-300 border-green-500/30' :
                          rubricConfidence >= 0.55 ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                                                     'bg-red-500/20 text-red-300 border-red-500/30'
                        }`}>
                          {rubricConfidence >= 0.75 ? 'High' : rubricConfidence >= 0.55 ? 'Medium' : 'Low'} confidence
                        </span>
                      </div>
                      <button
                        onClick={() => setShowRubricPreview(true)}
                        className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                      >
                        Edit Rubric
                      </button>
                    </div>
                    {guidelineFile && (
                      <p className="text-xs text-white/40">From: {guidelineFile.name}</p>
                    )}
                  </div>
                )}

                {rubricWarnings.length > 0 && !showRubricPreview && (
                  <div className="space-y-1">
                    {rubricWarnings.map((w, i) => (
                      <p key={i} className="text-xs text-amber-400/80">⚠ {w}</p>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── RUBRIC PREVIEW MODAL ──────────────────────────────── */}
            {showRubricPreview && customRubric && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                  <div className="flex items-center justify-between p-6 border-b border-white/10">
                    <div>
                      <h3 className="text-lg font-bold text-white">📋 Rubric Preview</h3>
                      <p className="text-xs text-white/40 mt-0.5">Review and edit extracted marks before evaluation</p>
                    </div>
                    <button onClick={() => setShowRubricPreview(false)} className="text-white/40 hover:text-white text-2xl">&times;</button>
                  </div>

                  <div className="p-6 space-y-4">
                    {/* Warnings */}
                    {rubricWarnings.length > 0 && (
                      <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 space-y-1">
                        {rubricWarnings.map((w, i) => (
                          <p key={i} className="text-xs text-amber-300">⚠ {w}</p>
                        ))}
                      </div>
                    )}

                    {/* Total */}
                    <div className="flex items-center justify-between px-3 py-2 bg-white/5 rounded-lg">
                      <span className="text-sm font-semibold text-white">Total Marks</span>
                      <span className="text-lg font-bold text-blue-400">{customRubric.total_marks}</span>
                    </div>

                    {/* Section table — editable marks */}
                    <div className="space-y-2">
                      {Object.entries(customRubric.sections || {}).map(([name, data]: [string, any]) => (
                        <div key={name} className="flex items-center justify-between bg-white/5 border border-white/10 rounded-lg px-4 py-3">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white truncate">{name}</p>
                            <p className="text-xs text-white/40">{Object.keys(data.criteria || {}).length} criteria</p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <input
                              type="number"
                              min={0}
                              max={100}
                              value={data.total}
                              onChange={(e) => {
                                const newVal = parseFloat(e.target.value) || 0;
                                setCustomRubric((prev: any) => {
                                  const updated = JSON.parse(JSON.stringify(prev));
                                  updated.sections[name].total = newVal;
                                  updated.total_marks = Object.values(updated.sections).reduce((sum: number, s: any) => sum + (s.total || 0), 0);
                                  return updated;
                                });
                              }}
                              className="w-16 bg-white/10 border border-white/20 rounded-lg px-2 py-1.5 text-sm text-white text-center focus:outline-none focus:border-blue-400"
                            />
                            <span className="text-xs text-white/40">marks</span>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Confidence */}
                    {customRubric._extraction_meta?.section_confidences && (
                      <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                        <p className="text-xs font-semibold text-white/60 mb-2">Section Confidence</p>
                        <div className="flex flex-wrap gap-1.5">
                          {Object.entries(customRubric._extraction_meta.section_confidences).map(([key, conf]: [string, any]) => (
                            <span key={key} className={`text-xs px-2 py-0.5 rounded-full border ${
                              conf >= 0.7 ? 'bg-green-500/20 text-green-300 border-green-500/30' :
                              conf >= 0.5 ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                                            'bg-red-500/20 text-red-300 border-red-500/30'
                            }`}>
                              {key}: {Math.round(conf * 100)}%
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-3 px-6 pb-6">
                    <button
                      onClick={() => setShowRubricPreview(false)}
                      className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-blue-600/80 to-indigo-600/80 hover:from-blue-500 hover:to-indigo-500 text-white text-sm font-semibold transition-all"
                    >
                      Use This Rubric
                    </button>
                    <button
                      onClick={() => { setCustomRubric(null); setGuidelineFile(null); setShowRubricPreview(false); setRubricWarnings([]); }}
                      className="px-6 py-2.5 rounded-xl bg-white/10 text-white/80 hover:bg-white/15 text-sm transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}

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

          {/* ── UPLOAD CARD ──────────────────────────────────────────────── */}
          <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <label className={`flex flex-col items-center justify-center w-full h-44 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-300 ${
                dragActive ? 'border-blue-400 bg-blue-500/10' : 'border-white/20 hover:border-blue-400/50 hover:bg-white/5'
              }`}>
                <div className="flex flex-col items-center justify-center py-6">
                  <div className="w-14 h-14 rounded-full bg-blue-500/20 flex items-center justify-center mb-4">
                    <svg className="w-7 h-7 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                  </div>
                  <p className="text-sm text-blue-200"><span className="font-semibold text-blue-400">Click to upload</span> or drag and drop</p>
                  <p className="text-xs text-blue-300/50 mt-2">PDF or DOCX documents only · Max 15MB</p>
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
                  <div>
                    <p className="font-medium text-blue-200 truncate text-sm">{file.name}</p>
                    <p className="text-xs text-blue-300/50">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                </div>
                <button onClick={() => setFile(null)} className="text-red-400 hover:text-red-300 text-sm font-medium transition-colors">Remove</button>
              </div>
            )}

            {/* Submit button */}
            <button
              onClick={handleUpload}
              disabled={!file}
              className={`mt-6 w-full py-4 rounded-xl text-base font-semibold transition-all duration-300 flex items-center justify-center gap-2 ${
                file
                  ? 'bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-400 hover:to-indigo-400 text-white shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 hover:scale-[1.01]'
                  : 'bg-white/10 text-white/30 cursor-not-allowed'
              }`}
            >
              {file ? (
                <>
                  {evalMode === 'fast' ? '⚡' : '🔬'}
                  <span>Start {evalMode === 'fast' ? 'Fast' : 'Deep'} Evaluation</span>
                </>
              ) : (
                'Upload a document to begin'
              )}
            </button>
          </div>

          {/* Trust indicators */}
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
