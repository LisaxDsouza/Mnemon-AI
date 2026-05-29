"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Shield, 
  Activity, 
  Compass, 
  Settings, 
  MessageSquare, 
  Sliders, 
  Plus, 
  Trash2, 
  Play, 
  Pause, 
  ExternalLink, 
  ChevronRight, 
  ChevronDown, 
  Search, 
  Clock, 
  Database,
  RefreshCw,
  Sparkles,
  Info,
  CheckCircle,
  FileText,
  Video,
  Monitor
} from "lucide-react";

// Inline GitHub icon to prevent version mismatch in lucide-react exports
const GithubIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
    <path d="M9 18c-4.51 2-5-2-7-2" />
  </svg>
);


const BACKEND_URL = "http://localhost:8000";

interface MemoryEvent {
  id: string;
  url: string;
  title: string;
  source_type: string;
  event_type: string;
  duration: number;
  scroll_depth: number;
  engagement_score: number;
  created_at: string;
  content_preview?: string;
}

interface SessionItem {
  id: string;
  title: string;
  topic: string;
  summary: string;
  started_at: string;
  ended_at: string;
  memories: Array<{
    id: string;
    title: string;
    url: string;
    source_type: string;
    created_at: string;
  }>;
}

interface AgentLog {
  agent: string;
  action: string;
}

interface ReflectionItem {
  topic: string;
  weight: number;
  rationale: string;
}

