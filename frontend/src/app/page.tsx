"use client";

import React, { useState, useEffect } from "react";
import {
  Briefcase,
  FileText,
  Sparkles,
  Search,
  Bookmark,
  FileSignature,
  Compass,
  Upload,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Mail,
  Phone,
  Layers,
  Palette,
  Download,
  Loader2,
  Building2,
  MapPin,
} from "lucide-react";

// فارغ ليعمل تلقائياً على نفس دومين Vercel مع فولدر api/index.py
const API_BASE = "";

type ThemeKey = "blue" | "emerald" | "purple";

interface Job {
  Title: string;
  Company: string;
  Location: string;
  Description: string;
  Match_Score?: number;
  Skill_Pct?: number;
  Exp_Pct?: number;
  Level_Pct?: number;
  Matched_Skills?: string[];
  Missing_Skills?: string[];
  Apply_Link?: string;
}

interface CVData {
  role?: string;
  skills?: string[];
  experience_level?: number;
  career_level?: string;
  contact_info?: {
    email?: string;
    phone?: string;
  };
}

const THEMES: Record<ThemeKey, { name: string; primary: string; badge: string; border: string; glow: string }> = {
  blue: {
    name: "Cyber Blue",
    primary: "from-indigo-600 to-sky-500",
    badge: "bg-sky-500/10 text-sky-400 border-sky-500/30",
    border: "border-sky-500",
    glow: "shadow-sky-500/20",
  },
  emerald: {
    name: "Emerald AI",
    primary: "from-emerald-600 to-teal-500",
    badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    border: "border-emerald-500",
    glow: "shadow-emerald-500/20",
  },
  purple: {
    name: "Royal Nebula",
    primary: "from-purple-600 to-pink-500",
    badge: "bg-purple-500/10 text-purple-400 border-purple-500/30",
    border: "border-purple-500",
    glow: "shadow-purple-500/20",
  },
};

