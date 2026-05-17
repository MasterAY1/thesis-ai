'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-white overflow-x-hidden">

      {/* ─── NAVBAR ─── */}
      <nav className={`fixed top-0 w-full z-50 transition-all duration-300 ${scrolled ? 'bg-slate-950/80 backdrop-blur-xl border-b border-white/5 shadow-lg' : ''}`}>
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 md:px-12 py-4">
          <span className="text-xl font-bold tracking-tight">
            <span className="text-blue-400">Thesis</span>AI
          </span>
          <div className="hidden md:flex items-center gap-8 text-sm text-blue-200/60">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-white transition-colors">How it Works</a>
            <a href="#rubric" className="hover:text-white transition-colors">Rubric Engine</a>
          </div>
          <Link href="/evaluate" className="px-5 py-2.5 rounded-lg bg-blue-500 hover:bg-blue-400 text-sm font-semibold transition-colors shadow-lg shadow-blue-500/20">
            Evaluate Now
          </Link>
        </div>
      </nav>

      {/* ─── HERO ─── */}
      <section className="relative min-h-screen flex items-center justify-center px-6 pt-20">
        {/* Background gradient orbs */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/15 rounded-full blur-3xl"></div>
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-indigo-500/15 rounded-full blur-3xl"></div>

        <div className="relative max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500/10 border border-blue-500/20 rounded-full text-xs text-blue-300 mb-8">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
            Powered by AI &middot; Built for NMCN Standards
          </div>
          <h1 className="text-5xl md:text-7xl font-bold leading-tight tracking-tight mb-6">
            Grade Your Project<br/>
            <span className="bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">Before Your Supervisor Does</span>
          </h1>
          <p className="text-lg md:text-xl text-blue-200/60 max-w-2xl mx-auto mb-10 leading-relaxed">
            Upload your final year project or thesis and get instant, evidence-based feedback with rubric-aware scoring, deduction reasoning, and actionable improvement tips — all in seconds.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/evaluate" className="group px-8 py-4 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold text-lg shadow-xl shadow-blue-500/25 hover:shadow-blue-500/40 transition-all hover:scale-105">
              Start Evaluating
              <span className="ml-2 group-hover:translate-x-1 inline-block transition-transform">→</span>
            </Link>
            <a href="#features" className="px-8 py-4 rounded-xl border border-white/10 text-blue-200/70 hover:text-white hover:border-white/20 transition-all text-lg">
              See How It Works
            </a>
          </div>

          {/* Stats Bar */}
          <div className="mt-20 grid grid-cols-3 gap-6 max-w-lg mx-auto">
            <div>
              <p className="text-3xl font-bold text-white">100</p>
              <p className="text-xs text-blue-300/50 mt-1">Total Rubric Marks</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-white">8</p>
              <p className="text-xs text-blue-300/50 mt-1">Sections Graded</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-white">&lt;60s</p>
              <p className="text-xs text-blue-300/50 mt-1">Evaluation Time</p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── FEATURES ─── */}
      <section id="features" className="py-24 px-6 relative">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-blue-400 text-sm font-semibold tracking-widest uppercase mb-3">Features</p>
            <h2 className="text-3xl md:text-5xl font-bold">Everything You Need to<br/><span className="text-blue-400">Ace Your Thesis</span></h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Feature Card 1 */}
            <div className="group bg-white/[0.03] border border-white/5 rounded-2xl p-8 hover:bg-white/[0.06] hover:border-blue-500/20 transition-all duration-300">
              <div className="w-12 h-12 rounded-xl bg-blue-500/15 flex items-center justify-center mb-5 group-hover:bg-blue-500/25 transition-colors">
                <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Smart Section Splitting</h3>
              <p className="text-sm text-blue-200/50 leading-relaxed">AI automatically detects and extracts your Abstract, Chapters 1–5, and References — even from messy document formatting.</p>
            </div>

            {/* Feature Card 2 */}
            <div className="group bg-white/[0.03] border border-white/5 rounded-2xl p-8 hover:bg-white/[0.06] hover:border-purple-500/20 transition-all duration-300">
              <div className="w-12 h-12 rounded-xl bg-purple-500/15 flex items-center justify-center mb-5 group-hover:bg-purple-500/25 transition-colors">
                <svg className="w-6 h-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Rubric-Aware Grading</h3>
              <p className="text-sm text-blue-200/50 leading-relaxed">Every deduction is explicitly tied to your university's rubric requirements — you always know exactly which rule you violated and why.</p>
            </div>

            {/* Feature Card 3 */}
            <div className="group bg-white/[0.03] border border-white/5 rounded-2xl p-8 hover:bg-white/[0.06] hover:border-green-500/20 transition-all duration-300">
              <div className="w-12 h-12 rounded-xl bg-green-500/15 flex items-center justify-center mb-5 group-hover:bg-green-500/25 transition-colors">
                <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Score Improvement Engine</h3>
              <p className="text-sm text-blue-200/50 leading-relaxed">See your projected improved score with specific, actionable fixes. Know exactly how many marks you can recover.</p>
            </div>

            {/* Feature Card 4 */}
            <div className="group bg-white/[0.03] border border-white/5 rounded-2xl p-8 hover:bg-white/[0.06] hover:border-red-500/20 transition-all duration-300">
              <div className="w-12 h-12 rounded-xl bg-red-500/15 flex items-center justify-center mb-5 group-hover:bg-red-500/25 transition-colors">
                <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 21h7a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v11m0 5l4.879-4.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242z" /></svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Evidence-Based Feedback</h3>
              <p className="text-sm text-blue-200/50 leading-relaxed">Every deduction comes with a direct quote from your thesis, pinpointing exactly where the issue was found.</p>
            </div>

            {/* Feature Card 5 */}
            <div className="group bg-white/[0.03] border border-white/5 rounded-2xl p-8 hover:bg-white/[0.06] hover:border-yellow-500/20 transition-all duration-300">
              <div className="w-12 h-12 rounded-xl bg-yellow-500/15 flex items-center justify-center mb-5 group-hover:bg-yellow-500/25 transition-colors">
                <svg className="w-6 h-6 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Supervisor Tone Feedback</h3>
              <p className="text-sm text-blue-200/50 leading-relaxed">Feedback is written in the tone of a calm, experienced university supervisor — professional, supportive, and never harsh.</p>
            </div>

            {/* Feature Card 6 */}
            <div className="group bg-white/[0.03] border border-white/5 rounded-2xl p-8 hover:bg-white/[0.06] hover:border-indigo-500/20 transition-all duration-300">
              <div className="w-12 h-12 rounded-xl bg-indigo-500/15 flex items-center justify-center mb-5 group-hover:bg-indigo-500/25 transition-colors">
                <svg className="w-6 h-6 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Deterministic Scoring</h3>
              <p className="text-sm text-blue-200/50 leading-relaxed">AI detects issues. Python calculates the math. No vague AI percentages — every point is accounted for deterministically.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── HOW IT WORKS ─── */}
      <section id="how-it-works" className="py-24 px-6 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-blue-950/30 to-transparent"></div>
        <div className="relative max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-blue-400 text-sm font-semibold tracking-widest uppercase mb-3">How It Works</p>
            <h2 className="text-3xl md:text-5xl font-bold">Three Simple Steps</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="relative text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center mx-auto mb-6 text-2xl font-bold shadow-lg shadow-blue-500/20">1</div>
              <h3 className="text-xl font-semibold mb-3">Upload</h3>
              <p className="text-blue-200/50 text-sm leading-relaxed">Upload your thesis as a PDF or DOCX file. We securely extract the text for analysis.</p>
            </div>
            <div className="relative text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center mx-auto mb-6 text-2xl font-bold shadow-lg shadow-indigo-500/20">2</div>
              <h3 className="text-xl font-semibold mb-3">AI Analysis</h3>
              <p className="text-blue-200/50 text-sm leading-relaxed">Our AI splits your thesis into sections, identifies issues, and extracts evidence quotes from your text.</p>
            </div>
            <div className="relative text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center mx-auto mb-6 text-2xl font-bold shadow-lg shadow-purple-500/20">3</div>
              <h3 className="text-xl font-semibold mb-3">Get Your Score</h3>
              <p className="text-blue-200/50 text-sm leading-relaxed">Receive a detailed breakdown with rubric-linked deductions, supervisor notes, and a projected improved score.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── RUBRIC ENGINE ─── */}
      <section id="rubric" className="py-24 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-purple-400 text-sm font-semibold tracking-widest uppercase mb-3">Rubric Engine</p>
            <h2 className="text-3xl md:text-5xl font-bold">Graded Against The Official<br/><span className="text-purple-400">NMCN Rubric</span></h2>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { name: "Preliminary Pages", marks: 8, color: "blue" },
              { name: "Chapter One", marks: 15, color: "indigo" },
              { name: "Chapter Two", marks: 12, color: "purple" },
              { name: "Chapter Three", marks: 20, color: "pink" },
              { name: "Chapter Four", marks: 15, color: "red" },
              { name: "Chapter Five", marks: 20, color: "orange" },
              { name: "References & Appendix", marks: 7, color: "yellow" },
              { name: "Typing Instructions", marks: 3, color: "green" },
            ].map((item) => (
              <div key={item.name} className="bg-white/[0.03] border border-white/5 rounded-xl p-5 text-center hover:bg-white/[0.06] transition-all">
                <p className="text-2xl md:text-3xl font-bold mb-1">{item.marks}</p>
                <p className="text-xs text-blue-200/50 uppercase tracking-wider">{item.name}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── WHY THESISAI ─── */}
      <section className="py-24 px-6 border-t border-white/5 bg-slate-900/50">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold">The ThesisAI Advantage</h2>
            <p className="text-blue-200/60 mt-4">Why students and supervisors trust our evaluation engine.</p>
          </div>
          
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02]">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-white/[0.05] border-b border-white/10">
                  <th className="p-6 font-semibold text-blue-300">Feature</th>
                  <th className="p-6 font-semibold text-blue-300">Benefit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-6 font-medium text-white flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-400">🏛️</span>
                    NMCN-Aligned
                  </td>
                  <td className="p-6 text-blue-200/70">Institutional trust — graded exactly how your school grades.</td>
                </tr>
                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-6 font-medium text-white flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center text-indigo-400">🔍</span>
                    Evidence-Based Feedback
                  </td>
                  <td className="p-6 text-blue-200/70">Explainable grading — no "black box" AI hallucinations.</td>
                </tr>
                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-6 font-medium text-white flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-green-500/20 flex items-center justify-center text-green-400">📈</span>
                    Recoverable Marks
                  </td>
                  <td className="p-6 text-blue-200/70">Improvement-focused — know exactly what to fix to score higher.</td>
                </tr>
                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-6 font-medium text-white flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-yellow-500/20 flex items-center justify-center text-yellow-400">👨‍🏫</span>
                    Supervisor Notes
                  </td>
                  <td className="p-6 text-blue-200/70">Humanized evaluation — supportive and professional guidance.</td>
                </tr>
                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-6 font-medium text-white flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center text-purple-400">⚖️</span>
                    Rubric-Aware Scoring
                  </td>
                  <td className="p-6 text-blue-200/70">Transparent deductions — every lost mark is mathematically accounted for.</td>
                </tr>
                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-6 font-medium text-white flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-pink-500/20 flex items-center justify-center text-pink-400">🔄</span>
                    Cross-Section Validation
                  </td>
                  <td className="p-6 text-blue-200/70">Holistic review — ensures your methodology matches your findings.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ─── CTA ─── */}
      <section className="py-24 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <div className="bg-gradient-to-br from-blue-500/10 to-indigo-500/10 border border-blue-500/10 rounded-3xl p-12 md:p-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Ready to Grade Your Thesis?</h2>
            <p className="text-blue-200/60 mb-8 max-w-md mx-auto">Upload your document and get a comprehensive, rubric-based evaluation in under 60 seconds.</p>
            <Link href="/evaluate" className="group inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold text-lg shadow-xl shadow-blue-500/25 hover:shadow-blue-500/40 transition-all hover:scale-105">
              Upload Your Thesis
              <span className="group-hover:translate-x-1 transition-transform">→</span>
            </Link>
          </div>
        </div>
      </section>

      {/* ─── FOOTER ─── */}
      <footer className="border-t border-white/5 py-8 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-sm text-blue-200/30">
            © 2026 <span className="text-blue-400">Thesis</span>AI. All rights reserved.
          </span>
          <div className="flex gap-6 text-xs text-blue-200/30">
            <span>Built for NMCN Standards</span>
            <span>·</span>
            <span>AI-Powered Evaluation</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
