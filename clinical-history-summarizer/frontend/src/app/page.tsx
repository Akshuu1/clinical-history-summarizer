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
  Sparkle
} from "lucide-react";

const API_URL = "http://localhost:8000";

const SAMPLE_DEMO_NOTE = `Pt: E9 / DOB ~1958 / seen 8/10/24

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

  const setAllCollapsed = (collapsed: boolean) => {
    const sectionIds = [
      "documented_conditions",
      "chief_complaint",
      "symptoms",
      "risk_factors",
      "clinical_findings",
      "recent_labs",
      "current_medications",
      "allergies",
      "pertinent_negatives",
      "clinical_impression",
      "differential_diagnoses",
      "doctor_recommendations",
      "pending_items",
      "uncertainties",
      "next_steps"
    ];
    const updated: Record<string, boolean> = {};
    sectionIds.forEach(id => {
      updated[id] = collapsed;
    });
    setCollapsedSections(updated);
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
      showToast(`🔥 Transcribed ${file.name}`);
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
      setError("Please drop a prescription or paste clinical notes first!");
      return;
    }
    
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_URL}/extract`, {
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
      showToast("⚡ Summary ready in both Patient & Doctor views!");
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

    showToast(`🎯 Locked on source Line ${lineNum}`);
  };

  const handleCopySummary = () => {
    if (!result) return;
    const s = result.summary;
    let md = `# Patient Health & Medication Summary\n`;
    md += `Patient Identifier: ${result.summary.patient_id || patientId || "N/A"}\n\n`;

    if (s.narrative_summary) {
      md += `## What Happened (Simple Language Summary)\n${s.narrative_summary}\n\n`;
    }
    if (s.current_medications?.length > 0) {
      md += `## Prescribed Medications\n`;
      s.current_medications.forEach((m: any) => {
        const det = [m.dose, m.route, m.frequency].filter(Boolean).join(" • ");
        md += `- **${m.drug}**: ${det || "Dose as directed"}${m.status ? ` [${m.status}]` : ""}\n`;
      });
      md += `\n`;
    }
    if (s.next_steps?.length > 0) {
      md += `## Recommended Next Tests & Actions\n`;
      s.next_steps.forEach((st: string) => { md += `- ${st}\n`; });
      md += `\n`;
    }
    if (s.doctor_recommendations?.length > 0) {
      md += `## Doctor's Explicit Instructions\n`;
      s.doctor_recommendations.forEach((r: string) => { md += `→ ${r}\n`; });
      md += `\n`;
    }
    if (s.red_flags?.length > 0) {
      md += `## ⚠️ Warning Signs to Watch For\n`;
      s.red_flags.forEach((f: string) => { md += `- ${f}\n`; });
      md += `\n`;
    }

    navigator.clipboard.writeText(md).then(() => {
      showToast("📋 Summary & medicines copied to clipboard!");
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
    showToast("💾 JSON report downloaded!");
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
        className={`ml-2 inline-flex items-center gap-1.5 text-[11px] font-mono font-extrabold px-2 py-0.5 rounded-lg border-2 transition-all cursor-pointer ${
          isTarget 
            ? "bg-[#ccff00] text-black border-black shadow-[3px_3px_0px_#ff5500] scale-105" 
            : "bg-zinc-800/90 hover:bg-[#ccff00] text-zinc-300 hover:text-black border-zinc-700 hover:border-black shadow-[2px_2px_0px_#000] hover:shadow-[3px_3px_0px_#ccff00]"
        }`}
        title={`Click to jump to line ${source.line_number}: "${source.quoted_text}"`}
      >
        <Zap size={11} className={isTarget ? "fill-black text-black" : "text-[#ccff00]"} />
        <span>L{source.line_number}</span>
        <span className="opacity-70 font-normal max-w-[110px] truncate hidden sm:inline">&ldquo;{snippet}&rdquo;</span>
      </button>
    );
  };

  const renderUnverifiedBadge = (fieldKey: string) => {
    if (!result) return null;
    const isUnv = (result.summary.unverified_fields || []).includes(fieldKey);
    if (!isUnv) return null;
    return (
      <span 
        className="ml-2 inline-flex items-center gap-1 bg-[#ff2a5f] text-black border-2 border-black font-extrabold text-[10px] px-2 py-0.5 rounded-full shadow-[2px_2px_0px_#000] uppercase tracking-wider"
        title="Unverified: Citation couldn't be matched verbatim"
      >
        <AlertTriangle size={11} className="stroke-[3]" />
        VERIFY
      </span>
    );
  };

  const matchesSearch = (text?: string | null) => {
    if (!searchTerm.trim()) return true;
    if (!text) return false;
    return text.toLowerCase().includes(searchTerm.toLowerCase());
  };

  const renderDocumentInspector = () => {
    if (!notes.trim()) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-zinc-500 py-12">
          <FileText size={48} className="mb-3 text-zinc-600 opacity-60" />
          <p className="text-sm font-bold">No prescription or notes loaded yet.</p>
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
              className={`flex items-start rounded-xl px-3 py-1.5 transition-all group ${
                isTarget 
                  ? "citation-active-target bg-[#ccff00]/20 text-white font-semibold" 
                  : isCited 
                  ? "bg-zinc-800/80 text-zinc-100 hover:bg-zinc-800 border-l-4 border-[#ccff00]" 
                  : "text-zinc-400 hover:bg-zinc-800/40"
              }`}
            >
              <div className="w-12 shrink-0 flex items-center justify-between pr-2 text-zinc-500 select-none">
                <span className={`text-[10px] font-extrabold ${isTarget ? "text-[#ccff00]" : isCited ? "text-[#ccff00]" : ""}`}>
                  L{lineNum}
                </span>
                {isCited && (
                  <span className="w-2 h-2 rounded-full bg-[#ccff00] shadow-[0_0_8px_#ccff00]" title={`Cited by: ${citations?.join(", ")}`} />
                )}
              </div>
              
              <div className="flex-1 whitespace-pre-wrap break-words leading-relaxed pl-1">
                {line || <span className="opacity-20 select-none">&nbsp;</span>}
              </div>

              {citations && citations.length > 0 && (
                <div className="hidden group-hover:flex shrink-0 items-center gap-1 pl-2">
                  <span className="text-[10px] font-extrabold bg-[#ccff00] text-black border border-black px-1.5 py-0.5 rounded shadow-[1px_1px_0px_#000]">
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
    <div className="flex flex-col min-h-screen text-zinc-100 selection:bg-[#ccff00] selection:text-black">
      
      {/* Toast Alert Banner */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 bg-zinc-950 text-white border-2 border-[#ccff00] px-4 py-3 rounded-2xl shadow-[5px_5px_0px_#ccff00] text-sm font-extrabold animate-bounce">
          <Sparkles size={18} className="text-[#ccff00]" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Header */}
      <header className="sticky top-0 z-40 bg-zinc-950/90 backdrop-blur-xl border-b-2 border-zinc-800 px-5 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
        
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="bg-[#ccff00] p-2.5 rounded-2xl border-2 border-black shadow-[3px_3px_0px_#ff5500]">
            <HeartPulse className="text-black w-6 h-6 stroke-[2.5]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl lg:text-2xl font-black tracking-tight text-white flex items-center gap-1.5">
                <span>HEALTH</span>
                <span className="bg-[#ccff00] text-black px-1.5 py-0.2 rounded-md font-mono text-base border border-black shadow-[2px_2px_0px_#000]">
                  RADAR
                </span>
              </h1>
              <span className="bg-[#ff5500] text-white border-2 border-black text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider hidden sm:inline-block shadow-[2px_2px_0px_#000]">
                EASY MEDICAL COPILOT
              </span>
            </div>
            <div className="flex items-center gap-2.5 text-xs text-zinc-400 font-medium">
              <span className="flex items-center gap-1 text-[#ccff00] font-bold">
                <span className="w-2 h-2 rounded-full bg-[#ccff00] animate-ping" />
                Easy Patient Language + Doctor Citations
              </span>
              <span className="text-zinc-600">•</span>
              <span className="hidden md:inline font-mono text-[11px] text-zinc-400">18 ANM Clinical Rules</span>
            </div>
          </div>
        </div>

        {/* Header Action Buttons */}
        <div className="flex items-center gap-3">
          {!result && !notes && (
            <button 
              onClick={() => {
                setNotes(SAMPLE_DEMO_NOTE);
                setPatientId("DEMO-CARDIO-01");
                setUploadFileName("emergency_cardio_note.txt");
                showToast("⚡ Emergency Cardio Case loaded!");
              }}
              className="bg-[#ccff00] hover:bg-[#b8e600] text-black font-extrabold text-xs px-4 py-2.5 rounded-xl border-2 border-black shadow-[3px_3px_0px_#ff5500] hover:shadow-[1px_1px_0px_#ff5500] hover:translate-x-[2px] hover:translate-y-[2px] flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <Sparkles size={14} className="stroke-[3]" />
              <span>Drop Sample Rx</span>
            </button>
          )}

          {result && (
            <button 
              onClick={() => {
                setResult(null);
                setError(null);
                setActiveCitedLine(null);
                setActiveQuotedText(null);
                showToast("✨ Fresh canvas ready!");
              }}
              className="bg-zinc-800 hover:bg-zinc-700 text-white font-bold text-xs px-3.5 py-2 rounded-xl border-2 border-zinc-700 shadow-[2px_2px_0px_#000] flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <RefreshCw size={13} />
              <span>Reset Encounter</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Grid */}
      <main className="flex-1 w-full max-w-[1920px] mx-auto p-4 lg:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* ======================================================== */}
        {/* LEFT PANEL: Ingestion & Live Line Inspector              */}
        {/* ======================================================== */}
        <div className="lg:col-span-5 flex flex-col h-[calc(100vh-105px)] bg-zinc-950/90 border-2 border-zinc-800 rounded-3xl shadow-[7px_7px_0px_#000] overflow-hidden">
          
          {/* Tabs Bar */}
          <div className="px-5 py-3.5 border-b-2 border-zinc-800 flex items-center justify-between bg-zinc-900/60">
            <div className="flex items-center gap-1.5 bg-black p-1 rounded-2xl border-2 border-zinc-800">
              <button 
                onClick={() => setLeftTab("editor")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-black flex items-center gap-1.5 transition-all cursor-pointer ${
                  leftTab === "editor"
                    ? "bg-[#ccff00] text-black border-2 border-black shadow-[2px_2px_0px_#ff5500]"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <Edit3 size={13} className="stroke-[2.5]" />
                <span>Upload & Type Rx</span>
              </button>
              
              <button 
                onClick={() => setLeftTab("inspector")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-black flex items-center gap-1.5 transition-all cursor-pointer ${
                  leftTab === "inspector"
                    ? "bg-[#ccff00] text-black border-2 border-black shadow-[2px_2px_0px_#ff5500]"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <Layers size={13} className="stroke-[2.5]" />
                <span>Line Radar</span>
                {citedLinesMap.size > 0 && (
                  <span className="ml-1 bg-black text-[#ccff00] text-[10px] px-1.5 py-0.2 rounded-full font-mono font-black border border-[#ccff00]">
                    {citedLinesMap.size}
                  </span>
                )}
              </button>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono text-zinc-400 font-bold hidden sm:inline">
                {noteMetrics.lines}L • {noteMetrics.words}W
              </span>
              {notes && (
                <button 
                  onClick={() => {
                    setNotes("");
                    setUploadFileName(null);
                    setPatientId("");
                    setResult(null);
                    setActiveCitedLine(null);
                    showToast("Cleared notes.");
                  }}
                  className="p-1.5 text-zinc-400 hover:text-[#ff2a5f] hover:bg-[#ff2a5f]/10 rounded-lg transition-colors cursor-pointer"
                  title="Wipe notes"
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>
          </div>

          {/* Active Citation Focus Banner */}
          {activeCitedLine && (
            <div className="bg-[#ccff00] border-b-2 border-black px-4 py-2 flex items-center justify-between text-xs text-black font-extrabold">
              <div className="flex items-center gap-2 truncate">
                <BookmarkCheck size={16} className="text-black stroke-[3] shrink-0" />
                <span>
                  LOCKED ON <strong>LINE {activeCitedLine}</strong>:
                  <span className="italic opacity-85 ml-1 truncate font-normal">
                    &ldquo;{activeQuotedText}&rdquo;
                  </span>
                </span>
              </div>
              <button 
                onClick={() => {
                  setActiveCitedLine(null);
                  setActiveQuotedText(null);
                }}
                className="bg-black text-[#ccff00] hover:text-white p-1 rounded-md cursor-pointer"
                title="Dismiss focus"
              >
                <X size={12} className="stroke-[3]" />
              </button>
            </div>
          )}

          {/* Left Panel Body */}
          <div className="flex-1 p-5 overflow-y-auto custom-scrollbar flex flex-col gap-4">
            
            {leftTab === "editor" ? (
              <>
                {/* Upload Dropzone */}
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
                  className={`border-2 border-dashed rounded-2xl p-5 transition-all cursor-pointer flex flex-col items-center justify-center text-center ${
                    isDragging 
                      ? 'border-[#ccff00] bg-[#ccff00]/15 scale-[0.98]' 
                      : isUploading 
                      ? 'border-[#ff5500] bg-zinc-900 cursor-wait' 
                      : uploadFileName 
                      ? 'border-[#ccff00] bg-[#ccff00]/10 shadow-[3px_3px_0px_#ccff00]' 
                      : 'border-zinc-700 hover:border-[#ccff00] hover:bg-zinc-900/60 bg-zinc-900/40 shadow-[4px_4px_0px_#000]'
                  }`}
                >
                  {isUploading ? (
                    <div className="flex items-center gap-3.5 py-2">
                      <div className="w-7 h-7 border-4 border-[#ff5500]/30 border-t-[#ff5500] rounded-full animate-spin" />
                      <div className="text-left">
                        <p className="text-sm font-black text-[#ff5500]">Reading Prescription File...</p>
                        <p className="text-xs text-zinc-400">Extracting medicines and doctor notes via Vision AI</p>
                      </div>
                    </div>
                  ) : uploadFileName ? (
                    <div className="flex items-center justify-between w-full px-2">
                      <div className="flex items-center gap-3">
                        <div className="bg-[#ccff00] text-black p-2.5 rounded-xl border border-black shadow-[2px_2px_0px_#000]">
                          <CheckCircle2 size={18} className="stroke-[3]" />
                        </div>
                        <div className="text-left">
                          <p className="text-sm font-black text-[#ccff00] truncate max-w-[280px]">{uploadFileName}</p>
                          <p className="text-xs text-zinc-400">Prescription read & ready to analyze</p>
                        </div>
                      </div>
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          setUploadFileName(null);
                          if (fileInputRef.current) fileInputRef.current.value = "";
                        }}
                        className="text-zinc-400 hover:text-[#ff2a5f] p-1.5 rounded-lg transition-colors cursor-pointer"
                        title="Remove file"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-2 py-1">
                      <div className="p-3 bg-[#ccff00] text-black rounded-2xl border-2 border-black shadow-[3px_3px_0px_#000]">
                        <UploadCloud size={24} className="stroke-[2.5]" />
                      </div>
                      <p className="text-sm font-black text-white">
                        Upload Any Doctor Prescription / Report
                      </p>
                      <p className="text-xs text-zinc-400 max-w-sm">
                        PDF, Mobile Photo (JPG/PNG), or Document &mdash; <span className="text-[#ccff00] font-bold underline">browse files</span>
                      </p>
                    </div>
                  )}
                </div>

                {/* Patient ID Metadata */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-black text-zinc-400 uppercase tracking-wider flex items-center justify-between">
                    <span>Patient Name / ID</span>
                    <span className="text-[10px] text-zinc-500 font-mono font-normal">auto-detected if in note</span>
                  </label>
                  <input 
                    type="text" 
                    value={patientId}
                    placeholder="e.g. Ramesh Kumar or PT-10492"
                    onChange={e => setPatientId(e.target.value)}
                    className="w-full bg-zinc-900 border-2 border-zinc-700 rounded-xl px-4 py-2.5 text-sm font-bold text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#ccff00] transition-colors shadow-[3px_3px_0px_#000]"
                  />
                </div>

                {/* Clinical Notes Input */}
                <div className="space-y-1.5 flex-1 flex flex-col min-h-[260px]">
                  <label className="text-[11px] font-black text-zinc-400 uppercase tracking-wider">
                    Doctor&apos;s Prescription / Clinical Text
                  </label>
                  <textarea 
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    placeholder="Type or paste any prescription text, doctor handwriting transcript, or hospital discharge notes here..."
                    className="w-full flex-1 bg-zinc-900 border-2 border-zinc-700 rounded-xl p-4 text-sm font-mono text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[#ccff00] transition-colors resize-none custom-scrollbar leading-relaxed shadow-[3px_3px_0px_#000]"
                  />
                </div>
              </>
            ) : (
              /* Line Radar */
              <div className="bg-zinc-900/90 border-2 border-zinc-800 rounded-2xl p-4 flex-1 overflow-y-auto custom-scrollbar shadow-[4px_4px_0px_#000]">
                {renderDocumentInspector()}
              </div>
            )}

          </div>

          {/* Action Button */}
          <div className="p-5 pt-3 border-t-2 border-zinc-800 bg-zinc-950/80">
            {error && (
              <div className="mb-3 text-black text-xs font-bold bg-[#ff2a5f] p-3 rounded-xl border-2 border-black flex items-start gap-2 shadow-[3px_3px_0px_#000]">
                <AlertTriangle size={16} className="text-black shrink-0 stroke-[2.5]" />
                <span className="leading-snug">{error}</span>
              </div>
            )}
            
            <button 
              onClick={handleExtract}
              disabled={isLoading}
              className="w-full bg-[#ccff00] hover:bg-[#b8e600] text-black font-black text-sm py-4 px-6 rounded-2xl border-2 border-black shadow-[5px_5px_0px_#ff5500] hover:shadow-[1px_1px_0px_#ff5500] hover:translate-x-[4px] hover:translate-y-[4px] active:scale-[0.99] transition-all flex items-center justify-center gap-2.5 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer uppercase tracking-wider"
            >
              {isLoading ? (
                <>
                  <div className="w-5 h-5 border-3 border-black/30 border-t-black rounded-full animate-spin" />
                  <span>Translating to Easy Language & Medicines...</span>
                </>
              ) : (
                <>
                  <Zap size={18} className="fill-black" />
                  <span>Extract Medicines & Simple Health Summary</span>
                  <ArrowRight size={18} className="stroke-[3]" />
                </>
              )}
            </button>
          </div>
        </div>

        {/* ======================================================== */}
        {/* RIGHT PANEL: Structured Output Bento                      */}
        {/* ======================================================== */}
        <div className="lg:col-span-7 flex flex-col h-[calc(100vh-105px)] bg-zinc-950/90 border-2 border-zinc-800 rounded-3xl shadow-[7px_7px_0px_#000] overflow-hidden">
          
          {/* Header & Mode Switcher */}
          <div className="px-6 py-3.5 border-b-2 border-zinc-800 flex flex-wrap items-center justify-between gap-3 bg-zinc-900/60">
            
            {/* View Mode Toggle: Patient vs Doctor */}
            <div className="flex items-center gap-1.5 bg-black p-1 rounded-2xl border-2 border-zinc-800">
              <button 
                onClick={() => setViewMode("patient")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-black flex items-center gap-1.5 transition-all cursor-pointer ${
                  viewMode === "patient"
                    ? "bg-[#ccff00] text-black border-2 border-black shadow-[2px_2px_0px_#ff5500]"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <span>🟢 Patient View (Easy Words)</span>
              </button>
              
              <button 
                onClick={() => setViewMode("clinical")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-black flex items-center gap-1.5 transition-all cursor-pointer ${
                  viewMode === "clinical"
                    ? "bg-[#ccff00] text-black border-2 border-black shadow-[2px_2px_0px_#ff5500]"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <span>🩺 Doctor View (EHR)</span>
              </button>
            </div>

            {/* Export Toolbar */}
            {result && (
              <div className="flex items-center gap-2">
                <button 
                  onClick={handleCopySummary}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-[#ccff00] text-zinc-300 hover:text-black font-extrabold rounded-xl text-xs border-2 border-zinc-700 hover:border-black shadow-[2px_2px_0px_#000] flex items-center gap-1.5 transition-all cursor-pointer"
                  title="Copy easy summary & medicines"
                >
                  <Copy size={13} className="stroke-[2.5]" />
                  <span>Copy</span>
                </button>

                <button 
                  onClick={handleExportJSON}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-[#ff5500] text-zinc-300 hover:text-white font-extrabold rounded-xl text-xs border-2 border-zinc-700 hover:border-black shadow-[2px_2px_0px_#000] flex items-center gap-1.5 transition-all cursor-pointer"
                  title="Download JSON"
                >
                  <Download size={13} className="stroke-[2.5]" />
                  <span>JSON</span>
                </button>

                <button 
                  onClick={handlePrint}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-white text-zinc-300 hover:text-black font-extrabold rounded-xl text-xs border-2 border-zinc-700 hover:border-black shadow-[2px_2px_0px_#000] flex items-center gap-1.5 transition-all cursor-pointer"
                  title="Print patient report"
                >
                  <Printer size={13} className="stroke-[2.5]" />
                  <span>Print</span>
                </button>
              </div>
            )}
          </div>

          {/* Empty State */}
          {!result && !isLoading && (
            <div className="flex-1 flex flex-col items-center justify-center text-zinc-500 p-8 text-center">
              <div className="p-5 bg-zinc-900 rounded-3xl border-2 border-zinc-800 mb-4 shadow-[4px_4px_0px_#000]">
                <ListTodo size={50} className="text-zinc-600" />
              </div>
              <h3 className="text-lg font-black text-white mb-1">No Prescription Processed Yet</h3>
              <p className="text-xs text-zinc-400 max-w-sm">
                Upload a prescription photo/PDF or click <span className="text-[#ccff00] font-black underline">&ldquo;Drop Sample Rx&rdquo;</span> at the top to generate a simple, patient-friendly summary and prescribed medicines stack.
              </p>
            </div>
          )}

          {/* Loading Animation */}
          {isLoading && (
            <div className="flex-1 flex flex-col items-center justify-center p-8">
              <div className="relative mb-6">
                <div className="w-16 h-16 border-4 border-zinc-800 border-t-[#ccff00] rounded-full animate-spin shadow-[0_0_20px_#ccff00]" />
                <Zap size={24} className="text-[#ccff00] absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 fill-[#ccff00]" />
              </div>
              <p className="text-white font-black text-sm mb-1">Analyzing Prescription & Simplifying Language...</p>
              <p className="text-xs font-mono text-zinc-400 max-w-sm text-center">
                Fetching exact medicine names, translating doctor notes to simple English, and verifying evidence lines.
              </p>
            </div>
          )}

          {/* Populated Result View */}
          {result && (
            <div className="flex-1 flex flex-col overflow-hidden">
              
              {/* Quick Summary Bento Stats */}
              <div className="px-6 py-3 border-b-2 border-zinc-800 bg-zinc-950/60">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  
                  {/* Prescribed Medicines Count */}
                  <div className="bg-zinc-900 border-2 border-black rounded-2xl p-3 shadow-[3px_3px_0px_#ccff00] flex items-center justify-between">
                    <div>
                      <div className="text-2xl font-black text-[#ccff00]">{result.summary.current_medications?.length || 0}</div>
                      <div className="text-[10px] font-black uppercase text-zinc-400 tracking-wider">Medicines Prescribed</div>
                    </div>
                    <Pill size={20} className="text-[#ccff00] stroke-[2.5]" />
                  </div>

                  {/* Recommended Next Tests / Moves */}
                  <div className="bg-zinc-900 border-2 border-black rounded-2xl p-3 shadow-[3px_3px_0px_#ff5500] flex items-center justify-between">
                    <div>
                      <div className="text-2xl font-black text-[#ff5500]">{result.summary.next_steps?.length || result.summary.pending_items?.length || 0}</div>
                      <div className="text-[10px] font-black uppercase text-zinc-400 tracking-wider">Suggested Tests</div>
                    </div>
                    <CalendarCheck size={20} className="text-[#ff5500] stroke-[2.5]" />
                  </div>

                  {/* Safety / Red Flags */}
                  <div className={`border-2 border-black rounded-2xl p-3 flex items-center justify-between ${
                    result.summary.red_flags?.length > 0
                      ? "bg-zinc-900 shadow-[3px_3px_0px_#ff2a5f]"
                      : "bg-zinc-900 shadow-[3px_3px_0px_#ccff00]"
                  }`}>
                    <div>
                      <div className={`text-2xl font-black ${result.summary.red_flags?.length > 0 ? "text-[#ff2a5f]" : "text-[#ccff00]"}`}>
                        {result.summary.red_flags?.length || 0}
                      </div>
                      <div className="text-[10px] font-black uppercase text-zinc-400 tracking-wider">Warning Flags</div>
                    </div>
                    <AlertOctagon size={20} className={result.summary.red_flags?.length > 0 ? "text-[#ff2a5f] stroke-[2.5]" : "text-[#ccff00] stroke-[2.5]"} />
                  </div>

                  {/* Verified Citations */}
                  <div className="bg-zinc-900 border-2 border-black rounded-2xl p-3 shadow-[3px_3px_0px_#ffffff] flex items-center justify-between">
                    <div>
                      <div className="text-2xl font-black text-white">{result.summary_stats.verified_count}</div>
                      <div className="text-[10px] font-black uppercase text-zinc-400 tracking-wider">Facts Verified</div>
                    </div>
                    <CheckCircle2 size={20} className="text-white stroke-[2.5]" />
                  </div>

                </div>
              </div>

              {/* Workstation Content Area */}
              <div className="p-6 flex-1 overflow-y-auto custom-scrollbar space-y-6">

                {/* ========================================================== */}
                {/* MODE A: 🟢 PATIENT-FRIENDLY VIEW (ASAN BHASHA / EASY WORDS) */}
                {/* ========================================================== */}
                {viewMode === "patient" && (
                  <div className="space-y-6">
                    
                    {/* 1. EASY LANGUAGE NARRATIVE SUMMARY */}
                    <div className="bg-zinc-900 border-2 border-black rounded-3xl p-6 shadow-[5px_5px_0px_#ccff00]">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2.5">
                          <div className="p-2 rounded-xl bg-[#ccff00] text-black border border-black shadow-[2px_2px_0px_#000]">
                            <Sparkle size={18} className="stroke-[2.5]" />
                          </div>
                          <div>
                            <h3 className="text-sm font-black text-[#ccff00] uppercase tracking-wider">
                              What Is Happening To You (Simple Explanation)
                            </h3>
                            <p className="text-xs text-zinc-400">Written in plain, everyday English for you and your family</p>
                          </div>
                        </div>
                        <span className="text-[10px] font-mono font-bold bg-black text-[#ccff00] px-2.5 py-1 rounded-full border border-[#ccff00]">
                          Easy Words
                        </span>
                      </div>

                      <div className="bg-black/50 border border-zinc-800 rounded-2xl p-4 mt-3">
                        <p className="text-sm leading-relaxed text-zinc-100 font-medium">
                          {result.summary.narrative_summary || (
                            <span>
                              You were seen for <strong>{result.summary.chief_complaint || "your health concerns"}</strong>. 
                              The doctor documented key findings and outlined the required medicine and follow-up plan below.
                            </span>
                          )}
                        </p>
                      </div>
                    </div>

                    {/* 2. PROMINENT PRESCRIBED MEDICINES SHOWCASE */}
                    <div className="bg-zinc-900 border-2 border-black rounded-3xl p-6 shadow-[5px_5px_0px_#ff5500]">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2.5">
                          <div className="p-2 rounded-xl bg-[#ff5500] text-black border border-black shadow-[2px_2px_0px_#000]">
                            <Pill size={20} className="stroke-[2.5]" />
                          </div>
                          <div>
                            <h3 className="text-base font-black text-white uppercase tracking-wider">
                              Prescribed Medicines & How to Take Them
                            </h3>
                            <p className="text-xs text-zinc-400">All medications identified from your prescription</p>
                          </div>
                        </div>
                        <span className="bg-[#ff5500] text-black text-[11px] font-black px-3 py-1 rounded-full border border-black shadow-[2px_2px_0px_#000]">
                          {result.summary.current_medications?.length || 0} Medicines Found
                        </span>
                      </div>

                      {result.summary.current_medications?.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                          {result.summary.current_medications.map((m: any, i: number) => {
                            const details = [m.dose, m.route, m.frequency].filter(Boolean).join(" • ");
                            return (
                              <div key={i} className="bg-black border-2 border-zinc-700 hover:border-[#ccff00] rounded-2xl p-4 flex flex-col justify-between shadow-[3px_3px_0px_#000] transition-colors">
                                <div>
                                  <div className="flex items-start justify-between gap-2">
                                    <span className="text-base font-black text-white">{m.drug}</span>
                                    {m.status && (
                                      <span className="bg-zinc-800 text-[#ccff00] text-[10px] font-mono font-black px-2 py-0.5 rounded-full uppercase border border-zinc-700">
                                        {m.status}
                                      </span>
                                    )}
                                  </div>

                                  <div className="mt-2 flex items-center gap-2">
                                    <span className="text-xs font-mono font-bold bg-zinc-800 text-zinc-200 px-2.5 py-1 rounded-lg border border-zinc-700">
                                      {details || "Take as directed by doctor"}
                                    </span>
                                  </div>

                                  {m.uncertainty && (
                                    <p className="text-xs text-[#ff5500] mt-2 font-bold flex items-center gap-1">
                                      <AlertTriangle size={13} className="shrink-0 stroke-[3]" />
                                      <span>Verify with doctor/chemist: {m.uncertainty}</span>
                                    </p>
                                  )}
                                </div>

                                <div className="mt-3 pt-2 border-t border-zinc-800 flex items-center justify-between text-xs">
                                  <span className="text-[11px] text-zinc-400">Prescription source</span>
                                  {renderCitationBadge(m.source)}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="bg-black/40 p-4 rounded-xl text-center text-xs text-zinc-400">
                          No specific medications found in the prescription notes.
                        </div>
                      )}
                    </div>

                    {/* 3. EXPLICIT SUGGESTIONS & NAMED TESTS */}
                    <div className="bg-zinc-900 border-2 border-black rounded-3xl p-6 shadow-[5px_5px_0px_#ffffff]">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2.5">
                          <div className="p-2 rounded-xl bg-white text-black border border-black shadow-[2px_2px_0px_#000]">
                            <CalendarCheck size={20} className="stroke-[2.5]" />
                          </div>
                          <div>
                            <h3 className="text-base font-black text-white uppercase tracking-wider">
                              Recommended Next Moves & Named Tests
                            </h3>
                            <p className="text-xs text-zinc-400">Specific tests and doctor visits suggested for your care</p>
                          </div>
                        </div>
                        <span className="bg-white text-black text-[11px] font-black px-3 py-1 rounded-full border border-black shadow-[2px_2px_0px_#000]">
                          Action Required
                        </span>
                      </div>

                      {/* Doctor Plan */}
                      {result.summary.doctor_recommendations?.length > 0 && (
                        <div className="mb-4">
                          <strong className="text-[11px] font-black text-[#ccff00] uppercase tracking-wider block mb-2">
                            Doctor&apos;s Stated Instructions:
                          </strong>
                          <ul className="space-y-2">
                            {result.summary.doctor_recommendations.map((rec: string, i: number) => (
                              <li key={i} className="text-sm flex items-start text-white bg-black/60 p-3 rounded-2xl border border-zinc-800">
                                <span className="text-[#ccff00] mr-2 font-black">→</span>
                                <span className="font-extrabold">{rec}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Named Next Steps (Tests / Specialists) */}
                      {result.summary.next_steps?.length > 0 && (
                        <div>
                          <strong className="text-[11px] font-black text-[#ff5500] uppercase tracking-wider block mb-2">
                            Suggested Tests & Checkups to Schedule:
                          </strong>
                          <ul className="space-y-2">
                            {result.summary.next_steps.map((step: string, i: number) => (
                              <li key={i} className="text-sm flex items-start text-zinc-100 bg-black/60 p-3 rounded-2xl border border-zinc-800">
                                <span className="text-[#ff5500] mr-2 font-black">✓</span>
                                <div className="flex-1 font-semibold leading-relaxed">
                                  {step}
                                </div>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* 4. RED FLAGS / WHEN TO RETURN IMMEDIATELY */}
                    {result.summary.red_flags?.length > 0 && (
                      <div className="bg-zinc-900 border-2 border-black p-6 rounded-3xl shadow-[5px_5px_0px_#ff2a5f]">
                        <div className="flex items-center gap-2.5 mb-3">
                          <div className="p-2 rounded-xl bg-[#ff2a5f] text-black border border-black shadow-[2px_2px_0px_#000]">
                            <AlertOctagon size={20} className="stroke-[3]" />
                          </div>
                          <div>
                            <h3 className="text-base font-black text-[#ff2a5f] uppercase tracking-wider">
                              Warning Signs &mdash; Go to ER If You Notice:
                            </h3>
                            <p className="text-xs text-zinc-400">Important red flag symptoms that need emergency care</p>
                          </div>
                        </div>

                        <ul className="space-y-2 mt-3">
                          {result.summary.red_flags.map((item: string, i: number) => (
                            <li key={i} className="text-sm flex items-start text-white bg-black/80 p-3.5 rounded-2xl border-2 border-zinc-800">
                              <span className="text-[#ff2a5f] font-black mr-2 text-lg leading-none">!</span>
                              <span className="font-black leading-snug">{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                  </div>
                )}

                {/* ========================================================== */}
                {/* MODE B: 🩺 CLINICAL WORKSTATION VIEW (FULL EHR CHART)      */}
                {/* ========================================================== */}
                {viewMode === "clinical" && (
                  <div className="space-y-6">

                    {/* Tabs Bar inside Clinical Mode */}
                    <div className="flex items-center gap-1.5 overflow-x-auto py-1 custom-scrollbar border-b border-zinc-800 pb-3">
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
                          label: "Pill Box & Labs", 
                          icon: Pill,
                          count: (result.summary.current_medications?.length || 0) + (result.summary.recent_labs?.length || 0)
                        },
                        { 
                          id: "safety", 
                          label: "Red Flag Radar", 
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
                            className={`px-3.5 py-1.5 rounded-xl text-xs font-black flex items-center gap-1.5 transition-all whitespace-nowrap cursor-pointer ${
                              isActive 
                                ? "bg-[#ccff00] text-black border-2 border-black shadow-[3px_3px_0px_#000] scale-105" 
                                : tab.isUrgent
                                ? "bg-[#ff2a5f]/20 text-[#ff2a5f] border-2 border-[#ff2a5f] hover:bg-[#ff2a5f] hover:text-black"
                                : "bg-zinc-800 text-zinc-300 border-2 border-zinc-700 hover:border-zinc-500"
                            }`}
                          >
                            <Icon size={13} className="stroke-[2.5]" />
                            <span>{tab.label}</span>
                            {tab.count !== undefined && tab.count > 0 && (
                              <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full border border-black ${
                                isActive 
                                  ? "bg-black text-[#ccff00]" 
                                  : tab.isUrgent 
                                  ? "bg-[#ff2a5f] text-black font-black" 
                                  : "bg-zinc-900 text-white"
                              }`}>
                                {tab.count}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>

                    {/* 1. NARRATIVE LORE CARD */}
                    {(rightTab === "overview" || rightTab === "all") && result.summary.narrative_summary && (
                      <div className="bg-zinc-900 border-2 border-black rounded-3xl p-5 shadow-[5px_5px_0px_#ccff00]">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <div className="p-1.5 rounded-xl bg-[#ccff00] text-black border border-black shadow-[2px_2px_0px_#000]">
                              <User size={15} className="stroke-[2.5]" />
                            </div>
                            <h3 className="text-xs font-black text-[#ccff00] uppercase tracking-widest">
                              Encounter Synthesis Lore
                            </h3>
                          </div>
                          <span className="text-[10px] font-mono font-bold bg-black text-[#ccff00] px-2 py-0.5 rounded-full border border-[#ccff00]">
                            Plain English Story
                          </span>
                        </div>
                        <div className="text-sm leading-relaxed text-zinc-100 whitespace-pre-wrap font-medium">
                          {result.summary.narrative_summary}
                        </div>
                      </div>
                    )}

                    {/* 2. CHIEF COMPLAINT & IMPRESSION */}
                    {(rightTab === "overview" || rightTab === "findings" || rightTab === "all") && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-zinc-900 border-2 border-black rounded-2xl p-4 shadow-[4px_4px_0px_#000]">
                          <div className="text-[10px] uppercase font-black text-zinc-400 tracking-wider mb-1.5">
                            Chief Complaint
                          </div>
                          {result.summary.chief_complaint ? (
                            <div className="text-sm font-black text-white">
                              <span>{result.summary.chief_complaint}</span>
                              {renderUnverifiedBadge("chief_complaint")}
                              {renderCitationBadge(result.summary.chief_complaint_source)}
                            </div>
                          ) : (
                            <span className="text-xs text-zinc-500 italic">Not mentioned in notes</span>
                          )}
                        </div>

                        <div className="bg-zinc-900 border-2 border-black rounded-2xl p-4 shadow-[4px_4px_0px_#000]">
                          <div className="text-[10px] uppercase font-black text-zinc-400 tracking-wider mb-1.5">
                            Clinical Impression
                          </div>
                          {result.summary.clinical_impression ? (
                            <div className="text-sm font-black text-[#ccff00]">
                              <span>{result.summary.clinical_impression}</span>
                              {renderUnverifiedBadge("clinical_impression")}
                              {renderCitationBadge(result.summary.clinical_impression_source)}
                            </div>
                          ) : (
                            <span className="text-xs text-zinc-500 italic">Not mentioned in notes</span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* 3. DOCUMENTED CONDITIONS */}
                    {(rightTab === "findings" || rightTab === "all") && (
                      <div className="bg-zinc-900 border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_#000]">
                        <div 
                          onClick={() => toggleSection("documented_conditions")}
                          className="flex items-center justify-between cursor-pointer select-none"
                        >
                          <div className="flex items-center gap-2">
                            <HeartPulse size={16} className="text-[#ff2a5f] stroke-[2.5]" />
                            <h4 className="text-xs font-black text-white uppercase tracking-widest">
                              Documented Conditions
                            </h4>
                            <span className="text-[10px] font-mono font-black bg-black text-[#ccff00] px-2 py-0.5 rounded-full border border-[#ccff00]">
                              {result.summary.documented_conditions?.length || 0}
                            </span>
                          </div>
                          {collapsedSections["documented_conditions"] ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                        </div>

                        {!collapsedSections["documented_conditions"] && (
                          <div className="mt-3.5">
                            {result.summary.documented_conditions?.length > 0 ? (
                              <ul className="space-y-2">
                                {result.summary.documented_conditions.map((item: string, i: number) => (
                                  <li key={i} className="text-sm flex items-start text-zinc-200">
                                    <span className="text-[#ccff00] mr-2 font-bold">•</span>
                                    <div>
                                      <span className="font-black text-white">{item}</span>
                                      {renderUnverifiedBadge(`documented_conditions[${i}]`)}
                                      {renderCitationBadge(result.summary.documented_conditions_sources?.[i])}
                                    </div>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <div className="text-xs text-zinc-500 italic">None documented</div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* 4. INVESTIGATIONS & LABS */}
                    {(rightTab === "meds_labs" || rightTab === "all") && (
                      <div className="bg-zinc-900 border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_#000]">
                        <div 
                          onClick={() => toggleSection("recent_labs")}
                          className="flex items-center justify-between cursor-pointer select-none"
                        >
                          <div className="flex items-center gap-2">
                            <Microscope size={16} className="text-[#ff5500] stroke-[2.5]" />
                            <h4 className="text-xs font-black text-white uppercase tracking-widest">
                              Investigations & Laboratory Results
                            </h4>
                            <span className="text-[10px] font-mono font-black bg-[#ff5500] text-black px-2 py-0.5 rounded-full border border-black shadow-[1px_1px_0px_#000]">
                              {result.summary.recent_labs?.length || 0}
                            </span>
                          </div>
                          {collapsedSections["recent_labs"] ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                        </div>

                        {!collapsedSections["recent_labs"] && (
                          <div className="mt-4">
                            {result.summary.recent_labs?.length > 0 ? (
                              <div className="space-y-2">
                                {result.summary.recent_labs.map((l: any, i: number) => {
                                  const isAbnormal = Boolean(l.abnormality);
                                  return (
                                    <div key={i} className={`p-3 rounded-2xl border-2 flex flex-wrap items-center justify-between gap-3 shadow-[2px_2px_0px_#000] ${
                                      isAbnormal ? "bg-black border-[#ff2a5f]" : "bg-black border-zinc-800"
                                    }`}>
                                      <div className="flex items-center gap-3">
                                        <span className="font-extrabold text-sm text-white">{l.test_name}</span>
                                        <span className="font-mono text-sm text-[#ccff00] font-black">
                                          {l.value || "—"} {l.unit || ""}
                                        </span>
                                        {l.abnormality && (
                                          <span className="bg-[#ff2a5f] text-black border border-black text-[10px] font-black px-2 py-0.5 rounded uppercase">
                                            {l.abnormality}
                                          </span>
                                        )}
                                        {l.reference_range && (
                                          <span className="text-xs text-zinc-400 font-mono">
                                            (Ref: {l.reference_range})
                                          </span>
                                        )}
                                      </div>

                                      <div className="flex items-center gap-2">
                                        {l.date && (
                                          <span className="text-[11px] text-zinc-500 font-mono">
                                            [{l.date}]
                                          </span>
                                        )}
                                        {renderUnverifiedBadge(`recent_labs[${i}]`)}
                                        {renderCitationBadge(l.source)}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : (
                              <div className="text-xs text-zinc-500 italic">No lab investigations recorded</div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                  </div>
                )}

              </div>

            </div>
          )}

        </div>

      </main>

    </div>
  );
}
