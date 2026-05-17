'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function Results() {
  const [results, setResults] = useState<any>(null);
  const router = useRouter();

  useEffect(() => {
    const savedData = localStorage.getItem('thesisData');
    if (savedData) {
      setResults(JSON.parse(savedData));
    } else {
      router.push('/');
    }
  }, [router]);

  if (!results) {
    return (
      <main className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto space-y-6 animate-pulse">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 flex flex-col md:flex-row items-center justify-between">
            <div className="space-y-3">
              <div className="h-8 w-56 bg-gray-200 rounded"></div>
              <div className="h-4 w-40 bg-gray-100 rounded"></div>
            </div>
            <div className="mt-6 md:mt-0">
              <div className="w-32 h-32 rounded-full bg-gray-200"></div>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 space-y-4">
              <div className="h-6 w-40 bg-gray-200 rounded"></div>
              <div className="h-3 w-full bg-gray-100 rounded"></div>
              <div className="h-3 w-full bg-gray-100 rounded"></div>
              <div className="h-3 w-3/4 bg-gray-100 rounded"></div>
            </div>
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 space-y-4">
              <div className="h-6 w-48 bg-gray-200 rounded"></div>
              <div className="h-16 w-full bg-gray-100 rounded"></div>
              <div className="h-16 w-full bg-gray-100 rounded"></div>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Debug Info */}
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-yellow-700">
                <strong>Debug Info:</strong> Successfully extracted {results.extracted_length?.toLocaleString() || 0} characters from {results.filename}.
              </p>
            </div>
          </div>
        </div>

        {/* Error State */}
        {results.results.error && (
          <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded mb-8">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-500" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Evaluation Failed</h3>
                <div className="mt-2 text-sm text-red-700">
                  <p>{results.results.error}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Header Section */}
        {!results.results.error && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 flex flex-col md:flex-row items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Evaluation Results</h1>
            <p className="text-gray-500 mt-2">Based on the NMCN Grading Rubric</p>
          </div>
          <div className="mt-6 md:mt-0 flex flex-col items-center">
            <div className="relative w-32 h-32 flex items-center justify-center rounded-full border-8 border-green-500">
              <span className="text-4xl font-bold text-gray-800">{results.results.overall_score || 0}%</span>
            </div>
            <span className="mt-2 text-sm font-medium text-green-600">Passed</span>
          </div>
        </div>
        )}

        {/* Grid and Evaluation Content - Only render if no error */}
        {!results.results.error && results.results.breakdown && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Breakdown Section */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
                <h2 className="text-xl font-bold text-gray-900 mb-6">Score Breakdown</h2>
                <div className="space-y-4">
                  {Object.entries(results.results.breakdown).map(([section, data]: [string, any]) => (
                    <div key={section}>
                      <div className="flex justify-between text-sm font-medium text-gray-700 mb-1">
                        <span>{section}</span>
                        <span>{data.score} / {data.max}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2.5">
                        <div 
                          className={`h-2.5 rounded-full ${data.score / data.max > 0.7 ? 'bg-green-500' : 'bg-yellow-500'}`} 
                          style={{ width: `${(data.score / data.max) * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Rubric-Aware Deductions */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
                <h2 className="text-xl font-bold text-gray-900 mb-6">Key Deductions &amp; Evidence</h2>
                <div className="space-y-4">
                  {results.results.deductions?.length > 0 ? (
                    results.results.deductions.map((item: any, index: number) => (
                      <details key={index} className="group bg-gray-50 border border-gray-200 rounded-lg open:bg-white open:ring-1 open:ring-blue-500 transition-all">
                        <summary className="flex items-center justify-between p-4 cursor-pointer font-medium text-gray-900">
                          <div className="flex items-center gap-3 pr-4">
                            <svg className="h-5 w-5 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            <span className="text-sm md:text-base">{item.issue_title || 'Issue'}</span>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            {/* Rubric Badge */}
                            {item.rubric?.section && (
                              <span className="px-2 py-1 text-xs font-semibold rounded-full bg-purple-100 text-purple-700">
                                {item.rubric.section}
                              </span>
                            )}
                            {/* Severity Badge */}
                            {item.severity && (
                              <span className={`px-2 py-1 text-xs font-bold rounded-full ${item.severity === 'high' ? 'bg-red-100 text-red-700' : item.severity === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>
                                {item.severity.toUpperCase()}
                              </span>
                            )}
                            <span className="text-red-500 font-bold text-sm">-{item.deduction}</span>
                            <svg className="h-5 w-5 text-gray-400 group-open:-rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                        </summary>
                        <div className="px-4 pb-4 text-sm text-gray-600 border-t border-gray-100 pt-3 mt-1 space-y-3">
                          {/* Rubric Expectation */}
                          {item.rubric?.expected_requirement && (
                            <div className="bg-purple-50 border-l-4 border-purple-400 p-3 rounded">
                              <p className="text-xs font-bold text-purple-700 mb-1">📋 Rubric Expectation ({item.rubric.section} — {item.rubric.max_marks} marks)</p>
                              <p className="text-purple-900 text-sm">{item.rubric.expected_requirement}</p>
                            </div>
                          )}
                          {/* Why Was This Deducted? */}
                          {item.deduction_reasoning && (
                            <div className="bg-red-50 border-l-4 border-red-300 p-3 rounded">
                              <p className="text-xs font-bold text-red-700 mb-1">❓ Why was this deducted?</p>
                              <p className="text-red-900 text-sm">{item.deduction_reasoning}</p>
                            </div>
                          )}
                          {/* Supervisor Note */}
                          {item.supervisor_note && <p className="text-gray-800"><strong>Supervisor&apos;s Note:</strong> {item.supervisor_note}</p>}
                          {/* Evidence Quote */}
                          {item.evidence?.quote && (
                            <div className="bg-blue-50 border-l-4 border-blue-400 p-3 rounded text-blue-900">
                              <p className="italic">&quot;{item.evidence.quote}&quot;</p>
                              {item.evidence.location && (
                                <p className="text-xs text-blue-700 font-semibold mt-2">📍 Found in: {item.evidence.location}</p>
                              )}
                            </div>
                          )}
                          {/* Suggested Fix + Recoverable Marks */}
                          {item.suggested_fix && (
                            <div className="bg-green-50 border-l-4 border-green-400 p-3 rounded flex justify-between items-start gap-4">
                              <p className="text-green-800 text-sm"><strong>💡 Fix:</strong> {item.suggested_fix}</p>
                              <span className="shrink-0 px-3 py-1 bg-green-600 text-white text-xs font-bold rounded-full">+{item.deduction} marks</span>
                            </div>
                          )}
                        </div>
                      </details>
                    ))
                  ) : (
                    <p className="text-gray-500">No major deductions found!</p>
                  )}
                </div>
              </div>
            </div>

            {/* Superpower: Improve My Score */}
            <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-2xl shadow-lg p-8 text-white mt-8">
              <div className="flex items-center mb-4">
                <span className="text-3xl mr-3">🔥</span>
                <h2 className="text-2xl font-bold">Improve My Score</h2>
              </div>
              <p className="mb-6 opacity-90">To move from {results.results.overall_score}% to {results.results.projected_score || 75}%, fix these specific issues:</p>
              <ul className="space-y-4">
                {results.results.improvements?.map((item: any, index: number) => (
                  <li key={index} className="flex items-start bg-white/10 p-4 rounded-lg">
                    <svg className="h-6 w-6 text-green-300 mr-3 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                      {item.issue_title && <span className="font-bold block mb-1 text-blue-100">{item.issue_title}</span>}
                      <span className="text-blue-50 text-sm md:text-base leading-relaxed block">{item.text || item}</span>
                      {item.marks_recovered && (
                        <span className="text-green-300 text-sm font-bold mt-1 block">Recover +{item.marks_recovered} marks</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* Cross-Section Validation */}
            {results.results.cross_validation?.validations?.length > 0 && (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 mt-8">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">Cross-Section Consistency</h2>
                    <p className="text-sm text-gray-500 mt-1">{results.results.cross_validation.summary}</p>
                  </div>
                  {results.results.cross_validation.total_deductions > 0 && (
                    <span className="px-3 py-1 bg-red-100 text-red-700 text-sm font-bold rounded-full">
                      -{results.results.cross_validation.total_deductions} marks
                    </span>
                  )}
                </div>
                <div className="space-y-3">
                  {results.results.cross_validation.validations.map((v: any, index: number) => (
                    <details key={index} className={`group border rounded-lg transition-all ${v.status === 'pass' ? 'bg-green-50 border-green-200 open:ring-1 open:ring-green-400' : v.status === 'fail' ? 'bg-red-50 border-red-200 open:ring-1 open:ring-red-400' : 'bg-yellow-50 border-yellow-200 open:ring-1 open:ring-yellow-400'}`}>
                      <summary className="flex items-center justify-between p-4 cursor-pointer font-medium text-gray-900">
                        <div className="flex items-center gap-3">
                          <span className="text-lg">{v.status === 'pass' ? '✅' : v.status === 'fail' ? '❌' : '⚠️'}</span>
                          <span className="text-sm md:text-base">{v.rule}</span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className={`px-2 py-1 text-xs font-bold rounded-full ${v.status === 'pass' ? 'bg-green-100 text-green-700' : v.status === 'fail' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>
                            {v.status.toUpperCase()}
                          </span>
                          {v.deduction > 0 && <span className="text-red-500 font-bold text-sm">-{v.deduction}</span>}
                          <svg className="h-5 w-5 text-gray-400 group-open:-rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </summary>
                      <div className="px-4 pb-4 text-sm border-t border-gray-200/50 pt-3 space-y-3">
                        {v.explanation && <p className="text-gray-800">{v.explanation}</p>}
                        {v.evidence?.length > 0 && (
                          <div className="space-y-2">
                            {v.evidence.map((e: any, ei: number) => (
                              <div key={ei} className="bg-white/70 border-l-4 border-blue-400 p-3 rounded">
                                <p className="text-xs font-bold text-blue-700 mb-1">📍 {e.source_section}</p>
                                <p className="text-blue-900 italic text-sm">&quot;{e.quote}&quot;</p>
                              </div>
                            ))}
                          </div>
                        )}
                        {v.suggested_fix && (
                          <p className="text-green-800 bg-green-50 p-3 rounded text-sm"><strong>💡 Fix:</strong> {v.suggested_fix}</p>
                        )}
                      </div>
                    </details>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
        
        <button 
          onClick={() => router.push('/')}
          className="mt-8 bg-blue-600 text-white px-6 py-3 rounded-lg font-bold hover:bg-blue-700 transition-colors"
        >
          Upload New Draft
        </button>

      </div>
    </main>
  );
}
