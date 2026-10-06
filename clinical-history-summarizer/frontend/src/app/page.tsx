"use client";

import { useState } from "react";
import { 
  HeartPulse, 
  Stethoscope, 
  User, 
  FileText, 
  AlertTriangle, 
  CheckCircle2, 
  Info,
  Pill,
  Microscope,
  ListTodo
} from "lucide-react";

const API_URL = "http://localhost:8000";

const EXAMPLE_NOTE = `Pt: E9 / DOB ~1958 / seen 8/10/24

CC - chest pain, onset last night around 10pm. Described as pressure,
7/10, radiates L arm. Had similar episode 6mo ago that "went away on its own".
Diaphoresis present. No syncope.

Pmhx: T2DM (on meds), HTN, ex-smoker (quit ~10yrs ago)

Meds (from patient — not verified against GP records):
metformin - not sure of dose, says "the small ones twice a day"
ramipril 5mg od
amlodipine - patient says 5 or 10mg, not certain

Allergies: says he had a bad reaction to "an antibiotic" years ago
but cannot recall which one or what happened. Nothing in the notes
brought today.

Ix:
Trop I: 0.06 (lab ref <0.04) — HIGH — taken at 03:15
ECG: ST depression V3-V5 (done on arrival)

Plan:
- ACS protocol started
- repeat trop at 0h+3 pending
- cardiology to review`;