export default function Dashboard() {
  // Navigation & Onboarding States
  const [userId, setUserId] = useState<string | null>(null);
  const [isOnboarding, setIsOnboarding] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<string>("timeline");
  const [apiOnline, setApiOnline] = useState<boolean>(true);

  // Onboarding Signup State
  const [email, setEmail] = useState("");
  const [signupCategories, setSignupCategories] = useState<string[]>([
    "articles", "youtube", "github", "pdf"
  ]);
  const [signupBlocks, setSignupBlocks] = useState("facebook.com, twitter.com, reddit.com");
  const [signupPrivacy, setSignupPrivacy] = useState("balanced");

  // Dashboard Data States
  const [timeline, setTimeline] = useState<MemoryEvent[]>([]);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [blockedDomains, setBlockedDomains] = useState<Array<{id: string, domain: string, wildcard: boolean}>>([]);
  const [categories, setCategories] = useState<Record<string, boolean>>({
    articles: true, youtube: true, github: true, pdf: true, social_media: false, ai_chats: false
  });
  const [privacyMode, setPrivacyMode] = useState("balanced");
  const [pauseMinutes, setPauseMinutes] = useState(10);
  const [isPauseActive, setIsPauseActive] = useState(false);
  const [reflections, setReflections] = useState<ReflectionItem[]>([]);

  // Agent Chat State
  const [queryText, setQueryText] = useState("");
  const [queryResponse, setQueryResponse] = useState("");
  const [citation, setCitation] = useState<any>(null);
  const [agentLogs, setAgentLogs] = useState<AgentLog[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  // Extension Simulator Widget State
  const [simUrl, setSimUrl] = useState("https://react.dev/reference/react/hooks");
  const [simTitle, setSimTitle] = useState("React Hooks Reference – React");
  const [simTabId, setSimTabId] = useState<number>(404);
  const [simStatus, setSimStatus] = useState<string>("idle");
  const [simDuration, setSimDuration] = useState<number>(0);
  const [simScroll, setSimScroll] = useState<number>(0);
  const [simLogs, setSimLogs] = useState<string[]>([]);
  const [simEventId, setSimEventId] = useState<string | null>(null);

  // UI Expanded Sessions list
  const [expandedSessions, setExpandedSessions] = useState<Record<string, boolean>>({});

  // Refs for auto-timers
  const simTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Force default-user for local testing and extension alignment
    localStorage.setItem("recall_user_id", "default-user");
    setUserId("default-user");
    setIsOnboarding(false);
    
    // Check API Status and fetch initial data
    checkApiHealth();
  }, []);

  useEffect(() => {
    if (userId) {
      fetchDashboardData();
    }
  }, [userId, activeTab]);

  const checkApiHealth = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/`);
      if (res.ok) {
        setApiOnline(true);
      } else {
        setApiOnline(false);
      }
    } catch {
      setApiOnline(false);
    }
  };

  const fetchDashboardData = async () => {
    if (!userId) return;
    await checkApiHealth();
    
    try {
      // 1. Fetch Timeline
      const timelineRes = await fetch(`${BACKEND_URL}/timeline?user_id=${userId}`);
      if (timelineRes.ok) {
        setTimeline(await timelineRes.json());
      }

      // 2. Fetch Sessions
      const sessionsRes = await fetch(`${BACKEND_URL}/sessions?user_id=${userId}`);
      if (sessionsRes.ok) {
        setSessions(await sessionsRes.json());
      }

      // 3. Fetch runtime configuration (privacy settings)
      const configRes = await fetch(`${BACKEND_URL}/runtime-config?user_id=${userId}`);
      if (configRes.ok) {
        const config = await configRes.json();
        setCategories(config.allowed_categories);
        setPrivacyMode(config.privacy_mode);
        setIsPauseActive(!config.capture_enabled);
      }

      // 4. Fetch Blocked Domains list
      const blockedRes = await fetch(`${BACKEND_URL}/privacy/blocked-domains?user_id=${userId}`);
      if (blockedRes.ok) {
        setBlockedDomains(await blockedRes.json());
      }

      // 5. Fetch Interest Reflections
      const reflectionRes = await fetch(`${BACKEND_URL}/privacy/reflection?user_id=${userId}`);
      if (reflectionRes.ok) {
        const data = await reflectionRes.json();
        setReflections(data.reflection || []);
      }
    } catch (e) {
      console.error("Dashboard: Error fetching records", e);
    }
  };

  // --- Actions ---

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    const blockList = signupBlocks.split(",")
      .map(d => d.trim())
      .filter(d => d.length > 0);

    try {
      const res = await fetch(`${BACKEND_URL}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          allowed_categories: signupCategories,
          blocked_domains: blockList,
          privacy_mode: signupPrivacy
        })
      });

      if (res.ok) {
        const data = await res.json();
        const newUserId = data.user_id;
        localStorage.setItem("recall_user_id", newUserId);
        setUserId(newUserId);
        setIsOnboarding(false);
      } else {
        alert("Failed to submit onboarding credentials.");
      }
    } catch (err) {
      alert("Backend API is currently offline. Please launch the backend server first!");
    }
  };

  const handleToggleCategory = async (cat: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/privacy/category-toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: cat,
          enabled: !categories[cat],
          user_id: userId
        })
      });
      if (res.ok) {
        setCategories(prev => ({ ...prev, [cat]: !prev[cat] }));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddBlockedDomain = async (domain: string) => {
    if (!domain.trim()) return;
    try {
      const res = await fetch(`${BACKEND_URL}/privacy/blocked-domains`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain: domain.trim(),
          wildcard: true,
          user_id: userId
        })
      });
      if (res.ok) {
        fetchDashboardData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteBlockedDomain = async (id: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/privacy/blocked-domains/${id}`, {
        method: "DELETE"
      });
      if (res.ok) {
        setBlockedDomains(prev => prev.filter(b => b.id !== id));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handlePauseCapture = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/privacy/pause`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          duration_minutes: pauseMinutes,
          user_id: userId
        })
      });
      if (res.ok) {
        setIsPauseActive(true);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleForceExtract = async (eventId: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/extract?event_id=${eventId}`, {
        method: "POST"
      });
      if (res.ok) {
        alert("Extraction triggered in background. Please refresh in a moment!");
        fetchDashboardData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleTriggerClustering = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/sessions/trigger-clustering?user_id=${userId}`, {
        method: "POST"
      });
      if (res.ok) {
        const data = await res.json();
        alert(`Clustering complete: ${data.sessions_created} session(s) created!`);
        fetchDashboardData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm("Are you sure you want to delete this session? This will remove all associated memory logs and vector indices.")) return;
    try {
      const res = await fetch(`${BACKEND_URL}/privacy/delete-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          user_id: userId
        })
      });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== sessionId));
        fetchDashboardData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handlePurgeAll = async () => {
    if (!confirm("CRITICAL WARNING: This will permanently delete all browsing logs, session structures, and vector embeddings in your database. This action CANNOT be undone. Proceed?")) return;
    if (!confirm("Please double confirm: Purge all digital memory logs?")) return;

    try {
      const res = await fetch(`${BACKEND_URL}/privacy/delete-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId
        })
      });
      if (res.ok) {
        alert("All memories have been purged.");
        fetchDashboardData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // --- Agentic Chat Submit ---

  const handleAgentChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryText.trim()) return;

    setChatLoading(true);
    setQueryResponse("");
    setCitation(null);
    setAgentLogs([]);

    try {
      const res = await fetch(`${BACKEND_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: queryText,
          user_id: userId
        })
      });

      if (res.ok) {
        const data = await res.json();
        setQueryResponse(data.answer);
        setCitation(data.citation);
        setAgentLogs(data.agent_logs || []);
      } else {
        setQueryResponse("API Query processing failed.");
      }
    } catch (err) {
      setQueryResponse("Unable to connect to RAG server.");
    } finally {
      setChatLoading(false);
    }
  };

  // --- Extension Simulator Actions ---

  const handleSimTabLoad = async () => {
    setSimStatus("loading");
    setSimLogs([`[0.0s] Triggering URL load: ${simUrl}`]);
    setSimDuration(0);
    setSimScroll(0);
    setSimEventId(null);
    if (simTimerRef.current) clearInterval(simTimerRef.current);

    try {
      const res = await fetch(`${BACKEND_URL}/capture`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: simUrl,
          title: simTitle,
          tab_id: simTabId,
          user_id: userId
        })
      });

      if (res.ok) {
        const data = await res.json();
        if (data.status === "accepted" && data.event_id) {
          setSimEventId(data.event_id);
          setSimStatus("active");
          setSimLogs(prev => [...prev, `[0.5s] Capture Accepted! Logged ID: ${data.event_id}`, `[0.6s] Tracking engagement metrics (timer active)`]);
          
          // Start Simulator Timer
          let timeCount = 0;
          simTimerRef.current = setInterval(() => {
            timeCount += 5;
            setSimDuration(timeCount);
          }, 1000);
        } else {
          setSimStatus("rejected");
          setSimLogs(prev => [...prev, `[0.5s] Capture Rejected: ${data.reason || data.status}`]);
        }
      } else {
        setSimStatus("error");
        setSimLogs(prev => [...prev, `[0.5s] Capture API call returned error status.`]);
      }
    } catch (err) {
      setSimStatus("error");
      setSimLogs(prev => [...prev, `[0.5s] Network error contacting capture API.`]);
    }
  };

  const handleSimUpdateEngagement = async (addedDuration: number, finalScroll: number) => {
    if (!simEventId) return;
    const newDur = simDuration + addedDuration;
    setSimDuration(newDur);
    setSimScroll(finalScroll);

    setSimLogs(prev => [...prev, `[${newDur}s] Submitting metrics: duration=${newDur}s, scroll=${finalScroll}%`]);

    try {
      const res = await fetch(`${BACKEND_URL}/engagement`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tab_id: simTabId,
          duration: newDur,
          scroll_depth: finalScroll,
          user_id: userId
        })
      });

      if (res.ok) {
        const data = await res.json();
        setSimLogs(prev => [...prev, `[${newDur}s] Backend Response: status=${data.status}, score=${data.score}`]);
        if (data.status === "extracting") {
          setSimLogs(prev => [...prev, `🔥 [${newDur}s] Capture crossed thresholds! Auto-extraction triggered.`]);
          setSimStatus("extracted");
          if (simTimerRef.current) clearInterval(simTimerRef.current);
          
          // Refresh timeline automatically
          setTimeout(fetchDashboardData, 4000);
        }
      }
    } catch (err) {
      setSimLogs(prev => [...prev, `[error] Failed to update engagement`]);
    }
  };

  // Helper source icons
  const getSourceIcon = (type: string) => {
    switch (type) {
      case "youtube": return <Video className="w-4 h-4 text-red-500" />;
      case "github": return <GithubIcon className="w-4 h-4 text-purple-400" />;
      case "pdf": return <FileText className="w-4 h-4 text-blue-400" />;
      default: return <Compass className="w-4 h-4 text-cyan-400" />;
    }
  };

  // --- RENDER ONBOARDING VIEW ---
  if (isOnboarding) {
    return (
      <div className="min-h-screen bg-[#09090b] text-[#e4e4e7] flex items-center justify-center p-6 relative overflow-hidden font-sans">
        {/* Decorative background grid/glow */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.15),rgba(255,255,255,0))]" />
        
        <div className="w-full max-w-lg bg-[#18181b] border border-zinc-800 rounded-xl p-8 shadow-2xl relative z-10">
          <div className="flex justify-center mb-6">
            <div className="bg-gradient-to-r from-cyan-400 to-violet-500 p-2.5 rounded-xl shadow-lg shadow-violet-500/20">
              <Shield className="w-8 h-8 text-black" />
            </div>
          </div>

          <h2 className="text-2xl font-bold text-center bg-gradient-to-r from-cyan-400 to-violet-500 bg-clip-text text-transparent mb-2">
            Welcome to Recall AI
          </h2>
          <p className="text-zinc-400 text-sm text-center mb-8">
            Let's configure your local agentic memory layer and default privacy exclusions.
          </p>

          <form onSubmit={handleSignup} className="space-y-6">
            {/* Email Address */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                Identity / Email Address
              </label>
              <input 
                type="email" 
                required
                placeholder="developer@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full bg-[#09090b] border border-zinc-800 focus:border-cyan-400 text-sm p-3 rounded-lg outline-none transition-colors"
              />
            </div>

            {/* Allowed Categories */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                Allowed Content Types
              </label>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { id: "articles", label: "Articles & Web" },
                  { id: "youtube", label: "YouTube Learning" },
                  { id: "github", label: "GitHub Code" },
                  { id: "pdf", label: "PDF Documents" }
                ].map(item => (
                  <label 
                    key={item.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer select-none transition-all ${
                      signupCategories.includes(item.id) 
                        ? 'bg-violet-950/20 border-violet-500 text-white' 
                        : 'bg-[#09090b] border-zinc-800 text-zinc-400 hover:border-zinc-700'
                    }`}
                  >
                    <input 
                      type="checkbox"
                      checked={signupCategories.includes(item.id)}
                      onChange={() => {
                        if (signupCategories.includes(item.id)) {
                          setSignupCategories(signupCategories.filter(c => c !== item.id));
                        } else {
                          setSignupCategories([...signupCategories, item.id]);
                        }
                      }}
                      className="hidden"
                    />
                    <span className="text-sm font-medium">{item.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Default Excluded Domains */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                Domain Exclusions (Comma-separated)
              </label>
              <textarea 
                rows={2}
                value={signupBlocks}
                onChange={e => setSignupBlocks(e.target.value)}
                placeholder="domain.com, bank.com, auth.net"
                className="w-full bg-[#09090b] border border-zinc-800 focus:border-cyan-400 text-sm p-3 rounded-lg outline-none transition-colors resize-none"
              />
              <p className="text-[10px] text-zinc-500 mt-1">
                * Note: Financial networks, identity panels, and checkout forms are blocked by default.
              </p>
            </div>

            {/* Privacy Mode */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                Memory Storage Mode
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: "balanced", label: "Balanced", desc: "Dual Sync" },
                  { id: "strict", label: "Strict Mode", desc: "Filtered Sync" },
                  { id: "local", label: "Local Only", desc: "Zero Cloud" }
                ].map(mode => (
                  <button 
                    key={mode.id}
                    type="button"
                    onClick={() => setSignupPrivacy(mode.id)}
                    className={`p-3 rounded-lg border text-left flex flex-col transition-all ${
                      signupPrivacy === mode.id 
                        ? 'bg-cyan-950/20 border-cyan-400 text-white' 
                        : 'bg-[#09090b] border-zinc-800 text-zinc-400 hover:border-zinc-700'
                    }`}
                  >
                    <span className="text-sm font-bold">{mode.label}</span>
                    <span className="text-[9px] text-zinc-500 font-medium">{mode.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            <button 
              type="submit"
              className="w-full bg-gradient-to-r from-cyan-400 to-violet-500 hover:from-cyan-500 hover:to-violet-600 text-black font-semibold py-3.5 rounded-lg shadow-lg hover:shadow-cyan-400/10 active:scale-[0.99] transition-all text-sm flex items-center justify-center gap-2"
            >
              Initialize Memory Platform
              <ChevronRight className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    );
  }

  // --- MAIN DASHBOARD VIEW ---
  return (
    <div className="min-h-screen bg-[#09090b] text-[#e4e4e7] flex flex-col font-sans">
      {/* Top Banner (API Status check) */}
      {!apiOnline && (
        <div className="bg-red-950/50 border-b border-red-800 text-red-300 p-2.5 text-xs text-center font-medium flex items-center justify-center gap-2">
          <Info className="w-4 h-4 text-red-400" />
          Backend connection error. Make sure Python FastAPI is running at http://localhost:8000
        </div>
      )}

      {/* Main Header */}
      <header className="border-b border-zinc-900 bg-[#0e0f11] py-4 px-8 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-r from-cyan-400 to-violet-500 p-2 rounded-lg">
            <Shield className="w-5 h-5 text-black" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
              Recall AI
              <span className="text-[10px] bg-zinc-800 text-cyan-400 px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider">
                Active Memory
              </span>
            </h1>
            <p className="text-[10px] text-zinc-500 mt-0.5">
              Secure Semantic Memory Layer
            </p>
          </div>
        </div>

        {/* Global stats indicators */}
        <div className="flex items-center gap-6 text-xs">
          <div className="flex items-center gap-2 bg-zinc-900/60 border border-zinc-800 px-3 py-1.5 rounded-lg">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-zinc-400 font-medium">Logged:</span>
            <span className="text-white font-bold">{timeline.length} items</span>
          </div>

          <div className="flex items-center gap-2 bg-zinc-900/60 border border-zinc-800 px-3 py-1.5 rounded-lg">
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-zinc-400 font-medium">Index Status:</span>
            <span className="text-white font-bold">FAISS Local</span>
          </div>

          <button 
            onClick={fetchDashboardData}
            className="bg-zinc-850 hover:bg-zinc-800 border border-zinc-800 p-2 rounded-lg transition-colors"
            title="Refresh Data"
          >
            <RefreshCw className="w-3.5 h-3.5 text-zinc-400" />
          </button>
        </div>
      </header>

      {/* Workspace Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar Nav */}
        <nav className="w-64 border-r border-zinc-900 bg-[#0e0f11] p-6 flex flex-col justify-between">
          <div className="space-y-1">
            <div className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 mb-3 px-3">
              Memory Hub
            </div>
            
            {[
              { id: "timeline", label: "Memory Log", icon: Activity },
              { id: "sessions", label: "Browsing Sessions", icon: Compass },
              { id: "chat", label: "Agentic Search", icon: MessageSquare },
              { id: "simulator", label: "Extension Simulator", icon: Monitor },
              { id: "privacy", label: "Privacy Governance", icon: Settings }
            ].map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                    activeTab === tab.id 
                      ? 'bg-zinc-800 text-white border border-zinc-700/50 shadow-md' 
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-900/40'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${activeTab === tab.id ? 'text-cyan-400' : 'text-zinc-500'}`} />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* User badge */}
          <div className="border-t border-zinc-800 pt-4 mt-6">
            <div className="bg-[#18181b] border border-zinc-800/60 p-3.5 rounded-lg flex flex-col">
              <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Active User Profile</span>
              <span className="text-xs text-white font-medium truncate mt-1" title={email}>{email || "default-user"}</span>
              <button 
                onClick={() => {
                  localStorage.removeItem("recall_user_id");
                  setUserId(null);
                  setIsOnboarding(true);
                }}
                className="text-[9px] text-red-400 hover:text-red-300 font-semibold text-left mt-2 underline"
              >
                Log out / Reset Profile
              </button>
            </div>
          </div>
        </nav>

        {/* Content Pane */}
        <main className="flex-1 overflow-y-auto p-8 bg-[#09090b]">
          
          {/* TAB 1: TIMELINE */}
          {activeTab === "timeline" && (
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    Digital Memory Log
                  </h2>
                  <p className="text-xs text-zinc-400 mt-1">
                    Real-time timeline capturing and parsing user browsing events.
                  </p>
                </div>
              </div>

              {timeline.length === 0 ? (
                <div className="bg-[#18181b] border border-zinc-800 rounded-xl p-12 text-center text-zinc-400">
                  <Clock className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                  <p className="font-medium text-white mb-2">No Memories Captured Yet</p>
                  <p className="text-xs text-zinc-500 max-w-sm mx-auto">
                    Use the **Extension Simulator** tab to navigate pages or run background traffic, and your structured memories will show up here.
                  </p>
                </div>
              ) : (
                <div className="relative border-l border-zinc-800 ml-4 pl-8 space-y-8">
                  {timeline.map((event) => (
                    <div key={event.id} className="relative">
                      {/* Timeline dot */}
                      <span className="absolute -left-[41px] top-1 bg-[#18181b] border border-zinc-700 p-1.5 rounded-full z-10 flex items-center justify-center">
                        {getSourceIcon(event.source_type)}
                      </span>

                      <div className="bg-[#121214] border border-zinc-850 rounded-lg p-5 hover:border-zinc-700 transition-colors">
                        <div className="flex flex-wrap justify-between items-start gap-4 mb-2">
                          <div className="flex-1 min-w-0">
                            <h3 className="font-semibold text-white text-sm truncate flex items-center gap-2">
                              {event.title}
                              <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                                ({event.source_type})
                              </span>
                            </h3>
                            <a 
                              href={event.url} 
                              target="_blank" 
                              rel="noreferrer"
                              className="text-[11px] text-cyan-400 hover:underline flex items-center gap-1 mt-1 truncate"
                            >
                              {event.url}
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>

                          {/* Badge scores */}
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] bg-zinc-800 border border-zinc-700 text-zinc-400 px-2 py-0.5 rounded-md font-medium">
                              Time: {event.duration}s
                            </span>
                            <span className="text-[10px] bg-zinc-800 border border-zinc-700 text-zinc-400 px-2 py-0.5 rounded-md font-medium">
                              Scroll: {event.scroll_depth}%
                            </span>
                            
                            {/* Score badge */}
                            <span className={`text-[10px] px-2.5 py-0.5 rounded-md font-bold ${
                              event.engagement_score >= 0.4 
                                ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' 
                                : 'bg-zinc-800 text-zinc-400'
                            }`}>
                              Score: {event.engagement_score}
                            </span>

                            {/* State indicator */}
                            <span className={`text-[10px] px-2.5 py-0.5 rounded-md font-bold ${
                              event.event_type === "extract"
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                            }`}>
                              {event.event_type === "extract" ? "Extracted" : "Captured"}
                            </span>
                          </div>
                        </div>

                        {/* Content preview */}
                        {event.content_preview ? (
                          <div className="mt-3 bg-[#09090b] border border-zinc-850 p-3 rounded-md text-xs text-zinc-400 leading-relaxed">
                            {event.content_preview}
                          </div>
                        ) : (
                          <div className="mt-3 flex items-center justify-between bg-[#09090b]/50 border border-dashed border-zinc-800 p-3 rounded-md">
                            <span className="text-xs text-zinc-500 italic">
                              Initial metadata captured. Below auto-extraction thresholds.
                            </span>
                            <button
                              onClick={() => handleForceExtract(event.id)}
                              className="text-[10px] font-bold bg-zinc-800 hover:bg-zinc-700 text-white px-2.5 py-1 rounded-md border border-zinc-700"
                            >
                              Force Deep Extract
                            </button>
                          </div>
                        )}

                        <div className="text-[10px] text-zinc-600 mt-2.5 flex items-center justify-between">
                          <span>Logged: {new Date(event.created_at).toLocaleString()}</span>
                          <span className="font-semibold">Event ID: {event.id}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: SESSIONS */}
          {activeTab === "sessions" && (
            <div className="space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    Browsing Sessions
                  </h2>
                  <p className="text-xs text-zinc-400 mt-1">
                    Semantic workflows grouped chronologically.
                  </p>
                </div>
                <button
                  onClick={handleTriggerClustering}
                  className="bg-gradient-to-r from-cyan-400 to-violet-500 text-black font-semibold text-xs px-4 py-2.5 rounded-lg flex items-center gap-2 transition-all active:scale-[0.98]"
                >
                  <Sparkles className="w-4 h-4 text-black" />
                  Run Clustering Agent
                </button>
              </div>

              {sessions.length === 0 ? (
                <div className="bg-[#18181b] border border-zinc-800 rounded-xl p-12 text-center text-zinc-400">
                  <Compass className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                  <p className="font-medium text-white mb-2">No Active Clustered Sessions</p>
                  <p className="text-xs text-zinc-500 max-w-sm mx-auto mb-4">
                    Clustering requires at least 2 browsing events within a 30-minute window. Gather memories, then click "Run Clustering Agent".
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4">
                  {sessions.map((session) => {
                    const isExpanded = expandedSessions[session.id] || false;
                    return (
                      <div key={session.id} className="bg-[#121214] border border-zinc-850 rounded-xl overflow-hidden">
                        <div 
                          onClick={() => setExpandedSessions(prev => ({ ...prev, [session.id]: !isExpanded }))}
                          className="p-5 flex items-start justify-between gap-6 cursor-pointer hover:bg-zinc-900/40 select-none"
                        >
                          <div className="flex-1 space-y-1.5">
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] bg-violet-500/10 text-violet-400 border border-violet-500/20 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                                {session.topic || "Research"}
                              </span>
                              <span className="text-[10px] text-zinc-500 font-semibold">
                                {new Date(session.started_at).toLocaleDateString()}
                              </span>
                            </div>
                            <h3 className="font-bold text-white text-base">
                              {session.title}
                            </h3>
                            <p className="text-xs text-zinc-400 leading-relaxed">
                              {session.summary}
                            </p>
                          </div>

                          <div className="flex items-center gap-3">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteSession(session.id);
                              }}
                              className="text-zinc-500 hover:text-red-400 p-2 rounded-lg hover:bg-zinc-800 transition-colors"
                              title="Delete Session & Memories"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                            {isExpanded ? <ChevronDown className="w-5 h-5 text-zinc-400" /> : <ChevronRight className="w-5 h-5 text-zinc-400" />}
                          </div>
                        </div>

                        {/* Expanded details */}
                        {isExpanded && (
                          <div className="bg-[#0b0b0d] border-t border-zinc-850 p-5 space-y-3">
                            <div className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 mb-2">
                              Linked Browsing Path
                            </div>
                            <div className="space-y-2">
                              {session.memories.map(m => (
                                <div key={m.id} className="flex justify-between items-center p-3 bg-[#121214] border border-zinc-850 rounded-lg text-xs">
                                  <div className="flex items-center gap-3 min-w-0">
                                    {getSourceIcon(m.source_type)}
                                    <span className="font-semibold text-white truncate max-w-md">{m.title}</span>
                                    <span className="text-[9px] text-zinc-500 truncate max-w-xs">({m.url})</span>
                                  </div>
                                  <div className="text-[10px] text-zinc-500">
                                    {new Date(m.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: AGENT CHAT */}
          {activeTab === "chat" && (
            <div className="space-y-6 max-w-4xl">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  Agentic Memory Retrieval
                </h2>
                <p className="text-xs text-zinc-400 mt-1">
                  Query your history using structured multi-agent synthesis.
                </p>
              </div>

              {/* Chat Input */}
              <form onSubmit={handleAgentChat} className="bg-[#121214] border border-zinc-850 p-4 rounded-xl flex gap-3 shadow-lg">
                <input 
                  type="text"
                  required
                  value={queryText}
                  onChange={e => setQueryText(e.target.value)}
                  placeholder="e.g. What did I read about recall metrics?"
                  className="flex-1 bg-[#09090b] border border-zinc-850 focus:border-cyan-400 rounded-lg p-3 outline-none text-sm text-white"
                />
                <button
                  type="submit"
                  disabled={chatLoading}
                  className="bg-cyan-400 hover:bg-cyan-500 text-black font-semibold text-xs px-5 py-3 rounded-lg flex items-center gap-2 active:scale-[0.98] disabled:opacity-50"
                >
                  <Search className="w-4 h-4 text-black" />
                  {chatLoading ? "Querying..." : "Retrieve"}
                </button>
              </form>

              {/* Chat Output Frame */}
              {(chatLoading || queryResponse || agentLogs.length > 0) && (
                <div className="space-y-4">
                  {/* Execution Logs widget */}
                  <div className="bg-[#121214] border border-zinc-850 rounded-xl p-5">
                    <h3 className="text-xs uppercase font-bold tracking-wider text-zinc-500 mb-3 flex items-center gap-2">
                      <Sliders className="w-3.5 h-3.5 text-zinc-500" />
                      Agent Execution Steps
                    </h3>
                    <div className="space-y-2.5">
                      {agentLogs.map((log, index) => (
                        <div key={index} className="flex gap-3 text-xs leading-relaxed">
                          <span className="font-bold text-cyan-400 min-w-[110px]">{log.agent}:</span>
                          <span className="text-zinc-400">{log.action}</span>
                        </div>
                      ))}
                      {chatLoading && agentLogs.length === 0 && (
                        <div className="text-xs text-zinc-500 italic animate-pulse">
                          Planner is decomposing search queries...
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Summary Response Card */}
                  {queryResponse && (
                    <div className="bg-gradient-to-br from-[#121214] to-[#1a1a1f] border border-zinc-800 rounded-xl p-6 shadow-xl relative overflow-hidden">
                      <div className="absolute top-0 right-0 p-3">
                        <Sparkles className="w-5 h-5 text-violet-400/20" />
                      </div>

                      <h3 className="text-xs uppercase font-bold tracking-wider text-cyan-400 mb-3">
                        Synthesized Answer
                      </h3>
                      <p className="text-sm text-zinc-200 leading-relaxed">
                        {queryResponse}
                      </p>

                      {/* Citation block */}
                      {citation && (
                        <div className="mt-5 border-t border-zinc-800/80 pt-4">
                          <div className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 mb-2">
                            Source Citation
                          </div>
                          <div className="bg-[#09090b] border border-zinc-850 p-4 rounded-lg space-y-2">
                            <p className="text-xs italic text-zinc-400 leading-relaxed">
                              "{citation.quote}"
                            </p>
                            <div className="flex justify-between items-center text-[10px] text-zinc-500 pt-2 border-t border-zinc-900">
                              <span className="font-bold text-white">
                                {citation.source} ({citation.location})
                              </span>
                              <a 
                                href={citation.url} 
                                target="_blank" 
                                rel="noreferrer"
                                className="text-cyan-400 hover:underline flex items-center gap-1 font-semibold"
                              >
                                View Source URL
                                <ExternalLink className="w-2.5 h-2.5" />
                              </a>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: EXTENSION SIMULATOR */}
          {activeTab === "simulator" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Simulator Input Controls */}
              <div className="space-y-6">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    Extension Simulation Engine
                  </h2>
                  <p className="text-xs text-zinc-400 mt-1">
                    Simulate how the Chrome Extension communicates tab events and engagement parameters.
                  </p>
                </div>

                <div className="bg-[#121214] border border-zinc-850 rounded-xl p-6 space-y-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                      Simulated Tab URL
                    </label>
                    <input 
                      type="text" 
                      value={simUrl}
                      onChange={e => setSimUrl(e.target.value)}
                      className="w-full bg-[#09090b] border border-zinc-850 focus:border-cyan-400 text-sm p-3 rounded-lg outline-none text-white transition-colors"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                      Simulated Tab Title
                    </label>
                    <input 
                      type="text" 
                      value={simTitle}
                      onChange={e => setSimTitle(e.target.value)}
                      className="w-full bg-[#09090b] border border-zinc-850 focus:border-cyan-400 text-sm p-3 rounded-lg outline-none text-white transition-colors"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                        Simulated Tab ID
                      </label>
                      <input 
                        type="number" 
                        value={simTabId}
                        onChange={e => setSimTabId(parseInt(e.target.value))}
                        className="w-full bg-[#09090b] border border-zinc-850 focus:border-cyan-400 text-sm p-3 rounded-lg outline-none text-white transition-colors"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                        Simulator State
                      </label>
                      <div className="w-full p-3 bg-zinc-900 border border-zinc-800 rounded-lg text-xs font-bold text-center capitalize">
                        {simStatus === "active" && <span className="text-emerald-400">● Active Capture</span>}
                        {simStatus === "idle" && <span className="text-zinc-500">○ Off / Idle</span>}
                        {simStatus === "loading" && <span className="text-amber-400 animate-pulse">● Loading...</span>}
                        {simStatus === "extracted" && <span className="text-cyan-400">✔ Extracted</span>}
                        {simStatus === "rejected" && <span className="text-red-400">✖ Rejected (Blocklist)</span>}
                        {simStatus === "error" && <span className="text-red-400">✖ API Offline</span>}
                      </div>
                    </div>
                  </div>

                  <div className="pt-2">
                    <button
                      onClick={handleSimTabLoad}
                      className="w-full bg-cyan-400 hover:bg-cyan-500 text-black font-semibold text-xs py-3 rounded-lg flex items-center justify-center gap-2 active:scale-[0.98]"
                    >
                      <Play className="w-4 h-4 fill-black" />
                      Simulate Tab Navigation Load
                    </button>
                  </div>
                </div>

                {/* Engagement sliders */}
                {simStatus === "active" && (
                  <div className="bg-[#121214] border border-zinc-850 rounded-xl p-6 space-y-5">
                    <h3 className="text-xs uppercase font-bold tracking-wider text-zinc-400">
                      Simulate Interactive Engagement
                    </h3>

                    {/* Duration Display */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-zinc-400">Time spent active:</span>
                        <span className="text-white">{simDuration} seconds</span>
                      </div>
                      <div className="w-full bg-zinc-900 h-2 rounded-full overflow-hidden">
                        <div 
                          className="bg-cyan-400 h-2 transition-all duration-300"
                          style={{ width: `${Math.min(simDuration / 20 * 100, 100)}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-zinc-500">
                        * Threshold requires minimum **20 seconds**.
                      </p>
                    </div>

                    {/* Scroll Depth Slider */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-zinc-400">Scroll depth:</span>
                        <span className="text-white">{simScroll}%</span>
                      </div>
                      <input 
                        type="range" 
                        min="0" 
                        max="100" 
                        value={simScroll}
                        onChange={e => setSimScroll(parseInt(e.target.value))}
                        className="w-full h-1.5 bg-zinc-900 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                      />
                      <p className="text-[10px] text-zinc-500">
                        * Threshold requires minimum **40% scroll depth**.
                      </p>
                    </div>

                    <button
                      onClick={() => handleSimUpdateEngagement(5, simScroll)}
                      className="w-full bg-zinc-800 hover:bg-zinc-750 text-white font-semibold text-xs py-2.5 rounded-lg border border-zinc-700"
                    >
                      Ping Engagement Signal
                    </button>
                  </div>
                )}
              </div>

              {/* Simulator Execution Output logs */}
              <div className="bg-[#121214] border border-zinc-850 rounded-xl p-6 flex flex-col h-[500px]">
                <h3 className="text-xs uppercase font-bold tracking-wider text-zinc-400 mb-3">
                  Simulator Execution Output Logs
                </h3>
                <div className="flex-1 bg-[#09090b] border border-zinc-850 p-4 rounded-lg font-mono text-[11px] text-zinc-400 space-y-2 overflow-y-auto">
                  {simLogs.map((log, index) => (
                    <div key={index} className="leading-relaxed border-b border-zinc-900/50 pb-1.5 last:border-b-0">
                      {log}
                    </div>
                  ))}
                  {simLogs.length === 0 && (
                    <div className="text-zinc-600 italic">
                      No logs recorded. Select a URL and start simulation above.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: PRIVACY GOVERNANCE */}
          {activeTab === "privacy" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Category Controls & Storage Mode */}
              <div className="space-y-6 lg:col-span-2">
                {/* Allowed Categories toggles */}
                <div className="bg-[#121214] border border-zinc-850 rounded-xl p-6">
                  <h3 className="text-base font-bold text-white mb-2">
                    Allowed Media Categories
                  </h3>
                  <p className="text-xs text-zinc-400 mb-6">
                    Toggle categories to enable or disable automatic memory tracking.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {[
                      { id: "articles", label: "Articles & General Web", icon: Compass },
                      { id: "youtube", label: "YouTube Transcripts", icon: Video },
                      { id: "github", label: "GitHub Code Readmes", icon: GithubIcon },
                      { id: "pdf", label: "Local PDF Documents", icon: FileText }
                    ].map(cat => {
                      const Icon = cat.icon;
                      const isAllowed = categories[cat.id] || false;
                      return (
                        <div 
                          key={cat.id}
                          onClick={() => handleToggleCategory(cat.id)}
                          className={`p-4 rounded-xl border flex items-center justify-between cursor-pointer select-none transition-all ${
                            isAllowed 
                              ? 'bg-violet-950/10 border-violet-500/40 hover:border-violet-500' 
                              : 'bg-zinc-900 border-zinc-850 text-zinc-500 hover:border-zinc-800'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <Icon className={`w-5 h-5 ${isAllowed ? 'text-violet-400' : 'text-zinc-600'}`} />
                            <div>
                              <div className={`text-sm font-bold ${isAllowed ? 'text-white' : 'text-zinc-400'}`}>
                                {cat.label}
                              </div>
                              <div className="text-[10px] text-zinc-500 mt-0.5">
                                {isAllowed ? "Recording Active" : "Blocked/Deny"}
                              </div>
                            </div>
                          </div>
                          <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                            isAllowed ? 'border-violet-400 bg-violet-400/20' : 'border-zinc-700'
                          }`}>
                            {isAllowed && <div className="w-1.5 h-1.5 bg-violet-400 rounded-full" />}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Local Storage details */}
                <div className="bg-[#121214] border border-zinc-850 rounded-xl p-6 space-y-6">
                  <div>
                    <h3 className="text-base font-bold text-white mb-2">
                      Active Privacy Policies
                    </h3>
                    <p className="text-xs text-zinc-400">
                      Define the synchronization rules and storage constraints for your memory platform.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {[
                      { id: "balanced", label: "Balanced Sync", desc: "Dual local/cloud storage vector RAG" },
                      { id: "strict", label: "Strict Mode", desc: "Aggressive keyword filters enabled" },
                      { id: "local", label: "Local Only", desc: "Zero cloud upload, local SQLite/FAISS only" }
                    ].map(mode => (
                      <button
                        key={mode.id}
                        onClick={async () => {
                          try {
                            const res = await fetch(`${BACKEND_URL}/privacy/preferences`, {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({
                                privacy_mode: mode.id,
                                cloud_sync_enabled: mode.id !== "local",
                                user_id: userId
                              })
                            });
                            if (res.ok) {
                              setPrivacyMode(mode.id);
                            }
                          } catch (e) {
                            console.error(e);
                          }
                        }}
                        className={`p-4 rounded-xl border text-left flex flex-col transition-all ${
                          privacyMode === mode.id 
                            ? 'bg-cyan-950/15 border-cyan-400 text-white' 
                            : 'bg-zinc-900 border-zinc-850 text-zinc-400 hover:border-zinc-800'
                        }`}
                      >
                        <span className="text-sm font-bold">{mode.label}</span>
                        <span className="text-[10px] text-zinc-500 font-semibold mt-1.5">{mode.desc}</span>
                      </button>
                    ))}
                  </div>

                  {/* Pause Recording timers */}
                  <div className="border-t border-zinc-850 pt-5">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400 mb-3">
                      Ambient Ingestion Control
                    </h4>
                    <div className="flex flex-wrap gap-4 items-center">
                      <div className="flex bg-zinc-900 border border-zinc-850 p-1.5 rounded-lg">
                        {[10, 60, 180].map(mins => (
                          <button
                            key={mins}
                            onClick={() => setPauseMinutes(mins)}
                            className={`px-3 py-1.5 text-xs rounded-md font-semibold ${
                              pauseMinutes === mins ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'
                            }`}
                          >
                            {mins >= 60 ? `${mins/60}h` : `${mins}m`}
                          </button>
                        ))}
                      </div>

                      <button
                        onClick={handlePauseCapture}
                        className={`text-xs font-bold px-4 py-2.5 rounded-lg border ${
                          isPauseActive 
                            ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' 
                            : 'bg-zinc-800 hover:bg-zinc-700 text-white border-zinc-700'
                        }`}
                      >
                        {isPauseActive ? "Recording Paused" : "Pause Recording"}
                      </button>

                      {isPauseActive && (
                        <button
                          onClick={async () => {
                            try {
                              const res = await fetch(`${BACKEND_URL}/privacy/pause`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({
                                  duration_minutes: 0, // Unpause
                                  user_id: userId
                                })
                              });
                              if (res.ok) {
                                setIsPauseActive(false);
                              }
                            } catch (e) {
                              console.error(e);
                            }
                          }}
                          className="text-xs font-semibold text-cyan-400 hover:underline"
                        >
                          Resume Ingestion
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Permanent purge / Danger zone */}
                <div className="bg-red-950/10 border border-red-900/40 rounded-xl p-6">
                  <h3 className="text-base font-bold text-red-400 mb-2">
                    Danger Zone
                  </h3>
                  <p className="text-xs text-red-300/70 mb-5">
                    Permanently delete history logs, session indices, and vector embeddings.
                  </p>
                  <button
                    onClick={handlePurgeAll}
                    className="bg-red-900/30 hover:bg-red-900/40 text-red-400 border border-red-800/60 font-semibold text-xs px-4 py-2.5 rounded-lg"
                  >
                    Purge All Platform Memories
                  </button>
                </div>
              </div>

              {/* Blocklist Domains Sidebar & Profile Reflection */}
              <div className="space-y-6">
                {/* Blocked Domains manager */}
                <div className="bg-[#121214] border border-zinc-850 rounded-xl p-6">
                  <h3 className="text-base font-bold text-white mb-2">
                    Exclusion Blocklist
                  </h3>
                  <p className="text-xs text-zinc-400 mb-4">
                    Domain wildcards matching exclusion bounds.
                  </p>

                  {/* Add Domain form */}
                  <form 
                    onSubmit={e => {
                      e.preventDefault();
                      const form = e.target as HTMLFormElement;
                      const input = form.elements.namedItem("domainInput") as HTMLInputElement;
                      handleAddBlockedDomain(input.value);
                      form.reset();
                    }}
                    className="flex gap-2 mb-4"
                  >
                    <input 
                      name="domainInput"
                      type="text" 
                      required
                      placeholder="e.g. reddit.com"
                      className="flex-1 bg-[#09090b] border border-zinc-850 focus:border-cyan-400 text-xs p-2.5 rounded-lg outline-none text-white"
                    />
                    <button 
                      type="submit"
                      className="bg-zinc-800 hover:bg-zinc-750 text-white p-2.5 rounded-lg border border-zinc-700"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </form>

                  {/* Blocked domains lists */}
                  <div className="space-y-2 max-h-[180px] overflow-y-auto pr-1">
                    {blockedDomains.map(b => (
                      <div key={b.id} className="flex justify-between items-center p-2.5 bg-[#09090b] border border-zinc-850 rounded-lg text-xs">
                        <span className="font-semibold text-zinc-300 truncate max-w-[150px]" title={b.domain}>
                          {b.domain}
                        </span>
                        <button
                          onClick={() => handleDeleteBlockedDomain(b.id)}
                          className="text-zinc-600 hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                    {blockedDomains.length === 0 && (
                      <div className="text-zinc-600 text-xs italic text-center py-4">
                        No custom domains blocked.
                      </div>
                    )}
                  </div>
                </div>

                {/* Profile Reflection logs */}
                <div className="bg-[#121214] border border-zinc-850 rounded-xl p-6">
                  <h3 className="text-base font-bold text-white mb-2">
                    Memory Profile Reflection
                  </h3>
                  <p className="text-xs text-zinc-400 mb-4">
                    Extracted learning topics by the Reflection Agent.
                  </p>

                  <div className="space-y-3.5">
                    {reflections.map((ref, idx) => (
                      <div key={idx} className="space-y-1.5 p-3 bg-[#09090b] border border-zinc-850 rounded-lg text-xs">
                        <div className="flex justify-between items-center font-bold">
                          <span className="text-white">{ref.topic}</span>
                          <span className="text-cyan-400">Score: {Math.round(ref.weight * 100)}%</span>
                        </div>
                        <p className="text-zinc-500 leading-relaxed">
                          {ref.rationale}
                        </p>
                      </div>
                    ))}
                    {reflections.length === 0 && (
                      <div className="text-zinc-600 text-xs italic text-center py-4">
                        Perform deep text extractions first to allow interest reflections.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  );
}
