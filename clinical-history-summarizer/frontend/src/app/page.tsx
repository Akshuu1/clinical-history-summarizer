"use client";

import { useState, useRef, useMemo } from "react";
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
  ListTodo,
  UploadCloud,
  X,
  Sparkles,
  Trash2,
  Copy,
  Download,
  Printer,
  Search,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
  Activity,
  ArrowRight,
  Eye,
  Edit3,
  BookmarkCheck,
  RefreshCw,
  Clock,
  Layers,
  FileCheck,
  Zap,
  HelpCircle,
  CalendarCheck,
  AlertOctagon,
  Sparkle,
  Compass,
  ClipboardList
} from "lucide-react";

const API_URL = "http://localhost:8000";

export default function Home() {
  // Input State
  const [patientId, setPatientId] = useState("");
  const [notes, setNotes] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadFileName, setUploadFileName] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // UI Navigation & Workstation States
  const [viewMode, setViewMode] = useState<"patient" | "clinical">("patient");
  const [leftTab, setLeftTab] = useState<"editor" | "inspector">("editor");
  const [rightTab, setRightTab] = useState<"overview" | "findings" | "meds_labs" | "safety" | "all">("overview");
  const [searchTerm, setSearchTerm] = useState("");
  const [activeCitedLine, setActiveCitedLine] = useState<number | null>(null);
  const [activeQuotedText, setActiveQuotedText] = useState<string | null>(null);
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [agenticMode, setAgenticMode] = useState(true);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 3200);
  };

  const toggleSection = (id: string) => {
    setCollapsedSections(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const handleFileUpload = async (file: File) => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setUploadFileName(file.name);

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (patientId.trim()) {
        formData.append("patient_id", patientId.trim());
      }

      const res = await fetch(`${API_URL}/upload-prescription`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${res.status}`);
      }

      const data = await res.json();
      setNotes(data.raw_notes || "");
      if (data.patient_id && !patientId.trim()) {
        setPatientId(data.patient_id);
      }
      setLeftTab("editor");
      showToast(`Transcribed ${file.name}`);
    } catch (err: any) {
      setError(err.message || "Failed to transcribe uploaded prescription.");
      setUploadFileName(null);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleExtract = async () => {
    if (!notes.trim()) {
      setError("Please drop a prescription or paste clinical notes first.");
      return;
    }
    
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const endpoint = agenticMode ? `${API_URL}/extract-agentic` : `${API_URL}/extract`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          raw_notes: notes, 
          patient_id: patientId.trim() || "PT-" + Math.floor(1000 + Math.random() * 9000) 
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
      setLeftTab("inspector");
      showToast("Clinical summary generated successfully.");
    } catch (err: any) {
      setError(err.message || "An error occurred during extraction.");
    } finally {
      setIsLoading(false);
    }
  };

  const jumpToCitation = (lineNum: number, quote: string) => {
    setActiveCitedLine(lineNum);
    setActiveQuotedText(quote);
    setLeftTab("inspector");

    setTimeout(() => {
      const el = document.getElementById(`source-line-${lineNum}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 100);

    showToast(`Focused on Line ${lineNum}`);
  };

  const handleCopySummary = () => {
    if (!result) return;
    const s = result.summary;
    let md = `# Patient Clinical Summary\n`;
    md += `Patient Identifier: ${result.summary.patient_id || patientId || "N/A"}\n\n`;

    if (s.narrative_summary) {
      md += `## Plain-Language Summary\n${s.narrative_summary}\n\n`;
    }
    if (s.current_medications?.length > 0) {
      md += `## Medications\n`;
      s.current_medications.forEach((m: any) => {
        const det = [m.dose, m.route, m.frequency].filter(Boolean).join(", ");
        md += `- **${m.drug}**: ${det || "Dose as directed"}${m.status ? ` [${m.status}]` : ""}${m.duration ? ` (Duration: ${m.duration})` : ""}\n`;
      });
      md += `\n`;
    }
    if (s.doctor_recommendations?.length > 0) {
      md += `## Doctor-Documented Plan\n`;
      s.doctor_recommendations.forEach((r: string) => { md += `→ ${r}\n`; });
      md += `\n`;
    }
    if (s.ai_recommendations?.length > 0) {
      md += `## AI-Suggested Next Steps (Not Documented as Prescribed)\n`;
      s.ai_recommendations.forEach((r: any) => {
        md += `- [${(r.priority || "routine").toUpperCase()}] ${r.recommendation} — Reason: ${r.reason}. Timing: ${r.timing}. Caveat: ${r.caveat || "Clinician judgment required"}\n`;
      });
      md += `\n`;
    }
    if (s.red_flags?.length > 0) {
      md += `## Urgent Concerns & Safety-Net\n`;
      s.red_flags.forEach((f: string) => { md += `- ${f}\n`; });
      md += `\n`;
    }

    navigator.clipboard.writeText(md).then(() => {
      showToast("Summary copied to clipboard.");
    });
  };

  const handleExportJSON = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `clinical_summary_${result.summary.patient_id || "report"}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("JSON report downloaded.");
  };

  const handleExportFHIR = async () => {
    if (!result?.summary?.patient_id) return;
    try {
      const res = await fetch(`${API_URL}/summary/${result.summary.patient_id}/fhir`);
      if (!res.ok) throw new Error("Failed to export FHIR");
      const fhirData = await res.json();
      const blob = new Blob([JSON.stringify(fhirData, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fhir_r4_bundle_${result.summary.patient_id}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("FHIR R4 Bundle downloaded.");
    } catch {
      showToast("Could not export FHIR bundle.");
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const citedLinesMap = useMemo(() => {
    const map = new Map<number, string[]>();
    if (!result) return map;

    const addCitation = (source: any, label: string) => {
      if (source && source.line_number !== undefined) {
        const list = map.get(source.line_number) || [];
        list.push(label);
        map.set(source.line_number, list);
      }
    };

    const s = result.summary;
    if (s.chief_complaint_source) addCitation(s.chief_complaint_source, "Chief Complaint");
    if (s.clinical_impression_source) addCitation(s.clinical_impression_source, "Impression");
    s.documented_conditions_sources?.forEach((src: any) => addCitation(src, "Condition"));
    s.symptoms_sources?.forEach((src: any) => addCitation(src, "Symptom"));
    s.clinical_findings?.forEach((f: any) => {
      if (f?.source) addCitation(f.source, "Finding");
    });
    s.clinical_findings_sources?.forEach((src: any) => addCitation(src, "Finding"));
    s.pertinent_negatives_sources?.forEach((src: any) => addCitation(src, "Negative"));
    s.risk_factors_sources?.forEach((src: any) => addCitation(src, "Risk"));
    s.differential_diagnoses_sources?.forEach((src: any) => addCitation(src, "Differential"));
    s.red_flags_sources?.forEach((src: any) => addCitation(src, "Red Flag"));
    s.current_medications?.forEach((m: any) => addCitation(m.source, `Med (${m.drug})`));
    s.recent_labs?.forEach((l: any) => addCitation(l.source, `Lab (${l.test_name})`));
    s.allergies?.forEach((a: any) => addCitation(a.source, `Allergy (${a.allergen})`));
    s.uncertainties_sources?.forEach((src: any) => addCitation(src, "Uncertainty"));

    return map;
  }, [result]);

  const noteMetrics = useMemo(() => {
    const lines = notes.split("\n");
    const words = notes.trim() ? notes.trim().split(/\s+/).length : 0;
    return {
      lines: lines.length,
      words: words,
      chars: notes.length
    };
  }, [notes]);

  const renderCitationBadge = (source: any) => {
    if (!source || !source.line_number) return null;
    let snippet = source.quoted_text || "";
    if (snippet.length > 32) snippet = snippet.substring(0, 29) + "...";
    const isTarget = activeCitedLine === source.line_number;

    return (
      <button 
        type="button"
        onClick={() => jumpToCitation(source.line_number, source.quoted_text)}
        className={`inline-flex items-center gap-1.5 text-[11px] font-mono px-2 py-0.5 rounded-md border transition-all cursor-pointer ${
          isTarget 
            ? "bg-indigo-600 text-white border-indigo-400 shadow-sm" 
            : "bg-zinc-800/80 text-zinc-300 hover:text-white border-zinc-700/80 hover:border-zinc-500"
        }`}
        title={`Line ${source.line_number}: "${source.quoted_text}"`}
      >
        <span className="font-semibold text-indigo-400">L{source.line_number}</span>
        <span className="opacity-70 font-normal max-w-[120px] truncate hidden sm:inline">&ldquo;{snippet}&rdquo;</span>
      </button>
    );
  };

  const renderUnverifiedBadge = (fieldKey: string) => {
    if (!result) return null;
    const isUnv = (result.summary.unverified_fields || []).includes(fieldKey);
    if (!isUnv) return null;
    return (
      <span 
        className="ml-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border border-rose-500/40 bg-rose-500/10 text-rose-400"
        title="Unverified against source line"
      >
        <AlertTriangle size={11} className="stroke-[2.5]" />
        Verify
      </span>
    );
  };

  const renderDrugIntelligenceCard = () => {
    if (!result?.drug_intelligence) return null;
    const di = result.drug_intelligence;
    const hasAlerts = (di.high_severity_count || 0) > 0 || (di.moderate_severity_count || 0) > 0;
    if (!hasAlerts && !di.dose_alerts?.length && !di.contraindications?.length && !di.allergy_conflicts?.length) return null;

    return (
      <div className="glass-card p-6 md:p-8 space-y-5 border-rose-500/25 bg-rose-950/10">
        <div className="flex items-center justify-between gap-4 border-b border-rose-500/15 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-rose-500/15 text-rose-400 border border-rose-500/30">
              <ShieldAlert size={20} className="stroke-[2]" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-rose-300">
                Drug Safety Intelligence
              </h3>
              <p className="text-xs text-zinc-400">Rule-based pharmacotherapy safety radar</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {di.high_severity_count > 0 && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium border border-rose-500/50 bg-rose-500/20 text-rose-300">
                {di.high_severity_count} High Risk
              </span>
            )}
            {di.moderate_severity_count > 0 && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium border border-amber-500/50 bg-amber-500/20 text-amber-300">
                {di.moderate_severity_count} Moderate
              </span>
            )}
          </div>
        </div>

        <div className="space-y-3 pt-1">
          {di.drug_interactions?.map((ddi: any, i: number) => (
            <div key={i} className={`p-4 rounded-xl border ${ddi.severity === "HIGH" ? "border-rose-500/40 bg-rose-500/5" : "border-amber-500/40 bg-amber-500/5"}`}>
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded ${ddi.severity === "HIGH" ? "bg-rose-500 text-black" : "bg-amber-500 text-black"}`}>
                  {ddi.severity} Interaction
                </span>
                <span className="text-sm font-semibold text-white">{ddi.drug_a}</span>
                <span className="text-zinc-500">+</span>
                <span className="text-sm font-semibold text-white">{ddi.drug_b}</span>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed">{ddi.explanation}</p>
              {ddi.action && <p className="text-xs text-indigo-400 font-medium mt-1.5">Action: {ddi.action}</p>}
            </div>
          ))}

          {di.allergy_conflicts?.map((ac: any, i: number) => (
            <div key={i} className="p-4 rounded-xl border border-rose-500/40 bg-rose-500/5">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-rose-500 text-black">
                  Allergy Conflict
                </span>
                <span className="text-sm font-semibold text-white">Allergen: {ac.allergen}</span>
                <span className="text-zinc-500">&rarr;</span>
                <span className="text-sm font-semibold text-white">Drug: {ac.conflicting_drug}</span>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed">{ac.explanation}</p>
            </div>
          ))}

          {di.contraindications?.map((ci: any, i: number) => (
            <div key={i} className={`p-4 rounded-xl border ${ci.severity === "HIGH" ? "border-rose-500/40 bg-rose-500/5" : "border-amber-500/40 bg-amber-500/5"}`}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded ${ci.severity === "HIGH" ? "bg-rose-500 text-black" : "bg-amber-500 text-black"}`}>
                  {ci.severity} Contraindication
                </span>
                <span className="text-sm font-semibold text-white">{ci.drug}</span>
                <span className="text-xs text-zinc-400">with {ci.condition}</span>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed">{ci.explanation}</p>
            </div>
          ))}

          {di.dose_alerts?.map((da: any, i: number) => (
            <div key={i} className="p-4 rounded-xl border border-amber-500/40 bg-amber-500/5">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-amber-500 text-black">
                  Dose Warning ({da.is_high ? "High" : "Low"})
                </span>
                <span className="text-sm font-semibold text-white">{da.drug}</span>
              </div>
              <p className="text-xs text-zinc-300 mt-1">
                Prescribed: <strong className="text-white">{da.prescribed_dose}</strong> &bull; Expected standard: <strong className="text-zinc-200">{da.expected_range}</strong>
              </p>
              {da.note && <p className="text-xs text-zinc-400 mt-1 italic">{da.note}</p>}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderMissingInfoCard = () => {
    if (!result?.clinical_decision_support?.missing_info?.length) return null;
    return (
      <div className="glass-card p-6 md:p-8 space-y-4 border-amber-500/25 bg-amber-950/10">
        <div className="flex items-center gap-3 border-b border-amber-500/15 pb-4">
          <div className="p-2 rounded-xl bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <HelpCircle size={20} className="stroke-[2]" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-amber-300">
              Missing Critical Information
            </h3>
            <p className="text-xs text-zinc-400">Important clinical details not documented in source</p>
          </div>
        </div>
        <ul className="space-y-2.5 pt-1">
          {result.clinical_decision_support.missing_info.map((m: any, i: number) => (
            <li key={i} className="flex items-start gap-3 text-sm bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
              <span className="text-amber-400 font-semibold shrink-0">&bull;</span>
              <div>
                <span className="font-medium text-zinc-200">{m.missing_item}</span>
                <p className="text-xs text-zinc-400 mt-0.5 leading-relaxed">{m.why_important}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    );
  };

  const renderClinicalPearlsCard = () => {
    if (!result?.clinical_decision_support?.clinical_pearls?.length) return null;
    return (
      <div className="glass-card p-6 md:p-8 space-y-4 border-indigo-500/25 bg-indigo-950/10">
        <div className="flex items-center gap-3 border-b border-indigo-500/15 pb-4">
          <div className="p-2 rounded-xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
            <Sparkles size={20} className="stroke-[2]" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-indigo-300">Clinical Insights</h3>
            <p className="text-xs text-zinc-400">Evidence-based guidelines & practice pearls</p>
          </div>
        </div>
        <ul className="space-y-2.5 pt-1">
          {result.clinical_decision_support.clinical_pearls.map((p: string, i: number) => (
            <li key={i} className="text-sm text-zinc-300 bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800 leading-relaxed">
              {p}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  const renderDocumentInspector = () => {
    if (!notes.trim()) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-zinc-500 py-16">
          <FileText size={44} className="mb-3 text-zinc-600 opacity-50" />
          <p className="text-sm font-medium">No prescription or notes loaded yet.</p>
        </div>
      );
    }

    const lines = notes.split("\n");
    return (
      <div className="space-y-1 font-mono text-xs">
        {lines.map((line, idx) => {
          const lineNum = idx + 1;
          const isTarget = activeCitedLine === lineNum;
          const citations = citedLinesMap.get(lineNum);
          const isCited = Boolean(citations && citations.length > 0);

          return (
            <div 
              key={lineNum}
              id={`source-line-${lineNum}`}
              className={`flex items-start rounded-lg px-3 py-1.5 transition-all group ${
                isTarget 
                  ? "citation-active-target bg-indigo-500/15 text-white font-medium" 
                  : isCited 
                  ? "bg-zinc-900/70 text-zinc-200 border-l-2 border-indigo-500/80" 
                  : "text-zinc-400 hover:bg-zinc-900/40"
              }`}
            >
              <div className="w-12 shrink-0 flex items-center justify-between pr-2 text-zinc-500 select-none">
                <span className={`text-[10px] ${isTarget ? "text-indigo-400 font-bold" : isCited ? "text-indigo-400 font-medium" : ""}`}>
                  L{lineNum}
                </span>
                {isCited && (
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" title={`Cited by: ${citations?.join(", ")}`} />
                )}
              </div>
              
              <div className="flex-1 whitespace-pre-wrap break-words leading-relaxed pl-1 font-mono">
                {line || <span className="opacity-20 select-none">&nbsp;</span>}
              </div>

              {citations && citations.length > 0 && (
                <div className="hidden group-hover:flex shrink-0 items-center gap-1 pl-2">
                  <span className="text-[10px] font-medium bg-zinc-800 text-indigo-300 border border-zinc-700 px-1.5 py-0.5 rounded">
                    {citations[0]} {citations.length > 1 ? `+${citations.length - 1}` : ""}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="flex flex-col min-h-screen text-zinc-100 selection:bg-indigo-500 selection:text-white">
      
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 bg-zinc-900/90 backdrop-blur-xl text-zinc-100 border border-zinc-700 px-4 py-3 rounded-xl shadow-lg text-sm">
          <Sparkles size={16} className="text-indigo-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 bg-zinc-950/80 backdrop-blur-xl border-b border-zinc-800/80 px-6 lg:px-12 py-4 flex flex-wrap items-center justify-between gap-4">
        
        {/* Brand */}
        <div className="flex items-center gap-3.5">
          <div className="p-2 rounded-xl bg-indigo-600/15 border border-indigo-500/30 text-indigo-400">
            <HeartPulse className="w-5 h-5 stroke-[2]" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-lg font-semibold tracking-tight text-white">
                ANM Clinical Intelligence
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-zinc-700 bg-zinc-800/80 text-zinc-300">
                Precision Engine
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              Deterministic Citation Grounding &bull; Strict Doctor vs AI Plan Separation
            </p>
          </div>
        </div>

        {/* View Switcher & Action Buttons */}
        <div className="flex items-center gap-3">
          {/* Segmented View Mode Switcher */}
          <div className="flex items-center p-1 rounded-xl bg-zinc-900 border border-zinc-800">
            <button 
              onClick={() => setViewMode("patient")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                viewMode === "patient"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              Patient View
            </button>
            <button 
              onClick={() => setViewMode("clinical")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                viewMode === "clinical"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              Clinical Workstation
            </button>
          </div>

          {result && (
            <button 
              onClick={() => {
                setResult(null);
                setError(null);
                setActiveCitedLine(null);
                setActiveQuotedText(null);
                showToast("Cleared results.");
              }}
              className="bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white font-medium text-xs px-3 py-2 rounded-xl border border-zinc-800 flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <RefreshCw size={13} />
              <span>Reset</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Workspace Layout */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-6 py-8 md:px-10 md:py-10 space-y-10">
        
        {/* Top Controls Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* ======================================================== */}
          {/* LEFT: Clinical Source Ingestion & Radar                 */}
          {/* ======================================================== */}
          <div className="lg:col-span-5 flex flex-col glass-card overflow-hidden">
            
            {/* Header Tabs */}
            <div className="px-5 py-3 border-b border-zinc-800/80 flex items-center justify-between bg-zinc-950/40">
              <div className="flex items-center gap-1 bg-zinc-900/80 p-0.5 rounded-lg border border-zinc-800">
                <button 
                  onClick={() => setLeftTab("editor")}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
                    leftTab === "editor"
                      ? "bg-zinc-800 text-white shadow-sm"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  <Edit3 size={13} />
                  <span>Clinical Notes</span>
                </button>
                
                <button 
                  onClick={() => setLeftTab("inspector")}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
                    leftTab === "inspector"
                      ? "bg-zinc-800 text-white shadow-sm"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  <Layers size={13} />
                  <span>Line Radar</span>
                  {citedLinesMap.size > 0 && (
                    <span className="ml-1 text-[10px] font-mono px-1.5 rounded-full bg-indigo-500/20 text-indigo-300">
                      {citedLinesMap.size}
                    </span>
                  )}
                </button>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-zinc-500 hidden sm:inline">
                  {noteMetrics.lines}L &bull; {noteMetrics.words}W
                </span>
                {notes && (
                  <button 
                    onClick={() => {
                      setNotes("");
                      setUploadFileName(null);
                      setPatientId("");
                      setResult(null);
                      setActiveCitedLine(null);
                    }}
                    className="p-1.5 text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors cursor-pointer"
                    title="Clear notes"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>

            {/* Active Citation Focus Notification */}
            {activeCitedLine && (
              <div className="bg-indigo-950/40 border-b border-indigo-500/20 px-4 py-2 flex items-center justify-between text-xs text-indigo-200">
                <div className="flex items-center gap-2 truncate">
                  <BookmarkCheck size={14} className="text-indigo-400 shrink-0" />
                  <span>
                    Referenced line <strong className="text-white">L{activeCitedLine}</strong>:
                    <span className="opacity-80 ml-1 truncate font-mono">
                      &ldquo;{activeQuotedText}&rdquo;
                    </span>
                  </span>
                </div>
                <button 
                  onClick={() => {
                    setActiveCitedLine(null);
                    setActiveQuotedText(null);
                  }}
                  className="p-1 text-zinc-400 hover:text-white cursor-pointer"
                >
                  <X size={12} />
                </button>
              </div>
            )}

            {/* Left Panel Body */}
            <div className="p-6 flex-1 flex flex-col gap-5 overflow-y-auto custom-scrollbar">
              
              {leftTab === "editor" ? (
                <>
                  {/* File Dropzone */}
                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    onChange={e => e.target.files && e.target.files[0] && handleFileUpload(e.target.files[0])} 
                    accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.md" 
                    className="hidden" 
                  />

                  <div 
                    onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleDrop}
                    onClick={() => !isUploading && fileInputRef.current?.click()}
                    className={`border border-dashed rounded-xl p-5 transition-all cursor-pointer flex flex-col items-center justify-center text-center ${
                      isDragging 
                        ? 'border-indigo-500 bg-indigo-500/10' 
                        : isUploading 
                        ? 'border-amber-500/60 bg-amber-500/5 cursor-wait' 
                        : uploadFileName 
                        ? 'border-indigo-500/60 bg-indigo-500/5' 
                        : 'border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/50 bg-zinc-900/30'
                    }`}
                  >
                    {isUploading ? (
                      <div className="flex items-center gap-3 py-1">
                        <div className="w-5 h-5 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
                        <div className="text-left">
                          <p className="text-sm font-medium text-amber-300">Processing prescription...</p>
                          <p className="text-xs text-zinc-400">Transcribing notes using vision OCR</p>
                        </div>
                      </div>
                    ) : uploadFileName ? (
                      <div className="flex items-center justify-between w-full px-2">
                        <div className="flex items-center gap-3 truncate">
                          <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                          <div className="text-left truncate">
                            <p className="text-sm font-medium text-zinc-200 truncate">{uploadFileName}</p>
                            <p className="text-xs text-zinc-400">Ready for structured extraction</p>
                          </div>
                        </div>
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            setUploadFileName(null);
                            if (fileInputRef.current) fileInputRef.current.value = "";
                          }}
                          className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg transition-colors cursor-pointer"
                        >
                          <X size={15} />
                        </button>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-2 py-1">
                        <UploadCloud size={20} className="text-zinc-500" />
                        <p className="text-xs text-zinc-300 font-medium">
                          Upload Prescription or Clinical Note
                        </p>
                        <p className="text-[11px] text-zinc-500">
                          PDF, image (PNG/JPG), or text file
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Patient Identifier */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-400 flex items-center justify-between">
                      <span>Patient Identifier</span>
                      <span className="text-[10px] text-zinc-500 font-normal">Optional</span>
                    </label>
                    <input 
                      type="text" 
                      value={patientId}
                      placeholder="e.g. Ramesh Kumar or PT-10492"
                      onChange={e => setPatientId(e.target.value)}
                      className="w-full bg-zinc-900/60 border border-zinc-800 rounded-xl px-3.5 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-indigo-500/70 transition-colors"
                    />
                  </div>

                  {/* Clinical Text Area */}
                  <div className="space-y-1.5 flex-1 flex flex-col min-h-[260px]">
                    <label className="text-xs font-medium text-zinc-400">
                      Source Clinical Notes
                    </label>
                    <textarea 
                      value={notes}
                      onChange={e => setNotes(e.target.value)}
                      placeholder="Paste doctor notes, consultation transcripts, or discharge summary here..."
                      className="w-full flex-1 bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 text-xs font-mono text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-indigo-500/70 transition-colors resize-none custom-scrollbar leading-relaxed"
                    />
                  </div>
                </>
              ) : (
                /* Line Radar */
                <div className="flex-1 overflow-y-auto custom-scrollbar">
                  {renderDocumentInspector()}
                </div>
              )}

            </div>

            {/* Bottom Ingestion Footer */}
            <div className="p-5 border-t border-zinc-800/80 bg-zinc-950/40 space-y-3">
              {error && (
                <div className="text-xs text-rose-300 bg-rose-500/10 border border-rose-500/30 p-3 rounded-xl flex items-start gap-2">
                  <AlertTriangle size={15} className="text-rose-400 shrink-0 mt-0.5" />
                  <span className="leading-relaxed">{error}</span>
                </div>
              )}
              
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${agenticMode ? "bg-indigo-400" : "bg-zinc-600"}`} />
                  <span className="text-zinc-300 font-medium">Multi-Pass Self-Correction</span>
                </div>
                <button
                  type="button"
                  onClick={() => setAgenticMode(prev => !prev)}
                  className={`px-2 py-0.5 rounded text-[10px] uppercase font-mono font-medium border transition-all cursor-pointer ${
                    agenticMode 
                      ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40"
                      : "bg-zinc-800 text-zinc-400 border-zinc-700"
                  }`}
                >
                  {agenticMode ? "Enabled" : "Off"}
                </button>
              </div>

              <button 
                onClick={handleExtract}
                disabled={isLoading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm py-3 px-4 rounded-xl transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-sm"
              >
                {isLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Extracting & Validating Citations...</span>
                  </>
                ) : (
                  <>
                    <Zap size={16} />
                    <span>Run Precision Clinical Extraction</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* ======================================================== */}
          {/* RIGHT: Structured Output & Workstation                  */}
          {/* ======================================================== */}
          <div className="lg:col-span-7 flex flex-col space-y-6">
            
            {/* Empty State */}
            {!result && !isLoading && (
              <div className="glass-card flex flex-col items-center justify-center text-center p-16 space-y-4">
                <div className="p-4 rounded-2xl bg-zinc-900 border border-zinc-800 text-zinc-500">
                  <Compass size={36} />
                </div>
                <div className="space-y-1.5 max-w-md">
                  <h3 className="text-base font-semibold text-zinc-200">Awaiting Clinical Encounter</h3>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    Paste consultation notes or upload a prescription file on the left to extract structured clinical data and generate verified summaries.
                  </p>
                </div>
              </div>
            )}

            {/* Loading State */}
            {isLoading && (
              <div className="glass-card flex flex-col items-center justify-center text-center p-16 space-y-4">
                <div className="w-10 h-10 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
                <div className="space-y-1">
                  <p className="text-sm font-medium text-zinc-200">Executing Grounded Clinical Analysis...</p>
                  <p className="text-xs text-zinc-400 font-mono">Verifying line citations, normalizing RxNorm / LOINC, separating doctor plan</p>
                </div>
              </div>
            )}

            {/* Populated Result View */}
            {result && (
              <div className="space-y-6">
                
                {/* Metric Strip */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="glass-card p-4 flex items-center justify-between">
                    <div>
                      <div className="text-xl font-semibold text-white">{result.summary.current_medications?.length || 0}</div>
                      <div className="text-[11px] text-zinc-400">Medications</div>
                    </div>
                    <Pill size={18} className="text-indigo-400" />
                  </div>

                  <div className="glass-card p-4 flex items-center justify-between">
                    <div>
                      <div className="text-xl font-semibold text-white">{result.summary.recent_labs?.length || 0}</div>
                      <div className="text-[11px] text-zinc-400">Investigations</div>
                    </div>
                    <Microscope size={18} className="text-sky-400" />
                  </div>

                  <div className="glass-card p-4 flex items-center justify-between">
                    <div>
                      <div className={`text-xl font-semibold ${result.summary.red_flags?.length > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                        {result.summary.red_flags?.length || 0}
                      </div>
                      <div className="text-[11px] text-zinc-400">Urgent Signs</div>
                    </div>
                    <AlertOctagon size={18} className={result.summary.red_flags?.length > 0 ? "text-rose-400" : "text-emerald-400"} />
                  </div>

                  <div className="glass-card p-4 flex items-center justify-between">
                    <div>
                      <div className="text-xl font-semibold text-emerald-400">{result.summary_stats.verified_count}</div>
                      <div className="text-[11px] text-zinc-400">Verified Citations</div>
                    </div>
                    <CheckCircle2 size={18} className="text-emerald-400" />
                  </div>
                </div>

                {/* Urgency Score Card */}
                {result?.clinical_decision_support?.urgency && (
                  <div className="glass-card p-4 px-5 flex items-center justify-between gap-4 border-indigo-500/20 bg-indigo-950/10">
                    <div className="flex items-center gap-3">
                      <div className="text-xl font-bold text-indigo-400">
                        {result.clinical_decision_support.urgency.level}/5
                      </div>
                      <div>
                        <div className="text-xs uppercase font-medium tracking-wide text-zinc-300">
                          {result.clinical_decision_support.urgency.label} Urgency Level
                        </div>
                        <p className="text-xs text-zinc-400 mt-0.5">
                          {result.clinical_decision_support.urgency.clinical_context}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {result.clinical_decision_support.urgency.reasons?.slice(0, 2).map((r: string, i: number) => (
                        <span key={i} className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">
                          {r}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Action Export Buttons */}
                <div className="flex items-center justify-end gap-2 text-xs">
                  <button 
                    onClick={handleCopySummary}
                    className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 hover:text-white flex items-center gap-1.5 transition-all cursor-pointer"
                  >
                    <Copy size={13} />
                    <span>Copy</span>
                  </button>
                  <button 
                    onClick={handleExportJSON}
                    className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 hover:text-white flex items-center gap-1.5 transition-all cursor-pointer"
                  >
                    <Download size={13} />
                    <span>JSON</span>
                  </button>
                  <button 
                    onClick={handleExportFHIR}
                    className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 hover:text-white flex items-center gap-1.5 transition-all cursor-pointer"
                  >
                    <Activity size={13} />
                    <span>FHIR R4</span>
                  </button>
                  <button 
                    onClick={handlePrint}
                    className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 hover:text-white flex items-center gap-1.5 transition-all cursor-pointer"
                  >
                    <Printer size={13} />
                    <span>Print</span>
                  </button>
                </div>

                {/* ========================================================== */}
                {/* MODE A: PATIENT-FRIENDLY VIEW                              */}
                {/* ========================================================== */}
                {viewMode === "patient" && (
                  <div className="space-y-6">
                    
                    {/* 1. NARRATIVE PATIENT SUMMARY */}
                    <div className="glass-card p-6 md:p-8 space-y-4">
                      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                            <Sparkle size={18} />
                          </div>
                          <div>
                            <h3 className="text-base font-semibold text-white">
                              Patient Health Summary
                            </h3>
                            <p className="text-xs text-zinc-400">Written in plain language for you and your family</p>
                          </div>
                        </div>
                        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium border border-zinc-700 bg-zinc-800/80 text-zinc-300">
                          Plain Language
                        </span>
                      </div>

                      <div className="text-sm leading-relaxed text-zinc-200 font-normal space-y-3 pt-1">
                        <p>{result.summary.narrative_summary}</p>
                      </div>
                    </div>

                    {/* 2. DOCTOR-DOCUMENTED PLAN (STRICT CLINICIAN INSTRUCTIONS) */}
                    {result.summary.doctor_recommendations?.length > 0 && (
                      <div className="glass-card p-6 md:p-8 space-y-4 border-indigo-500/30 bg-indigo-950/10">
                        <div className="flex items-center justify-between border-b border-indigo-500/20 pb-4">
                          <div className="flex items-center gap-3">
                            <div className="p-2 rounded-xl bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                              <Stethoscope size={18} />
                            </div>
                            <div>
                              <h3 className="text-base font-semibold text-indigo-200">
                                Doctor-Documented Plan
                              </h3>
                              <p className="text-xs text-zinc-400">
                                Exact instructions recorded by the doctor during your consultation
                              </p>
                            </div>
                          </div>
                          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium border border-indigo-500/40 bg-indigo-500/20 text-indigo-300">
                            Clinician Documented
                          </span>
                        </div>

                        <ul className="space-y-2.5 pt-1">
                          {result.summary.doctor_recommendations.map((rec: string, i: number) => (
                            <li key={i} className="flex items-start gap-3 text-sm bg-zinc-900/70 p-3.5 rounded-xl border border-zinc-800">
                              <span className="text-indigo-400 font-semibold mt-0.5">&rarr;</span>
                              <span className="font-medium text-zinc-100">{rec}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* 3. AI-SUGGESTED NEXT STEPS (STRUCTURED) */}
                    {(result.summary.ai_recommendations?.length > 0 || result.summary.next_steps?.length > 0) && (
                      <div className="glass-card p-6 md:p-8 space-y-4 border-zinc-800/80">
                        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-4">
                          <div className="flex items-center gap-3">
                            <div className="p-2 rounded-xl bg-zinc-800 text-zinc-300 border border-zinc-700">
                              <CalendarCheck size={18} />
                            </div>
                            <div>
                              <h3 className="text-base font-semibold text-white">
                                AI-Suggested Next Steps
                              </h3>
                              <p className="text-xs text-zinc-400">
                                Suggested investigations & questions to discuss with your doctor (Not documented as prescribed)
                              </p>
                            </div>
                          </div>
                          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium border border-zinc-700 bg-zinc-800 text-zinc-400">
                            AI-Suggested &bull; Not Prescribed
                          </span>
                        </div>

                        <div className="space-y-3.5 pt-1">
                          {result.summary.ai_recommendations?.length > 0 ? (
                            result.summary.ai_recommendations.map((item: any, i: number) => {
                              const priorityColor = 
                                item.priority === "urgent" 
                                  ? "border-rose-500/40 bg-rose-500/10 text-rose-300"
                                  : item.priority === "prompt"
                                  ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                                  : "border-zinc-700 bg-zinc-800/80 text-zinc-300";

                              return (
                                <div key={i} className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/50 space-y-2">
                                  <div className="flex items-start justify-between gap-3 flex-wrap">
                                    <div className="space-y-0.5">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <span className="text-sm font-semibold text-white">
                                          {item.recommendation}
                                        </span>
                                        <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-medium border ${priorityColor}`}>
                                          {item.priority}
                                        </span>
                                      </div>
                                    </div>
                                    <span className="text-[11px] text-zinc-400 bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-700/60">
                                      {item.prescription_status || "Not documented as prescribed"}
                                    </span>
                                  </div>

                                  <p className="text-xs text-zinc-300 leading-relaxed">
                                    <strong className="text-zinc-400 font-medium">Clinical Rationale:</strong> {item.reason}
                                  </p>

                                  <div className="flex items-center justify-between text-xs text-zinc-400 pt-1 border-t border-zinc-800/60">
                                    <span>Timing: <strong className="text-zinc-300 font-normal">{item.timing || "To be determined by clinician"}</strong></span>
                                    {item.caveat && (
                                      <span className="text-amber-300/90 italic max-w-md truncate">
                                        Note: {item.caveat}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })
                          ) : (
                            result.summary.next_steps.map((st: string, i: number) => (
                              <div key={i} className="p-3.5 rounded-xl border border-zinc-800 bg-zinc-900/50 text-xs text-zinc-200">
                                {st}
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    )}

                    {/* 4. MEDICATIONS SHOWCASE */}
                    <div className="glass-card p-6 md:p-8 space-y-4">
                      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                            <Pill size={18} />
                          </div>
                          <div>
                            <h3 className="text-base font-semibold text-white">
                              Prescribed & Reported Medications
                            </h3>
                            <p className="text-xs text-zinc-400">Identified from source notes without frequency duplication</p>
                          </div>
                        </div>
                        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium border border-zinc-700 bg-zinc-800/80 text-zinc-300">
                          {result.summary.current_medications?.length || 0} Medications
                        </span>
                      </div>

                      {result.summary.current_medications?.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                          {result.summary.current_medications.map((m: any, i: number) => {
                            return (
                              <div key={i} className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/40 flex flex-col justify-between space-y-3">
                                <div className="space-y-2">
                                  <div className="flex items-start justify-between gap-2">
                                    <div>
                                      <span className="text-sm font-semibold text-white">{m.drug}</span>
                                      {m.route && <span className="text-xs text-zinc-400 ml-1.5">({m.route})</span>}
                                    </div>
                                    <span className="px-2 py-0.5 rounded text-[10px] font-medium border border-zinc-700 bg-zinc-800 text-zinc-300">
                                      {m.status || "Current"}
                                    </span>
                                  </div>

                                  <div className="text-xs text-zinc-300 space-y-1">
                                    <div className="flex items-center gap-2">
                                      <span className="text-zinc-400">Dose & Frequency:</span>
                                      <strong className="text-white font-medium">{m.dose || "Dose not stated"}</strong>
                                      <span>&bull;</span>
                                      <strong className="text-indigo-300 font-medium">{m.frequency || "Schedule not specified"}</strong>
                                    </div>
                                    <div className="flex items-center gap-2 text-zinc-400">
                                      <span>Duration: <strong className="text-zinc-300 font-normal">{m.duration || "Duration not specified"}</strong></span>
                                      <span>&bull;</span>
                                      <span>Type: <strong className="text-zinc-300 font-normal">{m.prn_status || "Scheduled"}</strong></span>
                                    </div>
                                  </div>

                                  {m.missing_information && (
                                    <p className="text-xs text-amber-300/90 bg-amber-500/10 p-2 rounded-lg border border-amber-500/20">
                                      {m.missing_information}
                                    </p>
                                  )}

                                  {m.uncertainty && (
                                    <p className="text-xs text-amber-400 italic">
                                      Note: {m.uncertainty}
                                    </p>
                                  )}
                                </div>

                                <div className="pt-2 border-t border-zinc-800/80 flex items-center justify-between text-xs">
                                  <span className="text-[11px] text-zinc-500">Source Line:</span>
                                  {renderCitationBadge(m.source)}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-xs text-zinc-500 italic py-2">No medications recorded in notes.</p>
                      )}
                    </div>

                    {/* 5. URGENT CLINICAL CONCERNS & SAFETY-NET */}
                    {result.summary.red_flags?.length > 0 && (
                      <div className="glass-card p-6 md:p-8 space-y-4 border-rose-500/30 bg-rose-950/10">
                        <div className="flex items-center justify-between border-b border-rose-500/20 pb-4">
                          <div className="flex items-center gap-3">
                            <div className="p-2 rounded-xl bg-rose-500/20 text-rose-300 border border-rose-500/30">
                              <AlertOctagon size={18} />
                            </div>
                            <div>
                              <h3 className="text-base font-semibold text-rose-200">
                                Urgent Clinical Concerns & Warning Signs
                              </h3>
                              <p className="text-xs text-zinc-400">
                                When to seek prompt clinical review or emergency care
                              </p>
                            </div>
                          </div>
                          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium border border-rose-500/40 bg-rose-500/20 text-rose-300">
                            Safety-Net Guidance
                          </span>
                        </div>

                        <ul className="space-y-2.5 pt-1">
                          {result.summary.red_flags.map((item: string, i: number) => (
                            <li key={i} className="flex items-start gap-3 text-sm bg-zinc-900/80 p-3.5 rounded-xl border border-zinc-800">
                              <span className="text-rose-400 font-bold shrink-0 mt-0.5">!</span>
                              <span className="text-zinc-200 leading-relaxed">{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* 6. PHARMACOTHERAPY SAFETY & CLINICAL PEARLS */}
                    {renderDrugIntelligenceCard()}
                    {renderMissingInfoCard()}
                    {renderClinicalPearlsCard()}

                  </div>
                )}

                {/* ========================================================== */}
                {/* MODE B: CLINICAL WORKSTATION VIEW (EHR)                    */}
                {/* ========================================================== */}
                {viewMode === "clinical" && (
                  <div className="space-y-6">

                    {/* Clinical Tabs Bar */}
                    <div className="flex items-center gap-1.5 overflow-x-auto py-1 border-b border-zinc-800 pb-3 custom-scrollbar">
                      {[
                        { id: "overview", label: "Lore & Plan", icon: FileCheck },
                        { 
                          id: "findings", 
                          label: "Vitals & Findings", 
                          icon: HeartPulse,
                          count: (result.summary.documented_conditions?.length || 0) + (result.summary.symptoms?.length || 0)
                        },
                        { 
                          id: "meds_labs", 
                          label: "Medications & Labs", 
                          icon: Pill,
                          count: (result.summary.current_medications?.length || 0) + (result.summary.recent_labs?.length || 0)
                        },
                        { 
                          id: "safety", 
                          label: "Safety Radar", 
                          icon: ShieldAlert,
                          count: (result.summary.red_flags?.length || 0) + (result.summary.allergies?.length || 0),
                          isUrgent: result.summary.red_flags?.length > 0
                        },
                        { id: "all", label: "Full Chart", icon: Layers }
                      ].map(tab => {
                        const Icon = tab.icon;
                        const isActive = rightTab === tab.id;
                        return (
                          <button
                            key={tab.id}
                            onClick={() => setRightTab(tab.id as any)}
                            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all whitespace-nowrap cursor-pointer ${
                              isActive 
                                ? "bg-indigo-600 text-white shadow-sm" 
                                : tab.isUrgent
                                ? "bg-rose-500/10 text-rose-300 border border-rose-500/30 hover:bg-rose-500/20"
                                : "bg-zinc-900/60 text-zinc-400 border border-zinc-800 hover:text-white"
                            }`}
                          >
                            <Icon size={13} />
                            <span>{tab.label}</span>
                            {tab.count !== undefined && tab.count > 0 && (
                              <span className={`text-[10px] font-mono px-1.5 rounded-full ${
                                isActive ? "bg-white/20 text-white" : "bg-zinc-800 text-zinc-300"
                              }`}>
                                {tab.count}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>

                    {/* OVERVIEW / LORE & PLAN TAB */}
                    {(rightTab === "overview" || rightTab === "all") && (
                      <div className="space-y-6">
                        
                        {/* Encounter Lore */}
                        {result.summary.narrative_summary && (
                          <div className="glass-card p-6 space-y-3">
                            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
                              <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                                Encounter Synthesis
                              </h4>
                              <span className="text-[10px] text-zinc-500 font-mono">Patient Narrative</span>
                            </div>
                            <div className="text-sm leading-relaxed text-zinc-200">
                              {result.summary.narrative_summary}
                            </div>
                          </div>
                        )}

                        {/* Chief Complaint & Clinical Impression */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="glass-card p-5 space-y-2">
                            <span className="text-[11px] font-medium text-zinc-400 uppercase tracking-wide block">
                              Chief Complaint
                            </span>
                            {result.summary.chief_complaint ? (
                              <div className="text-sm font-semibold text-white flex items-center justify-between">
                                <span>{result.summary.chief_complaint}</span>
                                <div className="flex items-center gap-2">
                                  {renderUnverifiedBadge("chief_complaint")}
                                  {renderCitationBadge(result.summary.chief_complaint_source)}
                                </div>
                              </div>
                            ) : (
                              <span className="text-xs text-zinc-500 italic">Not documented</span>
                            )}
                          </div>

                          <div className="glass-card p-5 space-y-2">
                            <span className="text-[11px] font-medium text-zinc-400 uppercase tracking-wide block">
                              Clinical Impression (Suspected)
                            </span>
                            {result.summary.clinical_impression ? (
                              <div className="text-sm font-semibold text-indigo-300 flex items-center justify-between">
                                <span>{result.summary.clinical_impression}</span>
                                <div className="flex items-center gap-2">
                                  {renderUnverifiedBadge("clinical_impression")}
                                  {renderCitationBadge(result.summary.clinical_impression_source)}
                                </div>
                              </div>
                            ) : (
                              <span className="text-xs text-zinc-500 italic">No formal impression recorded</span>
                            )}
                          </div>
                        </div>

                        {/* Doctor Documented Plan (Explicit) */}
                        {result.summary.doctor_recommendations?.length > 0 && (
                          <div className="glass-card p-6 space-y-3 border-indigo-500/30 bg-indigo-950/10">
                            <div className="flex items-center justify-between border-b border-indigo-500/20 pb-3">
                              <h4 className="text-xs font-semibold text-indigo-300 uppercase tracking-wider">
                                Doctor-Documented Management Plan (Clinician Verbatim)
                              </h4>
                              <span className="text-[10px] font-mono text-indigo-400">Preserved Intent</span>
                            </div>
                            <ul className="space-y-2 pt-1">
                              {result.summary.doctor_recommendations.map((rec: string, i: number) => (
                                <li key={i} className="text-sm flex items-start gap-2.5 bg-zinc-900/80 p-3 rounded-lg border border-zinc-800 text-zinc-200">
                                  <span className="text-indigo-400 font-semibold">&rarr;</span>
                                  <span>{rec}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* AI-Suggested Next Steps (Structured) */}
                        {result.summary.ai_recommendations?.length > 0 && (
                          <div className="glass-card p-6 space-y-3">
                            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
                              <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                                AI-Suggested Next Steps & Investigations (Not Prescribed)
                              </h4>
                              <span className="text-[10px] text-zinc-500">Clinical Decision Support</span>
                            </div>
                            <div className="space-y-3 pt-1">
                              {result.summary.ai_recommendations.map((rec: any, i: number) => (
                                <div key={i} className="p-3.5 rounded-lg border border-zinc-800 bg-zinc-900/60 space-y-1.5 text-xs">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="font-semibold text-sm text-zinc-100">{rec.recommendation}</span>
                                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                                      {rec.priority}
                                    </span>
                                  </div>
                                  <p className="text-zinc-300">Rationale: {rec.reason}</p>
                                  <div className="text-zinc-400 pt-1 flex items-center justify-between border-t border-zinc-800/60">
                                    <span>Timing: {rec.timing || "Clinician to determine"}</span>
                                    {rec.caveat && <span className="text-amber-300/80 italic">{rec.caveat}</span>}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Differential Diagnoses */}
                        {result.summary.differential_diagnoses?.length > 0 && (
                          <div className="glass-card p-6 space-y-3">
                            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-800/80 pb-3">
                              Plausible Differentials with Evidence Attribution
                            </h4>
                            <ul className="space-y-2 pt-1">
                              {result.summary.differential_diagnoses.map((dx: string, i: number) => (
                                <li key={i} className="text-sm bg-zinc-900/60 p-3 rounded-lg border border-zinc-800 text-zinc-300">
                                  {dx}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Clinical Uncertainties & Unknowns */}
                        {result.summary.uncertainties?.length > 0 && (
                          <div className="glass-card p-6 space-y-3 border-amber-500/20 bg-amber-950/5">
                            <h4 className="text-xs font-semibold text-amber-300 uppercase tracking-wider border-b border-amber-500/20 pb-3">
                              Clinical Uncertainties & Missing Causality
                            </h4>
                            <ul className="space-y-2 pt-1">
                              {result.summary.uncertainties.map((unc: string, i: number) => (
                                <li key={i} className="text-sm bg-zinc-900/60 p-3 rounded-lg border border-zinc-800 text-zinc-300 flex items-start gap-2">
                                  <span className="text-amber-400 font-semibold">&bull;</span>
                                  <span>{unc}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                      </div>
                    )}

                    {/* FINDINGS TAB */}
                    {(rightTab === "findings" || rightTab === "all") && (
                      <div className="space-y-6">
                        
                        {/* Documented Conditions (Strict Documented Only) */}
                        <div className="glass-card p-6 space-y-3">
                          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-800/80 pb-3">
                            Documented Pre-Existing / Active Diagnoses
                          </h4>
                          {result.summary.documented_conditions?.length > 0 ? (
                            <ul className="space-y-2 pt-1">
                              {result.summary.documented_conditions.map((item: string, i: number) => (
                                <li key={i} className="text-sm flex items-center justify-between bg-zinc-900/60 p-3 rounded-lg border border-zinc-800">
                                  <span className="font-semibold text-white">{item}</span>
                                  <div className="flex items-center gap-2">
                                    {renderUnverifiedBadge(`documented_conditions[${i}]`)}
                                    {renderCitationBadge(result.summary.documented_conditions_sources?.[i])}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-xs text-zinc-500 italic py-2">No formal diagnoses explicitly documented by clinician in source note.</p>
                          )}
                        </div>

                        {/* Symptoms */}
                        <div className="glass-card p-6 space-y-3">
                          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-800/80 pb-3">
                            Patient-Reported Symptoms
                          </h4>
                          <ul className="space-y-2 pt-1">
                            {result.summary.symptoms?.map((s: string, i: number) => (
                              <li key={i} className="text-sm flex items-center justify-between bg-zinc-900/60 p-3 rounded-lg border border-zinc-800">
                                <span className="text-zinc-200">{s}</span>
                                <div className="flex items-center gap-2">
                                  {renderUnverifiedBadge(`symptoms[${i}]`)}
                                  {renderCitationBadge(result.summary.symptoms_sources?.[i])}
                                </div>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* Clinical Findings & Measured Vitals */}
                        <div className="glass-card p-6 space-y-3">
                          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-800/80 pb-3">
                            Clinical Measurements & Signs (BP, Pulse, SpO2, Pallor)
                          </h4>
                          <ul className="space-y-2 pt-1">
                            {result.summary.clinical_findings?.map((f: any, i: number) => {
                              const findingText = typeof f === "string" ? f : `${f.finding || ""}${f.value ? ` (${f.value}${f.unit ? ` ${f.unit}` : ""})` : ""}${f.finding_type ? ` [${f.finding_type}]` : ""}`;
                              const findingSource = typeof f === "object" && f?.source ? f.source : result.summary.clinical_findings_sources?.[i];
                              return (
                                <li key={i} className="text-sm flex items-center justify-between bg-zinc-900/60 p-3 rounded-lg border border-zinc-800">
                                  <span className="text-zinc-200">{findingText}</span>
                                  <div className="flex items-center gap-2">
                                    {renderUnverifiedBadge(`clinical_findings[${i}]`)}
                                    {renderCitationBadge(findingSource)}
                                  </div>
                                </li>
                              );
                            })}
                          </ul>
                        </div>

                        {/* Pertinent Negatives */}
                        <div className="glass-card p-6 space-y-3">
                          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-800/80 pb-3">
                            Pertinent Negatives (Explicitly Denied in Source)
                          </h4>
                          <ul className="space-y-2 pt-1">
                            {result.summary.pertinent_negatives?.map((n: string, i: number) => (
                              <li key={i} className="text-sm flex items-center justify-between bg-zinc-900/60 p-3 rounded-lg border border-zinc-800">
                                <span className="text-zinc-300">{n}</span>
                                <div className="flex items-center gap-2">
                                  {renderUnverifiedBadge(`pertinent_negatives[${i}]`)}
                                  {renderCitationBadge(result.summary.pertinent_negatives_sources?.[i])}
                                </div>
                              </li>
                            ))}
                          </ul>
                        </div>

                      </div>
                    )}

                    {/* MEDS & LABS TAB */}
                    {(rightTab === "meds_labs" || rightTab === "all") && (
                      <div className="space-y-6">
                        
                        {/* Labs Table */}
                        <div className="glass-card p-6 space-y-4">
                          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-800/80 pb-3">
                            Laboratory Investigations & Reference Ranges
                          </h4>
                          <div className="space-y-2.5 pt-1">
                            {result.summary.recent_labs?.map((l: any, i: number) => (
                              <div key={i} className="p-3.5 rounded-xl border border-zinc-800 bg-zinc-900/50 flex flex-wrap items-center justify-between gap-3 text-xs">
                                <div className="flex items-center gap-3">
                                  <span className="font-semibold text-sm text-white">{l.test_name}</span>
                                  <span className="font-mono text-sm text-indigo-300 font-semibold">{l.value || "—"} {l.unit || ""}</span>
                                  {l.abnormality && (
                                    <span className="px-2 py-0.5 rounded text-[10px] font-medium uppercase bg-rose-500/20 text-rose-300 border border-rose-500/40">
                                      {l.abnormality}
                                    </span>
                                  )}
                                  {l.reference_range && (
                                    <span className="text-zinc-500 font-mono">
                                      (Ref: {l.reference_range})
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center gap-2">
                                  {renderUnverifiedBadge(`recent_labs[${i}]`)}
                                  {renderCitationBadge(l.source)}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Medications Table */}
                        <div className="glass-card p-6 space-y-4">
                          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-800/80 pb-3">
                            Medication Regimen & Duration
                          </h4>
                          <div className="space-y-3 pt-1">
                            {result.summary.current_medications?.map((m: any, i: number) => (
                              <div key={i} className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/50 space-y-2 text-xs">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <span className="font-semibold text-sm text-white">{m.drug}</span>
                                    {m.route && <span className="text-zinc-400">({m.route})</span>}
                                  </div>
                                  <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-zinc-800 text-zinc-300 border border-zinc-700">
                                    {m.status || "Current"}
                                  </span>
                                </div>
                                <div className="text-zinc-300 flex items-center gap-3 flex-wrap">
                                  <span>Dose: <strong className="text-white">{m.dose || "N/A"}</strong></span>
                                  <span>&bull;</span>
                                  <span>Frequency: <strong className="text-indigo-300">{m.frequency || "N/A"}</strong></span>
                                  <span>&bull;</span>
                                  <span>Duration: <strong className="text-zinc-300">{m.duration || "Duration not specified"}</strong></span>
                                </div>
                                <div className="pt-2 border-t border-zinc-800/60 flex items-center justify-between">
                                  <span className="text-zinc-500">Source:</span>
                                  {renderCitationBadge(m.source)}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                      </div>
                    )}

                    {/* SAFETY RADAR TAB */}
                    {(rightTab === "safety" || rightTab === "all") && (
                      <div className="space-y-6">
                        {renderDrugIntelligenceCard()}
                        {renderMissingInfoCard()}

                        {/* Allergies */}
                        {result.summary.allergies?.length > 0 && (
                          <div className="glass-card p-6 space-y-3 border-amber-500/20 bg-amber-950/5">
                            <h4 className="text-xs font-semibold text-amber-300 uppercase tracking-wider border-b border-amber-500/20 pb-3">
                              Allergies & Adverse Drug Reactions
                            </h4>
                            <div className="space-y-2 pt-1">
                              {result.summary.allergies.map((a: any, i: number) => (
                                <div key={i} className="p-3 bg-zinc-900/60 rounded-xl border border-zinc-800 flex items-center justify-between text-xs">
                                  <div>
                                    <span className="text-white font-semibold">{a.allergen}</span>
                                    {a.reaction && <span className="text-zinc-400 ml-2">({a.reaction})</span>}
                                  </div>
                                  <div className="flex items-center gap-2">
                                    {renderUnverifiedBadge(`allergies[${i}]`)}
                                    {renderCitationBadge(a.source)}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                  </div>
                )}

              </div>
            )}

          </div>

        </div>

      </main>

    </div>
  );
}
