"use client";

import Image from "next/image";
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
import { supabase } from "../lib/supabase";

const API_BASE = "";
type ThemeKey = "blue" | "emerald" | "purple";

interface Job {
  Title: string; Company: string; Location: string; Description: string;
  Match_Score?: number; Skill_Pct?: number; Exp_Pct?: number; Level_Pct?: number;
  Matched_Skills?: string[]; Missing_Skills?: string[]; Apply_Link?: string;
}

interface CVData {
  role?: string; skills?: string[]; experience_level?: number; career_level?: string;
  contact_info?: { email?: string; phone?: string; };
}

const THEMES: Record<ThemeKey, { name: string; primary: string; badge: string; border: string; glow: string }> = {
  blue: { name: "Cyber Blue", primary: "from-indigo-600 to-sky-500", badge: "bg-sky-500/10 text-sky-400 border-sky-500/30", border: "border-sky-500", glow: "shadow-sky-500/20" },
  emerald: { name: "Emerald AI", primary: "from-emerald-600 to-teal-500", badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30", border: "border-emerald-500", glow: "shadow-emerald-500/20" },
  purple: { name: "Royal Nebula", primary: "from-purple-600 to-pink-500", badge: "bg-purple-500/10 text-purple-400 border-purple-500/30", border: "border-purple-500", glow: "shadow-purple-500/20" },
};

export default function JobMatchPlatform() {
  const [activeTab, setActiveTab] = useState("Home");
  const [theme, setTheme] = useState<ThemeKey>("blue");
  const currentTheme = THEMES[theme];

  // --- Auth & Session States ---
  const [user, setUser] = useState<any>(null);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");

  const [cvData, setCvData] = useState<CVData | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [country, setCountry] = useState("eg");
  const [loading, setLoading] = useState(false);
  const [matchedJobs, setMatchedJobs] = useState<Job[]>([]);
  const [liveJobs, setLiveJobs] = useState<Job[]>([]);
  const [savedJobs, setSavedJobs] = useState<Job[]>([]);

  const [manualSkills, setManualSkills] = useState("");
  const [manualExp, setManualExp] = useState(2);
  const [manualLevel, setManualLevel] = useState("Entry Level");
  const [searchQuery, setSearchQuery] = useState("AI Engineer");
  const [selectedDomain, setSelectedDomain] = useState("Machine Learning / AI");

  const [builder, setBuilder] = useState({
    name: "Omar Tarek Hamed",
    title: "AI Engineer",
    email: "eldeebomar440@gmail.com",
    phone: "+20 10X XXX XXXX",
    linkedin: "linkedin.com/in/omar-tarek-6b9611332",
    summary: "AI and Machine Learning Engineering student at Tanta University with hands-on experience in data analysis, predictive modeling, and developing end-to-end AI applications.",
    experience: "Freelance AI Engineer & Data Analyst (Mostaql, Khamsat, Nafezly)\nDigital Egypt Pioneers Initiative (DEPI) - Trainee (2026)\nNTI Summer Training - AI & ML Intern (2026)",
    projects: "VYRO - Career Intelligence Platform (Python, FastAPI, Scikit-learn, Streamlit)\nMyTracker - AI Habit-Tracking Web App\nMazeBot - Autonomous Maze-Solving Robot (1st Place)",
    education: "B.Sc. in Artificial Intelligence Engineering, Faculty of Engineering, Tanta University",
    skills: "Python, Scikit-learn, TensorFlow, Keras, PyTorch, OpenCV, NLP, FastAPI, Streamlit, Machine Learning, Deep Learning",
    languages: "Arabic (Native)\nEnglish (Intermediate)"
  });

  useEffect(() => {
    const timer = setTimeout(() => {
      const saved = localStorage.getItem("jobmatch_saved");
      if (saved) {
        try { setSavedJobs(JSON.parse(saved)); } catch (e) { console.error(e); }
      }
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  // --- Supabase Auth Effect ---
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });
    return () => subscription.unsubscribe();
  }, []);

  // --- Auth Functions ---
  const handleSignUp = async () => {
    if (!authEmail || !authPassword) return alert("يرجى إدخال الإيميل والباسورد");
    const { error } = await supabase.auth.signUp({ email: authEmail, password: authPassword });
    if (error) alert(error.message);
    else alert("تم إنشاء الحساب! يمكنك تسجيل الدخول الآن.");
  };

  const handleSignIn = async () => {
    if (!authEmail || !authPassword) return;
    const { error } = await supabase.auth.signInWithPassword({ email: authEmail, password: authPassword });
    if (error) alert("خطأ في تسجيل الدخول. تأكد من البيانات.");
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
  };

  const toggleSaveJob = (job: Job) => {
    const exists = savedJobs.some((j) => j.Title === job.Title && j.Company === job.Company);
    const updated = exists ? savedJobs.filter((j) => !(j.Title === job.Title && j.Company === job.Company)) : [...savedJobs, job];
    setSavedJobs(updated);
    localStorage.setItem("jobmatch_saved", JSON.stringify(updated));
  };

  const handleAnalyzeCV = async () => {
    if (!selectedFile) return;
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const res = await fetch(`${API_BASE}/api/analyze-cv`, { method: "POST", body: formData });
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
      alert("حدث خطأ أثناء تحليل الـ CV.");
    } finally { setLoading(false); }
  };

  const handleMatchCVJobs = async () => {
    if (!cvData) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/match-cv-jobs`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...cvData, country_code: country }),
      });
      if (!res.ok) throw new Error("Failed to match jobs");
      const data = await res.json();
      setMatchedJobs(data.jobs || []);
    } catch (err) { console.error(err); } finally { setLoading(false); }
  };

  const handleManualMatch = async () => {
    if (!manualSkills.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/manual-recommendations`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skills: manualSkills, experience_years: manualExp, career_level: manualLevel, country_code: country }),
      });
      if (!res.ok) throw new Error("Failed to fetch recommendations");
      const data = await res.json();
      setMatchedJobs(data.jobs || []);
    } catch (err) { console.error(err); } finally { setLoading(false); }
  };

  const handleLiveSearch = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/live-jobs?query=${encodeURIComponent(searchQuery)}&country=${encodeURIComponent(country)}`);
      if (!res.ok) throw new Error("Failed to search live jobs");
      const data = await res.json();
      setLiveJobs(data.jobs || []);
    } catch (err) { console.error(err); } finally { setLoading(false); }
  };

  const handleDownloadCV = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/build-cv`, {
        method: "POST", headers: { "Content-Type": "application/json" },
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
    } catch (err) { console.error(err); }
  };

  const JobCard = ({ job, showMetrics = true }: { job: Job; showMetrics?: boolean }) => {
    const isSaved = savedJobs.some((j) => j.Title === job.Title && j.Company === job.Company);
    return (
      <div className="bg-[#121723] border border-slate-800/80 hover:border-slate-700 rounded-2xl p-6 mb-5 transition-all duration-300 shadow-lg hover:shadow-xl">
        <div className="flex flex-wrap justify-between items-start gap-4 mb-3">
          <div>
            <div className="flex items-center gap-3">
              <h3 className="text-xl font-bold text-white">{job.Title}</h3>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-semibold">LIVE API</span>
            </div>
            <div className="flex items-center gap-4 text-slate-400 text-sm mt-2">
              <span className="flex items-center gap-1.5"><Building2 className="w-4 h-4 text-slate-500" /> {job.Company}</span>
              <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4 text-slate-500" /> {job.Location}</span>
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
              <div className="flex justify-between text-xs text-slate-400 mb-1"><span>Skills Alignment</span><span className="text-sky-400 font-semibold">{job.Skill_Pct}%</span></div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden"><div className="h-full bg-sky-500 rounded-full" style={{ width: `${job.Skill_Pct}%` }} /></div>
            </div>
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1"><span>Experience Match</span><span className="text-emerald-400 font-semibold">{job.Exp_Pct}%</span></div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden"><div className="h-full bg-emerald-500 rounded-full" style={{ width: `${job.Exp_Pct}%` }} /></div>
            </div>
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1"><span>Career Level Fit</span><span className="text-amber-400 font-semibold">{job.Level_Pct}%</span></div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden"><div className="h-full bg-amber-500 rounded-full" style={{ width: `${job.Level_Pct}%` }} /></div>
            </div>
          </div>
        )}
        <p className="text-slate-400 text-sm leading-relaxed mb-4 line-clamp-3">{job.Description}</p>
        {showMetrics && (job.Matched_Skills?.length || job.Missing_Skills?.length) ? (
          <div className="mb-5 space-y-2">
            <div className="flex flex-wrap gap-2">
              {job.Matched_Skills?.slice(0, 8).map((s: string) => (
                <span key={s} className="inline-flex items-center gap-1 text-xs px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><CheckCircle2 className="w-3 h-3" /> {s}</span>
              ))}
              {job.Missing_Skills?.slice(0, 6).map((s: string) => (
                <span key={s} className="inline-flex items-center gap-1 text-xs px-3 py-1 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20"><XCircle className="w-3 h-3" /> {s}</span>
              ))}
            </div>
          </div>
        ) : null}
        <div className="flex items-center gap-3 pt-3 border-t border-slate-800/80">
          {job.Apply_Link && job.Apply_Link !== "#" && (
            <a href={job.Apply_Link} target="_blank" rel="noreferrer" className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white text-sm font-semibold hover:opacity-95 transition shadow-md`}>
              Apply Now <ExternalLink className="w-4 h-4" />
            </a>
          )}
          <button onClick={() => toggleSaveJob(job)} className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-medium transition ${isSaved ? "bg-amber-500/10 border-amber-500/40 text-amber-400" : "border-slate-700 text-slate-300 hover:bg-slate-800"}`}>
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
            <Image 
              src="/logojpeg.jpeg" 
              alt="VYRO Logo"
              width={48} 
              height={48} 
              className="rounded-xl shadow-lg object-cover"
            />
            <div>
              <h1 className="text-2xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-sky-400 tracking-widest">
                VYRO
              </h1>
              <p className="text-[9px] tracking-widest text-slate-400 uppercase mt-0.5">AI Career Intelligence</p>
            </div>
          </div>
          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id} onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${active ? `bg-gradient-to-r ${currentTheme.primary} text-white shadow-lg ${currentTheme.glow}` : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"}`}
                >
                  <Icon className="w-4 h-4" />{item.label}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="mt-8 pt-6 border-t border-slate-800/80 space-y-4">
          {/* --- Auth Section --- */}
          <div className="mb-6 p-4 rounded-xl bg-slate-900/50 border border-slate-800">
            {user ? (
              <div className="text-xs text-slate-400">
                Logged in as <span className="text-emerald-400 font-bold block truncate mt-1">{user.email}</span>
                <button onClick={handleSignOut} className="mt-3 w-full py-1.5 rounded bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 font-bold transition">Sign Out</button>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-slate-400 mb-2 font-semibold">User Account</p>
                <input type="email" placeholder="Email" value={authEmail} onChange={e => setAuthEmail(e.target.value)} className="w-full px-3 py-1.5 rounded-lg bg-[#0b0e14] border border-slate-800 text-xs text-white focus:border-sky-500 outline-none" />
                <input type="password" placeholder="Password" value={authPassword} onChange={e => setAuthPassword(e.target.value)} className="w-full px-3 py-1.5 rounded-lg bg-[#0b0e14] border border-slate-800 text-xs text-white focus:border-sky-500 outline-none" />
                <div className="flex gap-2 pt-1">
                  <button onClick={handleSignIn} className="flex-1 py-1.5 bg-sky-500/20 text-sky-400 rounded-lg text-xs font-bold hover:bg-sky-500/30 transition">Login</button>
                  <button onClick={handleSignUp} className="flex-1 py-1.5 border border-slate-700 text-slate-300 rounded-lg text-xs font-bold hover:bg-slate-800 transition">Sign Up</button>
                </div>
              </div>
            )}
          </div>

          <div>
            <span className="text-xs text-slate-400 flex items-center gap-1.5 mb-2"><Palette className="w-3.5 h-3.5" /> UI Theme</span>
            <div className="grid grid-cols-3 gap-2">
              {(Object.keys(THEMES) as ThemeKey[]).map((tKey) => (
                <button key={tKey} onClick={() => setTheme(tKey)} className={`py-1.5 px-2 rounded-lg text-xs font-medium border capitalize transition ${theme === tKey ? `${THEMES[tKey].badge} ${THEMES[tKey].border}` : "border-slate-800 text-slate-400 hover:bg-slate-800"}`}>{tKey}</button>
              ))}
            </div>
          </div>
          <div className="text-xs text-slate-500">FastAPI Serverless Engine<div className="text-emerald-400 font-semibold flex items-center gap-1.5 mt-0.5"><span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> v5.0 Integrated</div></div>
        </div>
      </aside>

      <main className="flex-1 p-6 md:p-10 overflow-y-auto max-w-6xl mx-auto w-full">
        {!user && activeTab !== "Home" ? (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-sky-500/10 flex items-center justify-center mb-2"><Sparkles className="w-8 h-8 text-sky-400" /></div>
            <h2 className="text-2xl font-bold text-white">Authentication Required</h2>
            <p className="text-slate-400 max-w-md">Please login or sign up from the sidebar to access AI Analyzer, Jobs, and the ATS Builder.</p>
          </div>
        ) : (
          <>
            {activeTab === "Home" && (
              <div className="space-y-8">
                <div className="p-8 rounded-3xl bg-gradient-to-br from-slate-900 via-[#13192b] to-slate-900 border border-slate-800/80 shadow-2xl">
                  <span className={`inline-block text-xs font-semibold px-3 py-1 rounded-full border mb-4 ${currentTheme.badge}`}>AI-POWERED RECRUITMENT ENGINE</span>
                  <h2 className="text-3xl md:text-5xl font-extrabold text-white tracking-tight mb-4">Your Intelligent Career Copilot.</h2>
                  <p className="text-slate-400 text-lg max-w-2xl mb-6 leading-relaxed">We bridge the gap between your technical skills and live market demands using Machine Learning, NLP Vectorization, and Real-Time Job Matching.</p>
                  <div className="flex flex-wrap gap-4">
                    <button onClick={() => setActiveTab("CV Analyzer")} className={`px-6 py-3 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-semibold shadow-lg hover:opacity-95 transition flex items-center gap-2`}><Upload className="w-4 h-4" /> Analyze My CV Now</button>
                    <button onClick={() => setActiveTab("CV Builder")} className="px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold transition flex items-center gap-2"><FileSignature className="w-4 h-4" /> Build ATS Resume</button>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800/80 text-center"><p className="text-xs uppercase tracking-wider text-slate-400">Jobs Analyzed</p><p className="text-3xl font-extrabold text-white mt-2">353,052+</p></div>
                  <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800/80 text-center"><p className="text-xs uppercase tracking-wider text-slate-400">Active Tech Domains</p><p className="text-3xl font-extrabold text-white mt-2">19 Domains</p></div>
                  <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800/80 text-center"><p className="text-xs uppercase tracking-wider text-slate-400">Saved Opportunities</p><p className="text-3xl font-extrabold text-white mt-2">{savedJobs.length}</p></div>
                </div>
              </div>
            )}
            
            {activeTab === "CV Analyzer" && (
              <div className="space-y-6">
                <div><h2 className="text-3xl font-bold text-white">AI CV Analyzer</h2><p className="text-slate-400 mt-1">Upload your resume for deep semantic skill extraction.</p></div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 bg-[#121723] p-6 rounded-2xl border border-slate-800">
                  <div className="md:col-span-3">
                    <label className="block text-xs uppercase text-slate-400 mb-2">Upload Resume</label>
                    <input type="file" accept=".pdf,.docx,.txt" onChange={(e) => setSelectedFile(e.target.files?.[0] || null)} className="w-full text-sm text-slate-300 file:mr-4 file:py-2.5 file:px-4 file:rounded-xl file:border-0 file:bg-slate-800 file:text-white cursor-pointer bg-slate-900/70 p-2 border border-slate-800" />
                  </div>
                  <div>
                    <label className="block text-xs uppercase text-slate-400 mb-2">Country</label>
                    <input type="text" value={country} onChange={(e) => setCountry(e.target.value)} className="w-full px-4 py-3 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm" />
                  </div>
                  <div className="md:col-span-4">
                    <button onClick={handleAnalyzeCV} disabled={!selectedFile || loading} className={`w-full py-3.5 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-bold flex justify-center items-center gap-2`} >
                      {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />} Analyze My CV
                    </button>
                  </div>
                </div>
                {cvData && (
                  <div className="space-y-6 animate-fadeIn">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      <div className="p-5 rounded-2xl bg-[#121723] border border-slate-800"><span className="text-xs text-slate-400 uppercase">Predicted Role</span><p className="text-lg font-bold text-sky-400 mt-1">{cvData.role}</p></div>
                      <div className="p-5 rounded-2xl bg-[#121723] border border-slate-800"><span className="text-xs text-slate-400 uppercase">Skills Extracted</span><p className="text-2xl font-extrabold text-white mt-1">{cvData.skills?.length || 0}</p></div>
                      <div className="p-5 rounded-2xl bg-[#121723] border border-slate-800"><span className="text-xs text-slate-400 uppercase">Est. Experience</span><p className="text-2xl font-extrabold text-white mt-1">{cvData.experience_level} Years</p></div>
                      <div className="p-5 rounded-2xl bg-[#121723] border border-slate-800"><span className="text-xs text-slate-400 uppercase">Career Level</span><p className="text-xl font-bold text-emerald-400 mt-1">{cvData.career_level}</p></div>
                    </div>
                    <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800">
                      <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">Extracted Technical Skills</h3>
                      <div className="flex flex-wrap gap-2">{cvData.skills?.map(skill => <span key={skill} className="px-3.5 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">✓ {skill}</span>)}</div>
                    </div>
                    <button onClick={handleMatchCVJobs} disabled={loading} className={`w-full py-3.5 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-bold flex justify-center items-center gap-2`}>
                      {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />} Find Live Jobs Matching My CV
                    </button>
                    {matchedJobs.length > 0 && <div className="mt-6"><h3 className="text-xl font-bold text-white mb-4">Top Matches</h3>{matchedJobs.map((job, idx) => <JobCard key={idx} job={job} />)}</div>}
                  </div>
                )}
              </div>
            )}

            {activeTab === "AI Recommendations" && (
              <div className="space-y-6">
                <div><h2 className="text-3xl font-bold text-white">AI Job Recommendations</h2><p className="text-slate-400 mt-1">Enter stack manually for AI matching.</p></div>
                <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800 space-y-4">
                  <textarea rows={3} value={manualSkills} onChange={e => setManualSkills(e.target.value)} placeholder="e.g., python, react, sql..." className="w-full p-4 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm" />
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <input type="number" step="0.5" value={manualExp} onChange={e => setManualExp(parseFloat(e.target.value)||0)} className="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm" />
                    <select value={manualLevel} onChange={e => setManualLevel(e.target.value)} className="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm"><option>Student</option><option>Entry Level</option><option>Experienced</option><option>Manager</option></select>
                    <input type="text" value={country} onChange={e => setCountry(e.target.value)} className="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm" />
                  </div>
                  <button onClick={handleManualMatch} disabled={loading} className={`w-full py-3.5 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-bold flex justify-center items-center gap-2`}>
                    {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />} Generate AI Matches
                  </button>
                </div>
                {matchedJobs.map((job, idx) => <JobCard key={idx} job={job} />)}
              </div>
            )}

            {activeTab === "Live Jobs" && (
              <div className="space-y-6">
                <div className="flex gap-3">
                  <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Job title..." className="flex-1 px-4 py-3 rounded-xl bg-[#121723] border border-slate-800 text-white text-sm" />
                  <button onClick={handleLiveSearch} disabled={loading} className={`px-6 py-3 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-semibold flex items-center gap-2`}>{loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />} Search</button>
                </div>
                {liveJobs.map((job, idx) => <JobCard key={idx} job={job} showMetrics={false} />)}
              </div>
            )}

            {activeTab === "Saved Jobs" && (
              <div className="space-y-6">
                <h2 className="text-3xl font-bold text-white">Saved Jobs ({savedJobs.length})</h2>
                {savedJobs.length === 0 ? <div className="p-12 text-center text-slate-400 bg-[#121723] rounded-2xl">No saved jobs yet.</div> : savedJobs.map((job, idx) => <JobCard key={idx} job={job} />)}
              </div>
            )}

            {activeTab === "CV Builder" && (
              <div className="space-y-6">
                <div className="flex flex-wrap justify-between items-center gap-4">
                  <div><h2 className="text-3xl font-bold text-white">ATS-Optimized CV Builder</h2></div>
                  <button onClick={handleDownloadCV} className={`px-6 py-3 rounded-xl bg-gradient-to-r ${currentTheme.primary} text-white font-bold flex items-center gap-2`}><Download className="w-4 h-4" /> Download .docx</button>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  <div className="bg-[#121723] p-6 rounded-2xl border border-slate-800 space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <input value={builder.name} onChange={e => setBuilder({ ...builder, name: e.target.value })} className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white" />
                      <input value={builder.title} onChange={e => setBuilder({ ...builder, title: e.target.value })} className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white" />
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <input value={builder.email} onChange={e => setBuilder({ ...builder, email: e.target.value })} className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white" />
                      <input value={builder.phone} onChange={e => setBuilder({ ...builder, phone: e.target.value })} className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white" />
                      <input value={builder.linkedin} onChange={e => setBuilder({ ...builder, linkedin: e.target.value })} className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white" />
                    </div>
                    {(["summary", "experience", "projects", "education", "skills", "languages"] as const).map(field => (
                      <div key={field}><label className="text-xs uppercase text-slate-400">{field}</label><textarea rows={2} value={builder[field]} onChange={e => setBuilder({ ...builder, [field]: e.target.value })} className="w-full mt-1 p-3 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white" /></div>
                    ))}
                  </div>
                  <div className="bg-white text-slate-900 p-8 rounded-xl min-h-[750px] font-sans">
                    <div className="text-center border-b border-slate-300 pb-4"><h1 className="text-2xl font-bold uppercase">{builder.name}</h1><p className="font-semibold mt-0.5">{builder.title}</p></div>
                    <div className="space-y-4 mt-4 text-xs">
                      <div><h3 className="font-bold uppercase border-b border-slate-300 pb-0.5 mb-1">Summary</h3><p>{builder.summary}</p></div>
                      <div><h3 className="font-bold uppercase border-b border-slate-300 pb-0.5 mb-1">Experience</h3><ul className="list-disc pl-4">{builder.experience.split("\n").filter(Boolean).map((l, i) => <li key={i}>{l}</li>)}</ul></div>
                      <div><h3 className="font-bold uppercase border-b border-slate-300 pb-0.5 mb-1">Projects</h3><ul className="list-disc pl-4">{builder.projects.split("\n").filter(Boolean).map((l, i) => <li key={i}>{l}</li>)}</ul></div>
                      <div><h3 className="font-bold uppercase border-b border-slate-300 pb-0.5 mb-1">Skills</h3><p>{builder.skills}</p></div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "Domain AI" && (
              <div className="space-y-6">
                <h2 className="text-3xl font-bold text-white">Domain Intelligence</h2>
                <select value={selectedDomain} onChange={e => setSelectedDomain(e.target.value)} className="w-full md:w-96 px-4 py-3 rounded-xl bg-[#121723] border border-slate-800 text-white">
                  <option>Machine Learning / AI</option><option>Data Science & Analytics</option><option>Software Engineering</option><option>Cloud & DevOps</option><option>Cybersecurity</option>
                </select>
                <div className="p-6 rounded-2xl bg-[#121723] border border-slate-800 space-y-4">
                  <h3 className="text-xl font-bold text-white">{selectedDomain}</h3>
                  <div className="flex flex-wrap gap-2">
                    {["Python", "PyTorch", "TensorFlow", "Scikit-Learn", "FastAPI"].map((s) => <span key={s} className={`px-4 py-1.5 rounded-full text-xs font-semibold border ${currentTheme.badge}`}>{s}</span>)}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
