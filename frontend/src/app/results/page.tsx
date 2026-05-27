'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Confidence badge ───────────────────────────────────────────────────────
function ConfidenceBadge({ confidence }: { confidence?: number }) {
  if (confidence === undefined || confidence === null) return null;
  const pct = Math.round(confidence * 100);
  const cls =
    confidence >= 0.75 ? 'bg-green-500/20 text-green-300 border-green-500/30' :
    confidence >= 0.55 ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                         'bg-red-500/20 text-red-300 border-red-500/30';
  const label = confidence >= 0.75 ? 'High' : confidence >= 0.55 ? 'Medium' : 'Low';
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${cls}`}>
      🧠 {label} ({pct}%)
    </span>
  );
}

// ── Rewrite Modal ──────────────────────────────────────────────────────────
function RewriteModal({
  issue, onClose, feedbackStyle, institutionName,
}: {
  issue: any;
  onClose: () => void;
  feedbackStyle: string;
  institutionName: string;
}) {
  const [rewrite, setRewrite]   = useState<string>('');
  const [tips, setTips]         = useState<string[]>([]);
  const [loading, setLoading]   = useState(true);
  const [copied, setCopied]     = useState(false);

  useEffect(() => {
    const fetchRewrite = async () => {
      try {
        const res = await fetch(`${API_URL}/api/rewrite`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            issue_title: issue.issue_title,
            issue_description: `${issue.deduction_reasoning || ''} ${issue.suggested_fix || ''}`.trim(),
            section_name: issue.rubric?.section || issue.section || '',
            context: issue.evidence?.quote || '',
            feedback_style: feedbackStyle,
            institution_name: institutionName,
          }),
          signal: AbortSignal.timeout(60000),
        });
        const data = await res.json();
        setRewrite(data.rewrite || '');
        setTips(data.tips || []);
      } catch {
        setRewrite('Unable to generate rewrite at this time. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    fetchRewrite();
  }, [issue, feedbackStyle]);

  const handleCopy = () => {
    navigator.clipboard.writeText(rewrite);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl max-w-xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10">
          <div>
            <h3 className="text-lg font-bold text-white">✨ AI Rewrite</h3>
            <p className="text-xs text-blue-300/70 mt-0.5">{issue.issue_title}</p>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white transition-colors text-2xl leading-none">&times;</button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          {loading ? (
            <div className="flex flex-col items-center py-10 space-y-3">
              <div className="w-10 h-10 rounded-full border-4 border-transparent border-t-blue-400 animate-spin"></div>
              <p className="text-blue-300/60 text-sm">Generating academic rewrite...</p>
            </div>
          ) : (
            <>
              {/* Rewrite block */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold text-blue-300 uppercase tracking-wider">Corrected Text</span>
                  <button
                    onClick={handleCopy}
                    className={`text-xs px-3 py-1 rounded-full border transition-all ${copied ? 'bg-green-500/20 border-green-500/40 text-green-300' : 'border-white/20 text-white/60 hover:border-blue-400/50 hover:text-white'}`}
                  >
                    {copied ? '✓ Copied!' : 'Copy'}
                  </button>
                </div>
                <p className="text-white/90 text-sm leading-relaxed">{rewrite}</p>
              </div>

              {/* Tips */}
              {tips.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-blue-300 uppercase tracking-wider">Improvement Tips</p>
                  {tips.map((tip, i) => (
                    <div key={i} className="flex gap-2 text-sm text-white/70">
                      <span className="text-blue-400 shrink-0">→</span>
                      <span>{tip}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <div className="px-6 pb-6">
          <button onClick={onClose} className="w-full py-2.5 rounded-xl bg-white/10 text-white/80 hover:bg-white/15 transition-colors text-sm font-medium">Close</button>
        </div>
      </div>
    </div>
  );
}

// ── Deduction card ─────────────────────────────────────────────────────────
function DeductionCard({
  item, index, feedbackStyle, institutionName,
}: {
  item: any;
  index: number;
  feedbackStyle: string;
  institutionName: string;
}) {
  const [showRewrite, setShowRewrite] = useState(false);
  const lowConfidence = item.confidence !== undefined && item.confidence < 0.60;

  return (
    <>
      {showRewrite && (
        <RewriteModal issue={item} onClose={() => setShowRewrite(false)} feedbackStyle={feedbackStyle} institutionName={institutionName} />
      )}
      <details className="group bg-white/5 border border-white/10 rounded-xl open:bg-white/8 open:ring-1 open:ring-blue-500/40 transition-all">
        <summary className="flex items-center justify-between p-4 cursor-pointer">
          <div className="flex items-center gap-3 pr-3 min-w-0">
            <svg className={`h-4 w-4 shrink-0 ${item.severity === 'high' ? 'text-red-400' : item.severity === 'medium' ? 'text-amber-400' : 'text-blue-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span className="text-sm font-medium text-white truncate">{item.issue_title || 'Issue'}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <ConfidenceBadge confidence={item.confidence} />
            {item.severity && (
              <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${item.severity === 'high' ? 'bg-red-500/20 text-red-300' : item.severity === 'medium' ? 'bg-amber-500/20 text-amber-300' : 'bg-blue-500/20 text-blue-300'}`}>
                {item.severity.toUpperCase()}
              </span>
            )}
            <span className="text-red-400 font-bold text-sm">-{item.deduction}</span>
            <svg className="h-4 w-4 text-white/30 group-open:-rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </summary>

        <div className="px-4 pb-4 text-sm border-t border-white/10 pt-3 space-y-3">
          {/* Low confidence warning */}
          {lowConfidence && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2 text-xs text-amber-300">
              ⚠️ AI had difficulty confidently evaluating this section. Review this deduction carefully.
            </div>
          )}

          {/* Rubric */}
          {item.rubric?.expected_requirement && (
            <div className="bg-purple-500/10 border-l-4 border-purple-500 p-3 rounded-r-lg">
              <p className="text-xs font-bold text-purple-300 mb-1">📋 Rubric ({item.rubric.section} — {item.rubric.max_marks} marks)</p>
              <p className="text-purple-200 text-sm">{item.rubric.expected_requirement}</p>
            </div>
          )}

          {/* Reasoning */}
          {item.deduction_reasoning && (
            <div className="bg-red-500/10 border-l-4 border-red-500/60 p-3 rounded-r-lg">
              <p className="text-xs font-bold text-red-300 mb-1">❓ Why deducted</p>
              <p className="text-red-200 text-sm">{item.deduction_reasoning}</p>
            </div>
          )}

          {/* Supervisor note */}
          {item.supervisor_note && (
            <p className="text-white/80 text-sm"><span className="font-semibold text-blue-300">🎓 Supervisor:</span> {item.supervisor_note}</p>
          )}

          {/* Evidence */}
          {item.evidence?.quote && (
            <div className="bg-blue-500/10 border-l-4 border-blue-500/60 p-3 rounded-r-lg">
              <p className="italic text-blue-200 text-sm">&ldquo;{item.evidence.quote}&rdquo;</p>
              {item.evidence.location && <p className="text-xs text-blue-400 mt-1">📍 {item.evidence.location}</p>}
            </div>
          )}

          {/* Fix */}
          {item.suggested_fix && (
            <div className="bg-green-500/10 border-l-4 border-green-500/60 p-3 rounded-r-lg flex justify-between items-start gap-3">
              <p className="text-green-200 text-sm"><span className="font-semibold">💡 Fix:</span> {item.suggested_fix}</p>
              <span className="shrink-0 px-2 py-0.5 bg-green-600/60 text-green-200 text-xs font-bold rounded-full">+{item.deduction}</span>
            </div>
          )}

          {/* Fix This For Me button */}
          <button
            onClick={() => setShowRewrite(true)}
            className="mt-1 w-full py-2.5 rounded-xl bg-gradient-to-r from-violet-600/60 to-blue-600/60 hover:from-violet-500/70 hover:to-blue-500/70 border border-violet-500/30 text-white text-sm font-semibold transition-all duration-200 hover:shadow-lg hover:shadow-violet-500/20"
          >
            ✨ Fix This For Me
          </button>
        </div>
      </details>
    </>
  );
}

// ── Main Results page ──────────────────────────────────────────────────────
export default function Results() {
  const [results, setResults]           = useState<any>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const savedData = localStorage.getItem('thesisData');
    if (savedData) {
      setResults(JSON.parse(savedData));
    } else {
      router.push('/');
    }
  }, [router]);

  const handleDownloadPDF = useCallback(async () => {
    if (!results) return;
    setIsDownloading(true);
    try {
      const res = await fetch(`${API_URL}/api/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(results),
        signal: AbortSignal.timeout(60000),
      });
      if (!res.ok) throw new Error('Failed to generate report');
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `ThesisAI_Report_${results.filename || 'evaluation'}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Could not generate PDF. Please try again.');
    } finally {
      setIsDownloading(false);
    }
  }, [results]);

  if (!results) {
    return (
      <main className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="w-10 h-10 rounded-full border-4 border-transparent border-t-blue-400 animate-spin"></div>
      </main>
    );
  }

  const r              = results.results;
  const docType        = r?.document_type;
  const feedbackStyle  = r?.feedback_style || 'friendly_lecturer';
  const overall        = r?.overall_score ?? 0;
  const totalMarks     = r?.total_marks ?? 100;
  const scoreColor     = overall / totalMarks >= 0.70 ? '#22c55e' : overall / totalMarks >= 0.50 ? '#f59e0b' : '#ef4444';

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 md:px-12 py-5 border-b border-white/5">
        <Link href="/" className="text-xl font-bold tracking-tight">
          <span className="text-blue-400">Thesis</span>AI
        </Link>
        <div className="flex items-center gap-3">
          <button
            onClick={handleDownloadPDF}
            disabled={isDownloading}
            className="flex items-center gap-2 text-sm px-4 py-2 rounded-xl bg-blue-600/80 hover:bg-blue-500 border border-blue-500/40 transition-all disabled:opacity-50"
          >
            {isDownloading ? (
              <span className="w-4 h-4 border-2 border-transparent border-t-white rounded-full animate-spin"></span>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
            )}
            {isDownloading ? 'Generating...' : 'Download PDF'}
          </button>
          <Link href="/evaluate" className="text-sm text-blue-300 hover:text-white transition-colors">Upload New Draft</Link>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-10 space-y-6">

        {/* ── Error state ───────────────────────────────────────────── */}
        {r?.error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-6">
            <h2 className="text-red-300 font-bold mb-2">Evaluation Failed</h2>
            <p className="text-red-200/80 text-sm">{r.error}</p>
          </div>
        )}

        {!r?.error && (
          <>
            {/* ── Score hero ────────────────────────────────────────── */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-8 flex flex-col md:flex-row items-center justify-between gap-6">
              <div>
                <h1 className="text-3xl font-bold">Evaluation Results</h1>
                <p className="text-white/50 text-sm mt-1">
                  {results.filename} &middot; {r?.institution_name || r?.institution?.toUpperCase() || 'NMCN'} Rubric
                  {r?.rubric_source === 'adaptive' && (
                    <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-medium">Custom</span>
                  )}
                </p>
                {/* Document type badge */}
                {docType && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className={`text-xs px-3 py-1 rounded-full font-semibold border ${
                      docType.document_type === 'proposal'
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                        : 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                    }`}>
                      📄 {docType.document_type.charAt(0).toUpperCase() + docType.document_type.slice(1)} detected ({Math.round(docType.confidence * 100)}%)
                    </span>
                    {r?.skipped_sections?.length > 0 && (
                      <span className="text-xs px-3 py-1 rounded-full font-semibold border bg-purple-500/20 text-purple-300 border-purple-500/30">
                        ⏭ {r.skipped_sections.length} section(s) skipped (proposal mode)
                      </span>
                    )}
                  </div>
                )}
                {docType?.reason && (
                  <p className="text-xs text-white/40 mt-2 max-w-sm leading-relaxed">{docType.reason}</p>
                )}
              </div>

              {/* Score circle */}
              <div className="flex flex-col items-center shrink-0">
                <div className="relative w-32 h-32 flex items-center justify-center rounded-full" style={{ border: `6px solid ${scoreColor}` }}>
                  <div className="text-center">
                    <span className="text-4xl font-bold" style={{ color: scoreColor }}>{overall}</span>
                    <span className="text-white/40 text-sm">/{totalMarks}</span>
                  </div>
                </div>
                <span className="mt-2 text-sm font-medium" style={{ color: scoreColor }}>
                  {overall / totalMarks >= 0.70 ? 'Pass' : overall / totalMarks >= 0.50 ? 'Marginal' : 'Fail'}
                </span>
              </div>
            </div>

            {/* ── Score Breakdown ───────────────────────────────────── */}
            {r?.breakdown && (
              <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <h2 className="text-lg font-bold mb-5">Score Breakdown</h2>
                <div className="space-y-3">
                  {Object.entries(r.breakdown).map(([section, data]: [string, any]) => {
                    const pct = data.max > 0 ? (data.score / data.max) * 100 : 0;
                    const barColor = pct >= 70 ? '#22c55e' : pct >= 50 ? '#f59e0b' : '#ef4444';
                    const isSkipped = r?.skipped_sections?.some((k: string) =>
                      section.toLowerCase().includes(k.replace('chapter', 'chapter '))
                    );
                    return (
                      <div key={section} className={isSkipped ? 'opacity-40' : ''}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-white/80 flex items-center gap-1.5">
                            {section}
                            {isSkipped && <span className="text-xs text-amber-400">(skipped)</span>}
                          </span>
                          <span className="text-white/60 font-mono text-xs">{data.score}/{data.max}</span>
                        </div>
                        <div className="w-full bg-white/10 rounded-full h-2">
                          <div className="h-2 rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: barColor }}></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Deductions ────────────────────────────────────────── */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-lg font-bold">Deductions & Evidence</h2>
                {r?.deductions?.length > 0 && (
                  <span className="text-xs text-red-300 bg-red-500/20 px-3 py-1 rounded-full border border-red-500/30 font-semibold">
                    {r.deductions.length} issue{r.deductions.length !== 1 ? 's' : ''} found
                  </span>
                )}
              </div>
              <div className="space-y-3">
                {r?.deductions?.length > 0 ? (
                  r.deductions.map((item: any, index: number) => (
                    <DeductionCard key={index} item={item} index={index} feedbackStyle={feedbackStyle} institutionName={r?.institution_name || r?.institution?.toUpperCase() || 'NMCN'} />
                  ))
                ) : (
                  <p className="text-white/50 text-sm">No major deductions found. Excellent work!</p>
                )}
              </div>
            </div>

            {/* ── Improve My Score ──────────────────────────────────── */}
            {r?.improvements?.length > 0 && (
              <div className="bg-gradient-to-r from-blue-600/60 to-indigo-700/60 border border-blue-500/30 rounded-2xl p-8">
                <div className="flex items-center mb-4 gap-3">
                  <span className="text-3xl">🔥</span>
                  <h2 className="text-2xl font-bold">Improve My Score</h2>
                </div>
                <p className="mb-6 text-white/70 text-sm">
                  From <span className="font-bold text-white">{overall}</span> → <span className="font-bold text-green-300">{r.projected_score || overall}</span> by fixing:
                </p>
                <ul className="space-y-3">
                  {r.improvements.map((item: any, index: number) => (
                    <li key={index} className="flex items-start bg-white/10 p-4 rounded-xl gap-3">
                      <svg className="h-5 w-5 text-green-300 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <div>
                        {item.issue_title && <span className="font-bold block mb-0.5 text-blue-200 text-sm">{item.issue_title}</span>}
                        <span className="text-white/80 text-sm leading-relaxed">{item.text || item}</span>
                        {item.marks_recovered && <span className="text-green-300 text-xs font-bold mt-1 block">+{item.marks_recovered} marks</span>}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* ── Cross-Section Validation ───────────────────────────── */}
            {r?.cross_validation?.validations?.length > 0 && (
              <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-5">
                  <div>
                    <h2 className="text-lg font-bold">Cross-Section Consistency</h2>
                    <p className="text-xs text-white/40 mt-1">{r.cross_validation.summary}</p>
                  </div>
                  {r.cross_validation.total_deductions > 0 && (
                    <span className="text-xs px-3 py-1 bg-red-500/20 text-red-300 font-bold rounded-full border border-red-500/30">
                      -{r.cross_validation.total_deductions} marks
                    </span>
                  )}
                </div>
                <div className="space-y-2">
                  {r.cross_validation.validations.map((v: any, index: number) => {
                    const statusCls = v.status === 'pass'
                      ? 'bg-green-500/10 border-green-500/30'
                      : v.status === 'fail'
                      ? 'bg-red-500/10 border-red-500/30'
                      : 'bg-amber-500/10 border-amber-500/30';
                    return (
                      <details key={index} className={`group border rounded-xl transition-all ${statusCls}`}>
                        <summary className="flex items-center justify-between p-4 cursor-pointer">
                          <div className="flex items-center gap-2">
                            <span>{v.status === 'pass' ? '✅' : v.status === 'fail' ? '❌' : '⚠️'}</span>
                            <span className="text-sm font-medium">{v.rule}</span>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${v.status === 'pass' ? 'bg-green-500/20 text-green-300' : v.status === 'fail' ? 'bg-red-500/20 text-red-300' : 'bg-amber-500/20 text-amber-300'}`}>
                              {v.status?.toUpperCase()}
                            </span>
                            {v.deduction > 0 && <span className="text-red-400 font-bold text-sm">-{v.deduction}</span>}
                            <svg className="h-4 w-4 text-white/30 group-open:-rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
                          </div>
                        </summary>
                        <div className="px-4 pb-4 text-sm border-t border-white/10 pt-3 space-y-2">
                          {v.explanation && <p className="text-white/70">{v.explanation}</p>}
                          {v.suggested_fix && <p className="text-green-300"><strong>💡</strong> {v.suggested_fix}</p>}
                        </div>
                      </details>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