export default function Home() {
  const [mode, setMode] = useState<"clinical" | "patient">("clinical");
  const [patientId, setPatientId] = useState("DEMO-001");
  const [notes, setNotes] = useState(EXAMPLE_NOTE);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExtract = async () => {
    if (!notes.trim()) {
      setError("Please paste some clinical notes first.");
      return;
    }
    
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_URL}/extract?mode=${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_notes: notes, patient_id: patientId }),
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || "An error occurred during extraction.");
    } finally {
      setIsLoading(false);
    }
  };

  const renderHighlightedNotes = () => {
    if (!result) return null;
    
    // Collect all cited lines
    const citedLines = new Set<number>();
    const traverse = (obj: any) => {
      if (!obj) return;
      if (typeof obj === 'object') {
        if (obj.line_number !== undefined) citedLines.add(obj.line_number);
        Object.values(obj).forEach(traverse);
      } else if (Array.isArray(obj)) {
        obj.forEach(traverse);
      }
    };
    traverse(result.summary);

    const lines = notes.split('\n');
    return (
      <div className="font-mono text-sm leading-relaxed whitespace-pre-wrap">
        {lines.map((line, idx) => {
          const lineNum = idx + 1;
          const isCited = citedLines.has(lineNum);
          return (
            <div key={lineNum} className={`flex rounded px-1 ${isCited ? 'bg-amber-500/15 text-amber-200' : 'text-slate-300'}`}>
              <span className="w-8 shrink-0 text-slate-500 select-none text-right pr-3">L{lineNum}</span>
              <span>{line}</span>
            </div>
          );
        })}
      </div>
    );
  };

  const getUnverifiedBadge = (fieldKey: string) => {
    if (!result) return null;
    const isUnv = (result.summary.unverified_fields || []).includes(fieldKey);
    if (!isUnv) return null;
    return (
      <span className="ml-2 inline-flex items-center gap-1 bg-rose-500/10 border border-rose-500/30 text-rose-400 text-[10px] font-bold px-2 py-0.5 rounded animate-pulse-red uppercase tracking-wider">
        <AlertTriangle size={12} />
        Unverified
      </span>
    );
  };

  const getCitation = (source: any) => {
    if (!source) return null;
    let text = source.quoted_text;
    if (text.length > 40) text = text.substring(0, 37) + "...";
    return (
      <span className="ml-2 inline-flex items-center text-xs text-teal-400 bg-teal-500/10 px-1.5 py-0.5 rounded italic" title={source.quoted_text}>
        → L{source.line_number}: "{text}"
      </span>
    );
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-50 glass-panel border-x-0 border-t-0 rounded-none px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-teal-500 to-emerald-600 p-2 rounded-xl">
            <HeartPulse className="text-white w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-teal-400 to-emerald-400 bg-clip-text text-transparent">
              Clinical History Summarizer
            </h1>
            <p className="text-xs text-slate-400 font-medium">AI Extraction with Verifiable Citations</p>
          </div>
        </div>

        <div className="flex bg-slate-900/80 p-1 rounded-full border border-white/5">
          <button 
            onClick={() => setMode("clinical")}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium transition-all ${mode === "clinical" ? "bg-teal-600 text-white shadow-lg shadow-teal-500/25" : "text-slate-400 hover:text-white"}`}
          >
            <Stethoscope size={16} /> Clinical
          </button>
          <button 
            onClick={() => setMode("patient")}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium transition-all ${mode === "patient" ? "bg-teal-600 text-white shadow-lg shadow-teal-500/25" : "text-slate-400 hover:text-white"}`}
          >
            <User size={16} /> Patient
          </button>
        </div>
      </header>

      {/* Main Grid */}
      <main className="flex-1 w-full max-w-[1800px] mx-auto p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* LEFT PANEL */}
        <div className="glass-panel flex flex-col h-[calc(100vh-120px)] overflow-hidden">
          <div className="px-6 py-4 border-b border-white/10 flex items-center gap-2">
            <FileText className="text-teal-400" size={20} />
            <h2 className="font-semibold text-lg">Original Notes</h2>
          </div>
          
          <div className="p-6 flex-1 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
            {!result ? (
              <>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Patient ID</label>
                  <input 
                    type="text" 
                    value={patientId}
                    onChange={e => setPatientId(e.target.value)}
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-teal-500 transition-colors"
                  />
                </div>
                
                <div className="space-y-1 flex-1 flex flex-col">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Raw Clinical Notes</label>
                  <textarea 
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    className="w-full flex-1 bg-black/20 border border-white/10 rounded-lg p-4 text-sm font-mono focus:outline-none focus:border-teal-500 transition-colors resize-none custom-scrollbar"
                  />
                </div>
              </>
            ) : (
              <div className="bg-black/20 border border-white/10 rounded-lg p-4 flex-1 overflow-y-auto custom-scrollbar">
                {renderHighlightedNotes()}
              </div>
            )}
          </div>

          <div className="p-6 pt-0">
            {error && <div className="mb-4 text-rose-400 text-sm bg-rose-500/10 p-3 rounded-lg border border-rose-500/20">{error}</div>}
            
            {!result ? (
              <button 
                onClick={handleExtract}
                disabled={isLoading}
                className="w-full bg-teal-600 hover:bg-teal-500 text-white font-semibold py-3 rounded-xl shadow-lg shadow-teal-500/20 transition-all flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                ) : (
                  <>Extract Summary</>
                )}
              </button>
            ) : (
              <button 
                onClick={() => { setResult(null); setError(null); }}
                className="w-full bg-white/5 hover:bg-white/10 text-white font-semibold py-3 rounded-xl border border-white/10 transition-all"
              >
                Start Over
              </button>
            )}
          </div>
        </div>

        {/* RIGHT PANEL */}
        <div className="glass-panel flex flex-col h-[calc(100vh-120px)] overflow-hidden relative">
          <div className="px-6 py-4 border-b border-white/10 flex items-center gap-2">
            <CheckCircle2 className="text-emerald-400" size={20} />
            <h2 className="font-semibold text-lg">Structured Output</h2>
          </div>

          {!result && !isLoading && (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 opacity-60">
              <ListTodo size={64} className="mb-4 text-slate-600" />
              <p>Paste notes on the left and extract.</p>
            </div>
          )}

          {isLoading && (
            <div className="flex-1 flex flex-col items-center justify-center">
              <div className="w-12 h-12 border-4 border-teal-500/20 border-t-teal-500 rounded-full animate-spin mb-4" />
              <p className="text-teal-400 animate-pulse font-medium">Extracting & Verifying Citations...</p>
            </div>
          )}

          {result && (
            <div className="p-6 flex-1 overflow-y-auto custom-scrollbar space-y-6">
              
              {/* Stats Banner */}
              <div className="grid grid-cols-4 gap-4 bg-black/20 p-4 rounded-xl border border-white/5">
                <div className="flex flex-col items-center justify-center">
                  <span className="text-2xl font-bold text-emerald-400">{result.summary_stats.verified_count}</span>
                  <span className="text-[10px] text-slate-400 uppercase tracking-widest mt-1">Verified</span>
                </div>
                <div className="flex flex-col items-center justify-center border-l border-white/5">
                  <span className="text-2xl font-bold text-rose-400">{result.summary_stats.unverified_count}</span>
                  <span className="text-[10px] text-slate-400 uppercase tracking-widest mt-1">Unverified</span>
                </div>
                <div className="flex flex-col items-center justify-center border-l border-white/5">
                  <span className="text-2xl font-bold text-amber-400">{result.summary_stats.missing_count}</span>
                  <span className="text-[10px] text-slate-400 uppercase tracking-widest mt-1">Missing</span>
                </div>
                <div className="flex flex-col items-center justify-center border-l border-white/5">
                  <span className="text-xl font-bold text-slate-200">#{result.stored_summary_id}</span>
                  <span className="text-[10px] text-slate-400 uppercase tracking-widest mt-1">ID</span>
                </div>
              </div>

              {/* Missing Fields Banner */}
              {result.summary.missing_fields?.length > 0 && (
                <div className="bg-teal-500/10 border border-teal-500/30 p-4 rounded-xl flex items-start gap-3">
                  <Info className="text-teal-400 shrink-0 mt-0.5" size={18} />
                  <div>
                    <strong className="text-teal-400 block text-sm mb-1">Not mentioned in notes:</strong>
                    <p className="text-sm text-teal-200/70">
                      {result.summary.missing_fields.map((f: string) => f.replace(/_/g, ' ')).join(', ')}
                    </p>
                  </div>
                </div>
              )}

              {/* Patient Friendly Summary */}
              {result.patient_friendly_summary && (
                <div className="bg-gradient-to-br from-teal-900/40 to-slate-900/40 border-l-4 border-teal-500 p-5 rounded-r-xl border-y border-r border-y-white/5 border-r-white/5">
                  <h3 className="text-sm font-bold text-teal-300 flex items-center gap-2 mb-3">
                    <User size={16} /> Plain-Language Summary
                  </h3>
                  <div className="text-[15px] leading-relaxed text-teal-100/90 whitespace-pre-wrap">
                    {result.patient_friendly_summary}
                  </div>
                </div>
              )}

              {/* Structured Fields */}
              <div className="space-y-6">
                
                {/* 1. DOCUMENTED CONDITIONS */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2 flex items-center gap-2">
                    <HeartPulse size={14} /> Documented Conditions
                  </h3>
                  {result.summary.documented_conditions?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.documented_conditions.map((p: string, i: number) => (
                        <li key={i} className="text-sm flex items-start">
                          <span className="text-slate-500 mr-2">•</span>
                          <div>
                            <span className="font-semibold">{p}</span>
                            {getUnverifiedBadge(`documented_conditions[${i}]`)}
                            {getCitation(result.summary.documented_conditions_sources[i])}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

                {/* 2. CHIEF COMPLAINT */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2">Chief Complaint</h3>
                  {result.summary.chief_complaint ? (
                    <div className="text-sm">
                      <span className="font-semibold">{result.summary.chief_complaint}</span>
                      {getUnverifiedBadge('chief_complaint')}
                      {getCitation(result.summary.chief_complaint_source)}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-500 italic">Not extracted</div>
                  )}
                </section>

                {/* RED FLAGS (Conditional Safety Banner) */}
                {result.summary.red_flags?.length > 0 && (
                  <section className="bg-rose-500/10 border border-rose-500/20 p-4 rounded-xl">
                    <h3 className="text-xs font-bold text-rose-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                      <AlertTriangle size={14} /> Red Flags / Safety
                    </h3>
                    <ul className="space-y-2">
                      {result.summary.red_flags.map((p: string, i: number) => (
                        <li key={i} className="text-sm flex items-start text-rose-200">
                          <span className="text-rose-500/70 mr-2">•</span>
                          <div>
                            <span className="font-semibold">{p}</span>
                            {getUnverifiedBadge(`red_flags[${i}]`)}
                            {getCitation(result.summary.red_flags_sources[i])}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {/* 3. SYMPTOMS */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2">Symptoms</h3>
                  {result.summary.symptoms?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.symptoms.map((p: string, i: number) => (
                        <li key={i} className="text-sm flex items-start">
                          <span className="text-slate-500 mr-2">•</span>
                          <div>
                            <span>{p}</span>
                            {getUnverifiedBadge(`symptoms[${i}]`)}
                            {getCitation(result.summary.symptoms_sources[i])}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

                {/* 4. RELEVANT HISTORY / ASSOCIATED FACTORS */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2">Relevant History / Associated Factors</h3>
                  {result.summary.risk_factors?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.risk_factors.map((p: string, i: number) => (
                        <li key={i} className="text-sm flex items-start">
                          <span className="text-slate-500 mr-2">•</span>
                          <div>
                            <span>{p}</span>
                            {getUnverifiedBadge(`risk_factors[${i}]`)}
                            {getCitation(result.summary.risk_factors_sources[i])}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

                {/* 5. CLINICAL FINDINGS */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2">Clinical Findings</h3>
                  {result.summary.clinical_findings?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.clinical_findings.map((p: string, i: number) => (
                        <li key={i} className="text-sm flex items-start">
                          <span className="text-slate-500 mr-2">•</span>
                          <div>
                            <span>{p}</span>
                            {getUnverifiedBadge(`clinical_findings[${i}]`)}
                            {getCitation(result.summary.clinical_findings_sources[i])}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

                {/* 6. INVESTIGATIONS (Labs) */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2 flex items-center gap-2">
                    <Microscope size={14} /> Investigations
                  </h3>
                  {result.summary.recent_labs?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.recent_labs.map((l: any, i: number) => (
                        <li key={i} className="text-sm flex items-start">
                          <span className="text-slate-500 mr-2">•</span>
                          <div>
                            <span className="font-semibold text-emerald-200">{l.test_name}</span>
                            <span className="text-slate-300 ml-1">: {l.value || '—'}</span>
                            {l.unit && <span className="text-slate-400 ml-1">{l.unit}</span>}
                            {l.abnormality && <span className="text-rose-400 ml-2 uppercase text-[10px] font-bold border border-rose-500/30 px-1 py-0.5 rounded">{l.abnormality}</span>}
                            {l.reference_range && <span className="text-slate-500 ml-2 text-xs">(Ref: {l.reference_range})</span>}
                            {l.date && <span className="text-slate-500 text-xs ml-2">[{l.date}]</span>}
                            {getUnverifiedBadge(`recent_labs[${i}]`)}
                            {getCitation(l.source)}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

                {/* 7. MEDICATIONS */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2 flex items-center gap-2">
                    <Pill size={14} /> Medications
                  </h3>
                  {result.summary.current_medications?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.current_medications.map((m: any, i: number) => {
                        const details = [m.dose, m.route, m.frequency].filter(Boolean).join(" ");
                        return (
                          <li key={i} className="text-sm flex items-start">
                            <span className="text-slate-500 mr-2">•</span>
                            <div>
                              <span className="font-semibold text-teal-200">{m.drug}</span>
                              {details && <span className="text-slate-400 ml-2">&mdash; {details}</span>}
                              {m.status && (
                                <span className="ml-2 bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider border border-white/5">
                                  {m.status}
                                </span>
                              )}
                              {m.uncertainty && <span className="block text-xs text-amber-500 mt-1 italic">Uncertainty: {m.uncertainty}</span>}
                              <div className="mt-1">
                                {getUnverifiedBadge(`current_medications[${i}]`)}
                                {getCitation(m.source)}
                              </div>
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

                {/* 8. ALLERGIES */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2 flex items-center gap-2">
                    <AlertTriangle size={14} /> Allergies
                  </h3>
                  {result.summary.allergies?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.allergies.map((a: any, i: number) => (
                        <li key={i} className="text-sm flex items-start">
                          <span className="text-slate-500 mr-2">•</span>
                          <div>
                            <span className="font-semibold">{a.allergen}</span>
                            {a.reaction && <span className="text-slate-400 ml-2">&mdash; {a.reaction}</span>}
                            {a.status && <span className="text-slate-500 italic ml-2">({a.status})</span>}
                            {getUnverifiedBadge(`allergies[${i}]`)}
                            {getCitation(a.source)}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

                {/* 9. PERTINENT NEGATIVES */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2 flex items-center gap-2">
                    <CheckCircle2 size={14} /> Pertinent Negatives
                  </h3>
                  {result.summary.pertinent_negatives?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.pertinent_negatives.map((p: string, i: number) => (
                        <li key={i} className="text-sm flex items-start text-slate-400">
                          <span className="text-slate-500 mr-2">-</span>
                          <div>
                            <span>{p}</span>
                            {getUnverifiedBadge(`pertinent_negatives[${i}]`)}
                            {getCitation(result.summary.pertinent_negatives_sources[i])}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

                {/* 10. CLINICAL IMPRESSION */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2">Clinical Impression</h3>
                  {result.summary.clinical_impression ? (
                    <div className="text-sm text-amber-100">
                      <span className="font-semibold">{result.summary.clinical_impression}</span>
                      {getUnverifiedBadge('clinical_impression')}
                      {getCitation(result.summary.clinical_impression_source)}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-500 italic">Not extracted</div>
                  )}
                </section>

                {/* 11. DIFFERENTIAL DIAGNOSES */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2 flex items-center gap-2">
                    <ListTodo size={14} /> Differential Diagnoses
                  </h3>
                  {result.summary.differential_diagnoses?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.differential_diagnoses.map((p: string, i: number) => (
                        <li key={i} className="text-sm flex items-start">
                          <span className="text-slate-500 mr-2">•</span>
                          <div>
                            <span className="font-medium text-slate-300">{p}</span>
                            {getUnverifiedBadge(`differential_diagnoses[${i}]`)}
                            {getCitation(result.summary.differential_diagnoses_sources[i])}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

                {/* 12. PLAN / FOLLOW-UP */}
                <section>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 border-b border-white/10 pb-2">Plan / Follow-up</h3>
                  {result.summary.pending_items?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.pending_items.map((p: string, i: number) => (
                        <li key={i} className="text-sm flex items-start">
                          <span className="text-slate-500 mr-2">•</span>
                          <div>
                            <span>{p}</span>
                            {getUnverifiedBadge(`pending_items[${i}]`)}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

                {/* 13. UNCERTAINTIES / VERIFICATION REQUIRED */}
                <section className={result.summary.uncertainties?.length > 0 ? "bg-amber-500/5 border border-amber-500/20 p-4 rounded-xl mt-6" : ""}>
                  <h3 className={`text-xs font-bold uppercase tracking-widest mb-3 flex items-center gap-2 ${result.summary.uncertainties?.length > 0 ? 'text-amber-500' : 'text-slate-400 border-b border-white/10 pb-2'}`}>
                    <AlertTriangle size={14} /> Uncertainties / Verification Required
                  </h3>
                  {result.summary.uncertainties?.length > 0 ? (
                    <ul className="space-y-2">
                      {result.summary.uncertainties.map((p: string, i: number) => (
                        <li key={i} className="text-sm flex items-start text-amber-200/80">
                          <span className="text-amber-500/50 mr-2">•</span>
                          <div>
                            <span>{p}</span>
                            {getUnverifiedBadge(`uncertainties[${i}]`)}
                            {getCitation(result.summary.uncertainties_sources[i])}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 italic">None extracted</div>
                  )}
                </section>

              </div>
            </div>
          )}
        </div>

      </main>
    </div>
  );
}