export default function JobMatchPlatform() {
  const [activeTab, setActiveTab] = useState("Home");
  const [theme, setTheme] = useState<ThemeKey>("blue");
  const currentTheme = THEMES[theme];

  // States
  const [cvData, setCvData] = useState<CVData | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [country, setCountry] = useState("eg");
  const [loading, setLoading] = useState(false);
  const [matchedJobs, setMatchedJobs] = useState<Job[]>([]);
  const [liveJobs, setLiveJobs] = useState<Job[]>([]);
  const [savedJobs, setSavedJobs] = useState<Job[]>([]);

  // Manual Match States
  const [manualSkills, setManualSkills] = useState("");
  const [manualExp, setManualExp] = useState(2);
  const [manualLevel, setManualLevel] = useState("Entry Level");

  // Live Search State
  const [searchQuery, setSearchQuery] = useState("AI Engineer");

  // Domain AI State
  const [selectedDomain, setSelectedDomain] = useState("Machine Learning / AI");

  // CV Builder States
  const [builder, setBuilder] = useState({
    name: "Ahmed Belal Ibrahim Elgiar",
    title: "AI & Machine Learning Engineer",
    email: "aelgiar00@gmail.com",
    phone: "+20 155 706 6499",
    linkedin: "linkedin.com/in/ahmed-elgiar-49b9a5310",
    summary: "AI and Machine Learning Engineering student with hands-on experience in data analysis, visualization, and predictive modeling.",
    experience: "Digital Egypt Pioneers Initiative (DEPI) - Trainee (2025 - Present)\nNTI Summer Training - AI & ML Intern (2026)",
    projects: "JobMatch AI - Next-Gen Career Platform with React, TypeScript & Tailwind CSS\nAutonomous Maze Bot - BFS Algorithm & Ultrasonic Sensors",
    education: "B.Sc. in AI & Computer Science Engineering, Tanta University",
    skills: "Python, C++, TypeScript, FastAPI, Scikit-learn, PyTorch, TensorFlow, Pandas, SQL, Tailwind CSS",
    languages: "Arabic (Native)\nEnglish (Intermediate)",
  });

// Load Saved Jobs safely using useEffect
  useEffect(() => {
    const timer = setTimeout(() => {
      const saved = localStorage.getItem("jobmatch_saved");
      if (saved) {
        try {
          setSavedJobs(JSON.parse(saved));
        } catch (e) {
          console.error(e);
        }
      }
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  const toggleSaveJob = (job: Job) => {
    const exists = savedJobs.some((j) => j.Title === job.Title && j.Company === job.Company);
    const updated = exists
      ? savedJobs.filter((j) => !(j.Title === job.Title && j.Company === job.Company))
      : [...savedJobs, job];
    setSavedJobs(updated);
    localStorage.setItem("jobmatch_saved", JSON.stringify(updated));
  };

  // Integrated API Calls (Vercel Serverless Python Backend)
  const handleAnalyzeCV = async () => {
    if (!selectedFile) return;
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Failed to analyze CV");
      const data = await res.json();
      setCvData(data);
      if (data) {
        setBuilder((prev) => ({
          ...prev,
          title: data.role || prev.title,
          email: data.contact_info?.email && data.contact_info.email !== "Not Found" ? data.contact_info.email : prev.email,
          phone: data.contact_info?.phone && data.contact_info.phone !== "Not Found" ? data.contact_info.phone : prev.phone,
          skills: data.skills?.length ? data.skills.join(", ") : prev.skills,
        }));
      }
    } catch (err) {
      console.error(err);
      alert("حدث خطأ أثناء تحليل الـ CV. تأكد من تشغيل الباك إند أو رفع المشروع على Vercel.");
    } finally {
      setLoading(false);
    }
  };

  const handleMatchCVJobs = async () => {
    if (!cvData) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/match-cv-jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...cvData, country_code: country }),
      });
      if (!res.ok) throw new Error("Failed to match jobs");
      const data = await res.json();
      setMatchedJobs(data.jobs || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleManualMatch = async () => {
    if (!manualSkills.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/manual-recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skills: manualSkills,
          experience_years: manualExp,
          career_level: manualLevel,
          country_code: country,
        }),
      });
      if (!res.ok) throw new Error("Failed to fetch recommendations");
      const data = await res.json();
      setMatchedJobs(data.jobs || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleLiveSearch = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/live-jobs?query=${encodeURIComponent(searchQuery)}&country=${encodeURIComponent(country)}`
      );
      if (!res.ok) throw new Error("Failed to search live jobs");
      const data = await res.json();
      setLiveJobs(data.jobs || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadCV = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/build-cv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(builder),
      });
      if (!res.ok) throw new Error("Failed to generate CV");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${builder.name.replace(/\s+/g, "_")}_ATS_CV.docx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    }
  };

  const JobCard = ({ job, showMetrics = true }: { job: Job; showMetrics?: boolean }) => {
    const isSaved = savedJobs.some((j) => j.Title === job.Title && j.Company === job.Company);
    return (
      <div className="bg-[#121723] border border-slate-800/80 hover:border-slate-700 rounded-2xl p-6 mb-5 transition-all duration-300 shadow-lg hover:shadow-xl">
        <div className="flex flex-wrap justify-between items-start gap-4 mb-3">
          <div>
            <div className="flex items-center gap-3">
              <h3 className="text-xl font-bold text-white">{job.Title}</h3>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-semibold">
                LIVE API
              </span>
            </div>
            <div className="flex items-center gap-4 text-slate-400 text-sm mt-2">
              <span className="flex items-center gap-1.5">
                <Building2 className="w-4 h-4 text-slate-500" /> {job.Company}
              </span>
              <span className="flex items-center gap-1.5">
                <MapPin className="w-4 h-4 text-slate-500" /> {job.Location}
              </span>
            </div>
          </div>

          {showMetrics && job.Match_Score !== undefined && (
            <div className={`px-4 py-1.5 rounded-full bg-gradient-to-r ${currentTheme.primary} text-white font-bold text-sm shadow-lg`}>
              ⭐ {job.Match_Score}% Match
            </div>
          )}
        </div>

        {showMetrics && job.Skill_Pct !== undefined && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 my-4 p-4 bg-slate-900/60 rounded-xl border border-slate-800/60">
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Skills Alignment</span>
                <span className="text-sky-400 font-semibold">{job.Skill_Pct}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-sky-500 rounded-full" style={{ width: `${job.Skill_Pct}%` }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Experience Match</span>
                <span className="text-emerald-400 font-semibold">{job.Exp_Pct}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${job.Exp_Pct}%` }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Career Level Fit</span>
                <span className="text-amber-400 font-semibold">{job.Level_Pct}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-amber-500 rounded-full" style={{ width: `${job.Level_Pct}%` }} />
              </div>
            </div>
          </div>
        )}

        <p className="text-slate-400 text-sm leading-relaxed mb-4 line-clamp-3">
          {job.Description}
        </p>

        {showMetrics && (job.Matched_Skills?.length || job.Missing_Skills?.length) ? (
          <div className="mb-5 space-y-2">
            <div className="flex flex-wrap gap-2">
              {job.Matched_Skills?.slice(0, 8).map((s: string) => (
                <span key={s} className="inline-flex items-center gap-1 text-xs px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <CheckCircle2 className="w-3 h-3" /> {s}
                </span>
              ))}
              {job.Missing_Skills?.slice(0, 6).map((s: string) => (
                <span key={s} className="inline-flex items-center gap-1 text-xs px-3 py-1 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
                  <XCircle className="w-3 h-3" /> {s}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div className="flex items-center gap-3 pt-3 border-t border-slate-800/80">
          {job.Apply_Link && job.Apply_Link !== "#" && (
            <a
              href={job.Apply_Link}
              target="_blank"
              rel="noreferrer"
              className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white text-sm font-semibold hover:opacity-95 transition shadow-md`}
            >
              Apply Now <ExternalLink className="w-4 h-4" />
            </a>
          )}
          <button
            onClick={() => toggleSaveJob(job)}
            className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-medium transition ${
              isSaved
                ? "bg-amber-500/10 border-amber-500/40 text-amber-400"
                : "border-slate-700 text-slate-300 hover:bg-slate-800"
            }`}
          >
            <Bookmark className="w-4 h-4" /> {isSaved ? "Saved" : "Save Job"}
          </button>
        </div>
      </div>
    );
  };

  const navItems = [
    { id: "Home", label: "Home", icon: Compass },
    { id: "CV Analyzer", label: "CV Analyzer", icon: FileText },
    { id: "AI Recommendations", label: "AI Match (Manual)", icon: Sparkles },
    { id: "Live Jobs", label: "Live Jobs", icon: Search },
    { id: "Saved Jobs", label: `Saved Jobs (${savedJobs.length})`, icon: Bookmark },
    { id: "CV Builder", label: "ATS CV Builder", icon: FileSignature },
    { id: "Domain AI", label: "Domain AI", icon: Layers },
  ];

  return (
    <div className="min-h-screen bg-[#0b0e14] text-slate-200 flex flex-col md:flex-row font-sans">
      <aside className="w-full md:w-72 bg-[#111522] border-r border-slate-800/80 p-6 flex flex-col justify-between shrink-0">
        <div>
          <div className="flex items-center gap-3 mb-8">
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-tr ${currentTheme.primary} flex items-center justify-center shadow-lg`}>
              <Briefcase className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-extrabold text-white tracking-tight">
                JobMatch <span className="text-sky-400">AI</span>
              </h1>
              <p className="text-[10px] tracking-widest text-slate-400 uppercase">Next-Gen Career Platform</p>
            </div>
          </div>

          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                    active
                      ? `bg-gradient-to-r ${currentTheme.primary} text-white shadow-lg ${currentTheme.glow}`
                      : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="mt-8 pt-6 border-t border-slate-800/80 space-y-4">
          <div>
            <span className="text-xs text-slate-400 flex items-center gap-1.5 mb-2">
              <Palette className="w-3.5 h-3.5" /> UI Theme
            </span>
            <div className="grid grid-cols-3 gap-2">
              {(Object.keys(THEMES) as ThemeKey[]).map((tKey) => (
                <button
                  key={tKey}
                  onClick={() => setTheme(tKey)}
                  className={`py-1.5 px-2 rounded-lg text-xs font-medium border capitalize transition ${
                    theme === tKey
                      ? `${THEMES[tKey].badge} ${THEMES[tKey].border}`
                      : "border-slate-800 text-slate-400 hover:bg-slate-800"
                  }`}
                >
                  {tKey}
                </button>
              ))}
            </div>
          </div>

          <div className="text-xs text-slate-500">
            FastAPI Serverless Engine
            <div className="text-emerald-400 font-semibold flex items-center gap-1.5 mt-0.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> v5.0 Integrated
            </div>
          </div>
        </div>
      </aside>

      <main className="flex-1 p-6 md:p-10 overflow-y-auto max-w-6xl mx-auto w-full">
        {activeTab === "Home" && (
          <div className="space-y-8">
            <div className="p-8 rounded-3xl bg-gradient-to-br from-slate-900 via-[#13192b] to-slate-900 border border-slate-800/80 shadow-2xl">
              <span className={`inline-block text-xs font-semibold px-3 py-1 rounded-full border mb-4 ${currentTheme.badge}`}>
                AI-POWERED RECRUITMENT ENGINE
              </span>
              <h2 className="text-3xl md:text-5xl font-extrabold text-white tracking-tight mb-4">
                Your Intelligent Career Copilot.
              </h2>
              <p className="text-slate-400 text-lg max-w-2xl mb-6 leading-relaxed">
                We bridge the gap between your technical skills and live market demands using Machine Learning, NLP Vectorization, and Real-Time Job Matching.
              </p>
              <div className="flex flex-wrap gap-4">
                <button
                  onClick={() => setActiveTab("CV Analyzer")}
                  className={`px-6 py-3 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-semibold shadow-lg hover:opacity-95 transition flex items-center gap-2`}
                >
                  <Upload className="w-4 h-4" /> Analyze My CV Now
                </button>
                <button
                  onClick={() => setActiveTab("CV Builder")}
                  className="px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold transition flex items-center gap-2"
                >
                  <FileSignature className="w-4 h-4" /> Build ATS Resume
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800/80 text-center">
                <p className="text-xs uppercase tracking-wider text-slate-400">Jobs Analyzed</p>
                <p className="text-3xl font-extrabold text-white mt-2">353,052+</p>
              </div>
              <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800/80 text-center">
                <p className="text-xs uppercase tracking-wider text-slate-400">Active Tech Domains</p>
                <p className="text-3xl font-extrabold text-white mt-2">19 Domains</p>
              </div>
              <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800/80 text-center">
                <p className="text-xs uppercase tracking-wider text-slate-400">Saved Opportunities</p>
                <p className="text-3xl font-extrabold text-white mt-2">{savedJobs.length}</p>
              </div>
            </div>
          </div>
        )}

        {activeTab === "CV Analyzer" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-3xl font-bold text-white">AI CV Analyzer</h2>
              <p className="text-slate-400 mt-1">Upload your resume (PDF, DOCX, TXT) for deep semantic skill extraction and job matching.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 bg-[#121723] p-6 rounded-2xl border border-slate-800">
              <div className="md:col-span-3">
                <label className="block text-xs uppercase text-slate-400 mb-2">Upload Resume</label>
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="w-full text-sm text-slate-300 file:mr-4 file:py-2.5 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-slate-800 file:text-white hover:file:bg-slate-700 cursor-pointer bg-slate-900/70 rounded-xl p-2 border border-slate-800"
                />
              </div>
              <div>
                <label className="block text-xs uppercase text-slate-400 mb-2">Target Country</label>
                <input
                  type="text"
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  placeholder="e.g. eg, us, sa, ae"
                  className="w-full px-4 py-3 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm"
                />
              </div>
              <div className="md:col-span-4">
                <button
                  onClick={handleAnalyzeCV}
                  disabled={!selectedFile || loading}
                  className={`w-full py-3.5 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-bold shadow-lg hover:opacity-95 transition disabled:opacity-50 flex items-center justify-center gap-2`}
                >
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                  Analyze My CV
                </button>
              </div>
            </div>

            {cvData && (
              <div className="space-y-6 animate-fadeIn">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="p-5 rounded-2xl bg-[#121723] border border-slate-800">
                    <span className="text-xs text-slate-400 uppercase">Predicted Role</span>
                    <p className="text-lg font-bold text-sky-400 mt-1">{cvData.role}</p>
                  </div>
                  <div className="p-5 rounded-2xl bg-[#121723] border border-slate-800">
                    <span className="text-xs text-slate-400 uppercase">Skills Extracted</span>
                    <p className="text-2xl font-extrabold text-white mt-1">{cvData.skills?.length || 0}</p>
                  </div>
                  <div className="p-5 rounded-2xl bg-[#121723] border border-slate-800">
                    <span className="text-xs text-slate-400 uppercase">Est. Experience</span>
                    <p className="text-2xl font-extrabold text-white mt-1">{cvData.experience_level} Years</p>
                  </div>
                  <div className="p-5 rounded-2xl bg-[#121723] border border-slate-800">
                    <span className="text-xs text-slate-400 uppercase">Career Level</span>
                    <p className="text-xl font-bold text-emerald-400 mt-1">{cvData.career_level}</p>
                  </div>
                </div>

                <div className="p-5 rounded-2xl bg-[#121723] border border-slate-800 flex flex-wrap gap-6 items-center">
                  <div className="flex items-center gap-2 text-sm text-slate-300">
                    <Mail className="w-4 h-4 text-sky-400" /> {cvData.contact_info?.email}
                  </div>
                  <div className="flex items-center gap-2 text-sm text-slate-300">
                    <Phone className="w-4 h-4 text-emerald-400" /> {cvData.contact_info?.phone}
                  </div>
                </div>

                <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800">
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">
                    Extracted Technical Skills
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {cvData.skills?.map((skill: string) => (
                      <span
                        key={skill}
                        className="px-3.5 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 capitalize"
                      >
                        ✓ {skill}
                      </span>
                    ))}
                  </div>
                </div>

                <button
                  onClick={handleMatchCVJobs}
                  disabled={loading}
                  className={`w-full py-3.5 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-bold shadow-lg flex items-center justify-center gap-2`}
                >
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                  Find Live Jobs Matching My CV
                </button>

                {matchedJobs.length > 0 && (
                  <div className="mt-6">
                    <h3 className="text-xl font-bold text-white mb-4">Top Matched Jobs ({matchedJobs.length})</h3>
                    {matchedJobs.map((job, idx) => (
                      <JobCard key={idx} job={job} showMetrics={true} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === "AI Recommendations" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-3xl font-bold text-white">AI Job Recommendations</h2>
              <p className="text-slate-400 mt-1">Enter your tech stack manually and let our matching engine rank live jobs for you.</p>
            </div>

            <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800 space-y-4">
              <div>
                <label className="block text-xs uppercase text-slate-400 mb-2">Your Technical Stack</label>
                <textarea
                  rows={3}
                  value={manualSkills}
                  onChange={(e) => setManualSkills(e.target.value)}
                  placeholder="e.g., python, machine learning, scikit-learn, fastapi, react, typescript, sql..."
                  className="w-full p-4 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs uppercase text-slate-400 mb-2">Experience (Years)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={manualExp}
                    onChange={(e) => setManualExp(parseFloat(e.target.value) || 0)}
                    className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs uppercase text-slate-400 mb-2">Career Level</label>
                  <select
                    value={manualLevel}
                    onChange={(e) => setManualLevel(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm"
                  >
                    <option>Student</option>
                    <option>Entry Level</option>
                    <option>Experienced</option>
                    <option>Manager</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs uppercase text-slate-400 mb-2">Country Code</label>
                  <input
                    type="text"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm"
                  />
                </div>
              </div>
              <button
                onClick={handleManualMatch}
                disabled={loading}
                className={`w-full py-3.5 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-bold shadow-lg flex items-center justify-center gap-2`}
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                Generate AI Matches
              </button>
            </div>

            {matchedJobs.map((job, idx) => (
              <JobCard key={idx} job={job} showMetrics={true} />
            ))}
          </div>
        )}

        {activeTab === "Live Jobs" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-3xl font-bold text-white">Live Job Search</h2>
              <p className="text-slate-400 mt-1">Browse real-time job postings directly from the market.</p>
            </div>

            <div className="flex gap-3">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Job title (e.g., AI Engineer, Backend Developer)..."
                className="flex-1 px-4 py-3 rounded-xl bg-[#121723] border border-slate-800 text-white text-sm"
              />
              <button
                onClick={handleLiveSearch}
                disabled={loading}
                className={`px-6 py-3 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-semibold flex items-center gap-2`}
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                Search
              </button>
            </div>

            {liveJobs.map((job, idx) => (
              <JobCard key={idx} job={job} showMetrics={false} />
            ))}
          </div>
        )}

        {activeTab === "Saved Jobs" && (
          <div className="space-y-6">
            <h2 className="text-3xl font-bold text-white">Saved Jobs ({savedJobs.length})</h2>
            {savedJobs.length === 0 ? (
              <div className="p-12 text-center rounded-2xl bg-[#121723] border border-slate-800 text-slate-400">
                No saved jobs yet. Click &quot;Save Job&quot; on any job card to bookmark it here.
              </div>
            ) : (
              savedJobs.map((job, idx) => <JobCard key={idx} job={job} showMetrics={true} />)
            )}
          </div>
        )}

        {activeTab === "CV Builder" && (
          <div className="space-y-6">
            <div className="flex flex-wrap justify-between items-center gap-4">
              <div>
                <h2 className="text-3xl font-bold text-white">ATS-Optimized CV Builder</h2>
                <p className="text-slate-400 mt-1">Live preview & instant Word (.docx) export tailored for ATS parsers.</p>
              </div>
              <button
                onClick={handleDownloadCV}
                className={`px-6 py-3 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-bold shadow-lg flex items-center gap-2`}
              >
                <Download className="w-4 h-4" /> Download ATS CV (.docx)
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <div className="bg-[#121723] p-6 rounded-2xl border border-slate-800 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-400">Full Name</label>
                    <input
                      value={builder.name}
                      onChange={(e) => setBuilder({ ...builder, name: e.target.value })}
                      className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">Professional Title</label>
                    <input
                      value={builder.title}
                      onChange={(e) => setBuilder({ ...builder, title: e.target.value })}
                      className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <input
                    placeholder="Email"
                    value={builder.email}
                    onChange={(e) => setBuilder({ ...builder, email: e.target.value })}
                    className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white"
                  />
                  <input
                    placeholder="Phone"
                    value={builder.phone}
                    onChange={(e) => setBuilder({ ...builder, phone: e.target.value })}
                    className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white"
                  />
                  <input
                    placeholder="LinkedIn"
                    value={builder.linkedin}
                    onChange={(e) => setBuilder({ ...builder, linkedin: e.target.value })}
                    className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white"
                  />
                </div>
                {(["summary", "experience", "projects", "education", "skills", "languages"] as const).map((field) => (
                  <div key={field}>
                    <label className="text-xs uppercase text-slate-400">{field}</label>
                    <textarea
                      rows={2}
                      value={builder[field]}
                      onChange={(e) => setBuilder({ ...builder, [field]: e.target.value })}
                      className="w-full mt-1 p-3 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white"
                    />
                  </div>
                ))}
              </div>

              <div className="bg-white text-slate-900 p-8 rounded-xl shadow-2xl min-h-[750px] font-sans">
                <div className="text-center border-b border-slate-300 pb-4">
                  <h1 className="text-2xl font-bold uppercase tracking-wide">{builder.name}</h1>
                  <p className="text-sm font-semibold text-slate-700 mt-0.5">{builder.title}</p>
                  <p className="text-xs text-slate-500 mt-1">
                    {builder.email} | {builder.phone} | {builder.linkedin}
                  </p>
                </div>
                <div className="space-y-4 mt-4 text-xs leading-relaxed">
                  <div>
                    <h3 className="font-bold uppercase border-b border-slate-300 pb-0.5 mb-1">Summary</h3>
                    <p>{builder.summary}</p>
                  </div>
                  <div>
                    <h3 className="font-bold uppercase border-b border-slate-300 pb-0.5 mb-1">Experience</h3>
                    <ul className="list-disc pl-4 space-y-1">
                      {builder.experience.split("\n").filter(Boolean).map((line, i) => (
                        <li key={i}>{line}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3 className="font-bold uppercase border-b border-slate-300 pb-0.5 mb-1">Projects</h3>
                    <ul className="list-disc pl-4 space-y-1">
                      {builder.projects.split("\n").filter(Boolean).map((line, i) => (
                        <li key={i}>{line}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3 className="font-bold uppercase border-b border-slate-300 pb-0.5 mb-1">Education</h3>
                    <p>{builder.education}</p>
                  </div>
                  <div>
                    <h3 className="font-bold uppercase border-b border-slate-300 pb-0.5 mb-1">Technical Skills</h3>
                    <p>{builder.skills}</p>
                  </div>
                  <div>
                    <h3 className="font-bold uppercase border-b border-slate-300 pb-0.5 mb-1">Languages</h3>
                    <p>{builder.languages}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "Domain AI" && (
          <div className="space-y-6">
            <h2 className="text-3xl font-bold text-white">Domain Intelligence</h2>
            <select
              value={selectedDomain}
              onChange={(e) => setSelectedDomain(e.target.value)}
              className="w-full md:w-96 px-4 py-3 rounded-xl bg-[#121723] border border-slate-800 text-white"
            >
              <option>Machine Learning / AI</option>
              <option>Data Science & Analytics</option>
              <option>Software Engineering</option>
              <option>Cloud & DevOps</option>
              <option>Cybersecurity</option>
            </select>

            <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800 space-y-4">
              <h3 className="text-xl font-bold text-white">{selectedDomain}</h3>
              <p className="text-slate-400 text-sm">
                Core high-demand skills detected across top market postings in this domain:
              </p>
              <div className="flex flex-wrap gap-2">
                {(selectedDomain === "Machine Learning / AI"
                  ? ["Python", "PyTorch", "TensorFlow", "Scikit-Learn", "NLP", "Computer Vision", "FastAPI", "Docker"]
                  : selectedDomain === "Data Science & Analytics"
                  ? ["Python", "SQL", "Pandas", "Power BI", "Tableau", "Statistical Modeling"]
                  : selectedDomain === "Software Engineering"
                  ? ["TypeScript", "React", "Next.js", "Node.js", "Python", "FastAPI", "C++", "PostgreSQL"]
                  : selectedDomain === "Cloud & DevOps"
                  ? ["AWS", "Docker", "Kubernetes", "Terraform", "CI/CD", "Linux"]
                  : ["Network Security", "Linux", "Penetration Testing", "SIEM", "SOC"]
                ).map((s) => (
                  <span key={s} className={`px-4 py-1.5 rounded-full text-xs font-semibold border ${currentTheme.badge}`}>
                    {s}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}