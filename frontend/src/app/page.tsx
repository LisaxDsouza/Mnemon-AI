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
  status?: string;
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

interface ThreadItem {
  id: string;
  title: string;
  summary: string;
  status: string;
  created_at: string;
  sessions: Array<{
    id: string;
    title: string;
    intent: string;
    summary: string;
    started_at: string;
    ended_at: string;
    memories: Array<{
      id: string;
      title: string;
      url: string;
      created_at: string;
    }>;
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

// --- Control Deck design tokens & small shared primitives ---

const NAV_ITEMS = [
  { id: "timeline", label: "Memory Log", desc: "Everything captured, in order", icon: Activity },
  { id: "threads", label: "Threads", desc: "Related visits grouped by topic", icon: Database },
  { id: "chat", label: "Ask Recall", desc: "Search your history in plain language", icon: MessageSquare },
  { id: "privacy", label: "Privacy", desc: "What's tracked, blocked, or paused", icon: Settings },
];

function relevanceLabel(score: number) {
  if (score >= 0.7) return "High";
  if (score >= 0.4) return "Medium";
  return "Low";
}

function StatusPill({ status }: { status?: string }) {
  if (status === "extracted") {
    return (
      <span className="inline-flex items-center gap-1.5 text-[10.5px] font-semibold px-2.5 py-1 rounded-full text-[#5fe6a0] bg-[#5fe6a0]/10">
        ✓ Processed
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1.5 text-[10.5px] font-semibold px-2.5 py-1 rounded-full text-[#ff6b6b] bg-[#ff6b6b]/10">
        ⚠ Failed
      </span>
    );
  }
  if (status === "ignored") {
    return (
      <span className="inline-flex items-center gap-1.5 text-[10.5px] font-semibold px-2.5 py-1 rounded-full text-[#84a0ad] bg-[#84a0ad]/10">
        Ignored
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-[10.5px] font-semibold px-2.5 py-1 rounded-full text-[#ffb646] bg-[#ffb646]/10">
      ⏳ Waiting
    </span>
  );
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
  const [threads, setThreads] = useState<ThreadItem[]>([]);
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

  // UI Expanded Sessions list
  const [expandedSessions, setExpandedSessions] = useState<Record<string, boolean>>({});

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

      // 2.5 Fetch Threads
      try {
        const threadsRes = await fetch(`${BACKEND_URL}/threads?user_id=${userId}`);
        if (threadsRes.ok) {
          setThreads(await threadsRes.json());
        }
      } catch (err) {
        console.error("Threads fetch failed", err);
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

  // Helper source icons
  const getSourceIcon = (type: string) => {
    switch (type) {
      case "youtube": return <Video className="w-4 h-4 text-[#5fd8e6]" />;
      case "github": return <GithubIcon className="w-4 h-4 text-[#5fd8e6]" />;
      case "pdf": return <FileText className="w-4 h-4 text-[#5fd8e6]" />;
      default: return <Compass className="w-4 h-4 text-[#5fd8e6]" />;
    }
  };

  const sourceLabel = (type: string) => {
    switch (type) {
      case "youtube": return "YouTube";
      case "github": return "GitHub";
      case "pdf": return "PDF";
      case "stackoverflow": return "Stack Overflow";
      default: return "Article";
    }
  };

  const processedCount = timeline.filter(e => e.status === "extracted").length;
  const waitingCount = timeline.length - processedCount;

  // --- RENDER ONBOARDING VIEW ---
  if (isOnboarding) {
    return (
      <div className="min-h-screen bg-[#0b1016] text-[#e3edf1] flex items-center justify-center p-6 relative overflow-hidden font-sans">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "linear-gradient(rgba(103,214,229,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(103,214,229,0.05) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        />

        <div className="w-full max-w-lg bg-[#111820] border border-[#20303c] rounded-xl p-8 shadow-2xl relative z-10">
          <div className="flex justify-center mb-6">
            <div className="relative w-11 h-11 rounded-full border-2 border-[#5fd8e6] flex items-center justify-center">
              <div className="w-4 h-4 rounded-full bg-[#5fd8e6]" />
            </div>
          </div>

          <h2 className="text-2xl font-bold text-center text-[#e3edf1] mb-2">
            Welcome to Recall AI
          </h2>
          <p className="text-[#84a0ad] text-sm text-center mb-8">
            Let's set up your local memory layer and default privacy exclusions.
          </p>

          <form onSubmit={handleSignup} className="space-y-6">
            {/* Email Address */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#84a0ad] mb-2">
                Identity / Email Address
              </label>
              <input
                type="email"
                required
                placeholder="developer@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full bg-[#0e141b] border border-[#20303c] focus:border-[#5fd8e6] text-sm p-3 rounded-lg outline-none transition-colors"
              />
            </div>

            {/* Allowed Categories */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#84a0ad] mb-2">
                What should Recall save?
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
                        ? 'bg-[#5fd8e6]/10 border-[#5fd8e6]/60 text-white'
                        : 'bg-[#0e141b] border-[#20303c] text-[#84a0ad] hover:border-[#2f4451]'
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
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#84a0ad] mb-2">
                Sites to never track (comma-separated)
              </label>
              <textarea
                rows={2}
                value={signupBlocks}
                onChange={e => setSignupBlocks(e.target.value)}
                placeholder="domain.com, bank.com, auth.net"
                className="w-full bg-[#0e141b] border border-[#20303c] focus:border-[#5fd8e6] text-sm p-3 rounded-lg outline-none transition-colors resize-none"
              />
              <p className="text-[10px] text-[#516b78] mt-1">
                * Banking, identity, and checkout pages are blocked by default.
              </p>
            </div>

            {/* Privacy Mode */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#84a0ad] mb-2">
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
                        ? 'bg-[#ffb646]/10 border-[#ffb646] text-white'
                        : 'bg-[#0e141b] border-[#20303c] text-[#84a0ad] hover:border-[#2f4451]'
                    }`}
                  >
                    <span className="text-sm font-bold">{mode.label}</span>
                    <span className="text-[9px] text-[#516b78] font-medium">{mode.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            <button
              type="submit"
              className="w-full bg-[#5fd8e6] hover:bg-[#4bc6d4] text-[#0b1016] font-semibold py-3.5 rounded-lg shadow-lg active:scale-[0.99] transition-all text-sm flex items-center justify-center gap-2"
            >
              Initialize Memory Platform
              <ChevronRight className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    );
  }

  // --- MAIN DASHBOARD VIEW (Control Deck) ---
  return (
    <div
      className="min-h-screen bg-[#0b1016] text-[#e3edf1] flex flex-col font-sans"
      style={{
        backgroundImage:
          "linear-gradient(rgba(103,214,229,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(103,214,229,0.045) 1px, transparent 1px)",
        backgroundSize: "32px 32px",
      }}
    >
      {/* Top Banner (API Status check) */}
      {!apiOnline && (
        <div className="bg-[#ff6b6b]/10 border-b border-[#ff6b6b]/30 text-[#ff6b6b] p-2.5 text-xs text-center font-medium flex items-center justify-center gap-2">
          <Info className="w-4 h-4" />
          Backend connection error. Make sure Python FastAPI is running at http://localhost:8000
        </div>
      )}

      {/* Main Header */}
      <header className="border-b border-[#20303c] bg-[#151f29] py-3.5 px-6 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="relative w-8 h-8 rounded-full border-2 border-[#5fd8e6] flex items-center justify-center flex-shrink-0">
            <div className="w-3 h-3 rounded-full bg-[#5fd8e6]" />
          </div>
          <div>
            <h1 className="text-[14.5px] font-bold tracking-tight text-white">
              Recall
            </h1>
            <p className="text-[10px] text-[#516b78] -mt-0.5">
              Semantic memory for your browsing
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full font-mono text-[10.5px] tracking-wide ${
            isPauseActive ? "text-[#ffb646] bg-[#ffb646]/10" : "text-[#5fe6a0] bg-[#5fe6a0]/10"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isPauseActive ? "bg-[#ffb646]" : "bg-[#5fe6a0]"}`} />
            {isPauseActive ? "Paused" : "Capturing"}
          </div>

          <button
            onClick={fetchDashboardData}
            className="bg-[#111820] hover:bg-[#182430] border border-[#20303c] p-2 rounded-lg transition-colors"
            title="Refresh Data"
          >
            <RefreshCw className="w-3.5 h-3.5 text-[#84a0ad]" />
          </button>
        </div>
      </header>

      {/* Workspace Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Rail Nav — icon + label + one-line description of what each tab does */}
        <nav className="w-[220px] border-r border-[#20303c] bg-[#0e141b] p-3 flex flex-col justify-between flex-shrink-0">
          <div className="space-y-1">
            {NAV_ITEMS.map(tab => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-start gap-3 px-2.5 py-2.5 rounded-lg text-left transition-all ${
                    active ? "bg-[#5fd8e6]/10" : "hover:bg-[#111820]"
                  }`}
                >
                  <span className={`w-7 h-7 rounded-md border flex items-center justify-center flex-shrink-0 ${
                    active ? "border-[#5fd8e6] text-[#5fd8e6]" : "border-[#20303c] text-[#84a0ad] bg-[#111820]"
                  }`}>
                    <Icon className="w-3.5 h-3.5" />
                  </span>
                  <span>
                    <div className={`text-[12.5px] font-semibold leading-tight ${active ? "text-[#5fd8e6]" : "text-[#e3edf1]"}`}>
                      {tab.label}
                    </div>
                    <div className="text-[10px] text-[#516b78] leading-tight mt-0.5">
                      {tab.desc}
                    </div>
                  </span>
                </button>
              );
            })}
          </div>

          {/* User badge */}
          <div className="border-t border-[#20303c] pt-3 mt-4">
            <div className="bg-[#111820] border border-[#20303c] p-3 rounded-lg flex flex-col">
              <span className="text-[9.5px] text-[#516b78] font-bold uppercase tracking-wider">Signed in as</span>
              <span className="text-xs text-white font-medium truncate mt-1" title={email}>{email || "default-user"}</span>
              <button
                onClick={() => {
                  localStorage.removeItem("recall_user_id");
                  setUserId(null);
                  setIsOnboarding(true);
                }}
                className="text-[9px] text-[#ff6b6b] hover:text-[#ff8b8b] font-semibold text-left mt-2 underline"
              >
                Log out / Reset Profile
              </button>
            </div>
          </div>
        </nav>

        {/* Content Pane */}
        <main
          className="flex-1 overflow-y-auto p-7 md:p-10"
          style={{
            backgroundColor: "#0b1016",
            backgroundImage:
              "linear-gradient(rgba(103,214,229,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(103,214,229,0.045) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        >
        <div className="max-w-6xl mx-auto">

          {/* TAB 1: TIMELINE / MEMORY LOG */}
          {activeTab === "timeline" && (
            <div className="space-y-5">
              <div>
                <h2 className="text-[19px] font-bold text-white">Memory Log</h2>
                <p className="text-[12.5px] text-[#84a0ad] mt-1 max-w-[52ch] leading-relaxed">
                  Every page Recall captured, parsed, and made searchable — most recent first.
                </p>
              </div>

              {/* Stat row: surfaces status before the detail */}
              <div className="flex gap-2.5">
                <div className="flex-1 border border-[#20303c] bg-[#151f29] rounded-lg px-3.5 py-3">
                  <div className="font-mono text-[19px] font-bold tabular-nums">{timeline.length}</div>
                  <div className="text-[10.5px] text-[#84a0ad] mt-0.5">pages captured</div>
                </div>
                <div className="flex-1 border border-[#20303c] bg-[#151f29] rounded-lg px-3.5 py-3">
                  <div className="font-mono text-[19px] font-bold tabular-nums text-[#5fe6a0]">{processedCount}</div>
                  <div className="text-[10.5px] text-[#84a0ad] mt-0.5">fully processed</div>
                </div>
                <div className="flex-1 border border-[#20303c] bg-[#151f29] rounded-lg px-3.5 py-3">
                  <div className="font-mono text-[19px] font-bold tabular-nums text-[#ffb646]">{waitingCount}</div>
                  <div className="text-[10.5px] text-[#84a0ad] mt-0.5">waiting to process</div>
                </div>
              </div>

              {timeline.length === 0 ? (
                <div className="bg-[#151f29] border border-[#20303c] rounded-xl p-12 text-center text-[#84a0ad]">
                  <Clock className="w-12 h-12 text-[#2f4451] mx-auto mb-4" />
                  <p className="font-medium text-white mb-2">No Memories Captured Yet</p>
                  <p className="text-xs text-[#516b78] max-w-sm mx-auto">
                    Browse normally with the extension installed — captured pages will show up here automatically.
                  </p>
                </div>
              ) : (
                <>
                  {/* Legend explains what the status colors mean, up front */}
                  <div className="flex gap-5 flex-wrap items-center px-3.5 py-2.5 border border-[#1a2530] bg-[#0e141b] rounded-lg text-[11px] text-[#84a0ad]">
                    <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-[#5fe6a0]" /><b className="text-[#e3edf1]">Processed</b> — read and searchable in Ask Recall</span>
                    <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-[#ffb646]" /><b className="text-[#e3edf1]">Waiting</b> — captured, not yet parsed</span>
                  </div>

                  <div className="space-y-3">
                    {timeline.map((event) => {
                      const isDone = event.status === "extracted";
                      const score = event.engagement_score || 0;
                      return (
                        <div key={event.id} className="border border-[#20303c] bg-[#151f29] rounded-xl p-4 grid grid-cols-[auto_1fr_auto] gap-4 items-start hover:border-[#2f4451] transition-colors">
                          <div className="w-9 h-9 rounded-lg border border-[#20303c] bg-[#0e141b] flex items-center justify-center flex-shrink-0">
                            {getSourceIcon(event.source_type)}
                          </div>

                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-semibold text-white text-[13.5px] truncate">{event.title}</span>
                              <span className="font-mono text-[9.5px] uppercase tracking-wide text-[#84a0ad] border border-[#20303c] rounded px-1.5 py-0.5">
                                {sourceLabel(event.source_type)}
                              </span>
                            </div>
                            <a
                              href={event.url}
                              target="_blank"
                              rel="noreferrer"
                              className="font-mono text-[10.5px] text-[#4a99a4] hover:text-[#5fd8e6] flex items-center gap-1 mt-1 truncate"
                            >
                              {event.url}
                              <ExternalLink className="w-2.5 h-2.5 flex-shrink-0" />
                            </a>

                            {isDone && event.content_preview ? (
                              <div className="mt-2.5 pl-2.5 border-l-2 border-[#1a2530] text-[11.5px] text-[#84a0ad] leading-relaxed">
                                {event.content_preview}
                              </div>
                            ) : event.status === "failed" ? (
                              <div className="mt-2.5 flex items-center justify-between bg-[#ff6b6b]/5 border border-dashed border-[#ff6b6b]/30 p-2.5 rounded-md">
                                <span className="text-[11px] text-[#ff8b8b]/90 italic">Couldn't parse this page's content.</span>
                                <button
                                  onClick={() => handleForceExtract(event.id)}
                                  className="text-[10px] font-bold bg-[#0e141b] hover:bg-[#182430] text-white px-2.5 py-1 rounded-md border border-[#20303c]"
                                >
                                  Retry
                                </button>
                              </div>
                            ) : event.status !== "ignored" ? (
                              <div className="mt-2.5 flex items-center justify-between bg-[#0e141b] border border-dashed border-[#20303c] p-2.5 rounded-md">
                                <span className="text-[11px] text-[#516b78] italic">Captured, not processed yet.</span>
                                <button
                                  onClick={() => handleForceExtract(event.id)}
                                  className="text-[10px] font-bold bg-[#0e141b] hover:bg-[#182430] text-white px-2.5 py-1 rounded-md border border-[#20303c]"
                                >
                                  Process now
                                </button>
                              </div>
                            ) : null}

                            <div className="flex gap-4 mt-2.5 text-[11px] text-[#84a0ad]">
                              <span>Time on page <b className="text-[#e3edf1] tabular-nums">{event.duration}s</b></span>
                              <span>Scrolled <b className="text-[#e3edf1] tabular-nums">{event.scroll_depth}%</b></span>
                            </div>
                          </div>

                          <div className="text-right min-w-[110px]">
                            <StatusPill status={event.status} />
                            <div className="text-[9.5px] text-[#516b78] uppercase tracking-wide mt-2 mb-1">Relevance</div>
                            <div className="w-full h-[5px] rounded-full bg-[#1a2530] overflow-hidden">
                              <div
                                className={`h-full rounded-full ${isDone ? "bg-[#5fd8e6]" : "bg-[#ffb646]"}`}
                                style={{ width: `${Math.min(100, Math.round(score * 100))}%` }}
                              />
                            </div>
                            <div className="font-mono text-[10.5px] text-[#84a0ad] mt-1 tabular-nums">
                              {relevanceLabel(score)} · {score.toFixed(2)}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="flex justify-between text-[11px] text-[#516b78] pt-3 border-t border-[#20303c]">
                    <span>Showing {timeline.length} of {timeline.length}</span>
                    <span>New pages appear here automatically</span>
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB 2: THREADS */}
          {activeTab === "threads" && (
            <div className="space-y-5">
              <div>
                <h2 className="text-[19px] font-bold text-white">Threads</h2>
                <p className="text-[12.5px] text-[#84a0ad] mt-1 max-w-[52ch] leading-relaxed">
                  Long-running research and learning threads, automatically grouped from related visits across days.
                </p>
              </div>

              {threads.length === 0 ? (
                <div className="bg-[#151f29] border border-[#20303c] rounded-xl p-12 text-center text-[#84a0ad]">
                  <Database className="w-12 h-12 text-[#2f4451] mx-auto mb-4" />
                  <p className="font-medium text-white mb-2">No Threads Yet</p>
                  <p className="text-xs text-[#516b78] max-w-sm mx-auto">
                    Keep browsing — Recall clusters related sessions into threads once there's enough signal.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {threads.map((thread) => (
                    <div key={thread.id} className="bg-[#151f29] border border-[#20303c] rounded-xl p-5 space-y-4">
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2">
                          <span className="text-[9.5px] bg-[#5fd8e6]/10 text-[#5fd8e6] px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                            Thread
                          </span>
                          <span className="text-[10px] text-[#516b78] font-semibold">
                            Started {new Date(thread.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <h3 className="font-bold text-white text-[15px]">{thread.title}</h3>
                        <p className="text-[12px] text-[#84a0ad] leading-relaxed">{thread.summary}</p>
                      </div>

                      <div className="border-t border-[#1a2530] pt-4 space-y-3">
                        <div className="text-[10px] uppercase font-bold tracking-wider text-[#516b78] mb-1">
                          {thread.sessions?.length || 0} browsing sessions in this thread
                        </div>
                        <div className="space-y-2.5">
                          {thread.sessions?.map(sess => (
                            <div key={sess.id} className="bg-[#0e141b] border border-[#1a2530] p-3.5 rounded-lg space-y-2">
                              <div className="flex justify-between items-start">
                                <div>
                                  <h4 className="text-xs font-bold text-white">{sess.title}</h4>
                                  <p className="text-[11px] text-[#84a0ad] mt-1">{sess.summary}</p>
                                </div>
                                <span className="text-[9px] text-[#516b78] flex-shrink-0 ml-3">
                                  {new Date(sess.started_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                </span>
                              </div>

                              <div className="flex flex-wrap gap-1.5 pt-1">
                                {sess.memories?.slice(0, 4).map(m => (
                                  <a
                                    key={m.id}
                                    href={m.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-[9px] bg-[#111820] border border-[#20303c] hover:border-[#2f4451] text-[#c5d6dc] px-2 py-1 rounded truncate max-w-[160px]"
                                    title={m.title}
                                  >
                                    {m.title}
                                  </a>
                                ))}
                                {(sess.memories?.length || 0) > 4 && (
                                  <span className="text-[9px] text-[#516b78] py-1 px-1">
                                    +{sess.memories.length - 4} more
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: ASK RECALL / AGENT CHAT */}
          {activeTab === "chat" && (
            <div className="space-y-5 max-w-3xl mx-auto">
              <div>
                <h2 className="text-[19px] font-bold text-white">Ask Recall</h2>
                <p className="text-[12.5px] text-[#84a0ad] mt-1 max-w-[52ch] leading-relaxed">
                  Ask a question in plain language. Recall's agents search, rank, and cite your own browsing history to answer.
                </p>
              </div>

              <form onSubmit={handleAgentChat} className="bg-[#151f29] border border-[#20303c] p-3.5 rounded-xl flex gap-3 shadow-lg">
                <input
                  type="text"
                  required
                  value={queryText}
                  onChange={e => setQueryText(e.target.value)}
                  placeholder="e.g. What did I read about recall metrics?"
                  className="flex-1 bg-[#0e141b] border border-[#20303c] focus:border-[#5fd8e6] rounded-lg p-3 outline-none text-sm text-white"
                />
                <button
                  type="submit"
                  disabled={chatLoading}
                  className="bg-[#5fd8e6] hover:bg-[#4bc6d4] text-[#0b1016] font-semibold text-xs px-5 py-3 rounded-lg flex items-center gap-2 active:scale-[0.98] disabled:opacity-50"
                >
                  <Search className="w-4 h-4" />
                  {chatLoading ? "Searching..." : "Ask"}
                </button>
              </form>

              {(chatLoading || queryResponse || agentLogs.length > 0) && (
                <div className="space-y-4">
                  <div className="bg-[#151f29] border border-[#20303c] rounded-xl p-5">
                    <h3 className="text-[10.5px] uppercase font-bold tracking-wider text-[#516b78] mb-1 flex items-center gap-2">
                      <Sliders className="w-3.5 h-3.5" />
                      How Recall found this answer
                    </h3>
                    <p className="text-[10.5px] text-[#516b78] mb-3">Each agent hands off to the next — planning the search, retrieving matches, then ranking and summarizing them.</p>
                    <div className="space-y-2.5">
                      {agentLogs.map((log, index) => (
                        <div key={index} className="flex gap-3 text-xs leading-relaxed">
                          <span className="font-bold text-[#5fd8e6] min-w-[110px] font-mono text-[10.5px]">{log.agent}</span>
                          <span className="text-[#84a0ad]">{log.action}</span>
                        </div>
                      ))}
                      {chatLoading && agentLogs.length === 0 && (
                        <div className="text-xs text-[#516b78] italic animate-pulse">
                          Planner is decomposing your question...
                        </div>
                      )}
                    </div>
                  </div>

                  {queryResponse && (
                    <div className="bg-[#151f29] border border-[#20303c] rounded-xl p-6 shadow-xl relative">
                      <h3 className="text-[10.5px] uppercase font-bold tracking-wider text-[#5fd8e6] mb-3">
                        Answer
                      </h3>
                      <p className="text-sm text-[#e3edf1] leading-relaxed">{queryResponse}</p>

                      {citation && (
                        <div className="mt-5 border-t border-[#1a2530] pt-4">
                          <div className="text-[10px] uppercase font-bold tracking-wider text-[#516b78] mb-2">
                            Where this came from
                          </div>
                          <div className="bg-[#0e141b] border border-[#1a2530] p-4 rounded-lg space-y-2">
                            <p className="text-xs italic text-[#84a0ad] leading-relaxed">"{citation.quote}"</p>
                            <div className="flex justify-between items-center text-[10px] text-[#516b78] pt-2 border-t border-[#1a2530]">
                              <span className="font-bold text-white">{citation.source} ({citation.location})</span>
                              <a
                                href={citation.url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-[#5fd8e6] hover:underline flex items-center gap-1 font-semibold"
                              >
                                View source <ExternalLink className="w-2.5 h-2.5" />
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

          {/* TAB 4: PRIVACY */}
          {activeTab === "privacy" && (
            <div className="space-y-5">
              <div>
                <h2 className="text-[19px] font-bold text-white">Privacy</h2>
                <p className="text-[12.5px] text-[#84a0ad] mt-1 max-w-[56ch] leading-relaxed">
                  Control exactly what Recall is allowed to see, pause capture any time, or erase everything it has stored.
                </p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="space-y-5 lg:col-span-2">
                  {/* Categories */}
                  <div className="bg-[#151f29] border border-[#20303c] rounded-xl p-6">
                    <h3 className="text-[14px] font-bold text-white mb-1">What gets saved</h3>
                    <p className="text-[11.5px] text-[#84a0ad] mb-5">Recall only remembers pages in categories you turn on here.</p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {[
                        { id: "articles", label: "Articles & Web", icon: Compass },
                        { id: "youtube", label: "YouTube Videos", icon: Video },
                        { id: "github", label: "GitHub Code", icon: GithubIcon },
                        { id: "pdf", label: "PDF Documents", icon: FileText }
                      ].map(cat => {
                        const Icon = cat.icon;
                        const isAllowed = categories[cat.id] || false;
                        return (
                          <div
                            key={cat.id}
                            onClick={() => handleToggleCategory(cat.id)}
                            className={`p-3.5 rounded-lg border flex items-center justify-between cursor-pointer select-none transition-all ${
                              isAllowed
                                ? 'bg-[#5fd8e6]/10 border-[#4a99a4] hover:border-[#5fd8e6]'
                                : 'bg-[#0e141b] border-[#20303c] text-[#516b78] hover:border-[#2f4451]'
                            }`}
                          >
                            <div className="flex items-center gap-3">
                              <Icon className={`w-[18px] h-[18px] ${isAllowed ? 'text-[#5fd8e6]' : 'text-[#516b78]'}`} />
                              <div>
                                <div className={`text-[12.5px] font-bold ${isAllowed ? 'text-white' : 'text-[#84a0ad]'}`}>{cat.label}</div>
                                <div className="text-[10px] text-[#516b78] mt-0.5">{isAllowed ? "Being saved" : "Not saved"}</div>
                              </div>
                            </div>
                            <div className={`w-7 h-4 rounded-full border relative flex-shrink-0 ${isAllowed ? "border-[#5fd8e6] bg-[#5fd8e6]/20" : "border-[#20303c]"}`}>
                              <div className={`absolute top-[1px] w-3 h-3 rounded-full transition-all ${isAllowed ? "left-[13px] bg-[#5fd8e6]" : "left-[1px] bg-[#516b78]"}`} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Storage mode + pause */}
                  <div className="bg-[#151f29] border border-[#20303c] rounded-xl p-6 space-y-6">
                    <div>
                      <h3 className="text-[14px] font-bold text-white mb-1">Storage mode</h3>
                      <p className="text-[11.5px] text-[#84a0ad]">Decide where your memory data lives and how it syncs.</p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      {[
                        { id: "balanced", label: "Balanced", desc: "Local + cloud, best search quality" },
                        { id: "strict", label: "Strict", desc: "Aggressive filtering before anything is saved" },
                        { id: "local", label: "Local Only", desc: "Nothing ever leaves this device" }
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
                              if (res.ok) setPrivacyMode(mode.id);
                            } catch (e) { console.error(e); }
                          }}
                          className={`p-3.5 rounded-lg border text-left flex flex-col transition-all ${
                            privacyMode === mode.id
                              ? 'bg-[#ffb646]/10 border-[#ffb646] text-white'
                              : 'bg-[#0e141b] border-[#20303c] text-[#84a0ad] hover:border-[#2f4451]'
                          }`}
                        >
                          <span className="text-[12.5px] font-bold">{mode.label}</span>
                          <span className="text-[10px] text-[#516b78] font-medium mt-1 leading-snug">{mode.desc}</span>
                        </button>
                      ))}
                    </div>

                    <div className="border-t border-[#1a2530] pt-5">
                      <h4 className="text-[12.5px] font-bold text-white mb-1">Pause capture</h4>
                      <p className="text-[11px] text-[#516b78] mb-3">Stop Recall from saving anything for a set time — useful for private browsing.</p>
                      <div className="flex flex-wrap gap-4 items-center">
                        <div className="flex bg-[#0e141b] border border-[#20303c] p-1 rounded-lg">
                          {[10, 60, 180].map(mins => (
                            <button
                              key={mins}
                              onClick={() => setPauseMinutes(mins)}
                              className={`px-3 py-1.5 text-xs rounded-md font-semibold ${
                                pauseMinutes === mins ? 'bg-[#ffb646]/15 text-[#ffb646]' : 'text-[#516b78] hover:text-[#84a0ad]'
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
                              ? 'bg-[#ffb646]/10 border-[#ffb646]/40 text-[#ffb646]'
                              : 'bg-[#0e141b] hover:bg-[#182430] text-white border-[#20303c]'
                          }`}
                        >
                          {isPauseActive ? "Capture Paused" : "Pause Capture"}
                        </button>

                        {isPauseActive && (
                          <button
                            onClick={async () => {
                              try {
                                const res = await fetch(`${BACKEND_URL}/privacy/pause`, {
                                  method: "POST",
                                  headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({ duration_minutes: 0, user_id: userId })
                                });
                                if (res.ok) setIsPauseActive(false);
                              } catch (e) { console.error(e); }
                            }}
                            className="text-xs font-semibold text-[#5fd8e6] hover:underline"
                          >
                            Resume now
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Danger zone */}
                  <div className="bg-[#ff6b6b]/5 border border-[#ff6b6b]/30 rounded-xl p-6">
                    <h3 className="text-[14px] font-bold text-[#ff6b6b] mb-1">Erase everything</h3>
                    <p className="text-[11.5px] text-[#ff8b8b]/70 mb-4">Permanently deletes every captured page, session, thread, and vector embedding. This cannot be undone.</p>
                    <button
                      onClick={handlePurgeAll}
                      className="bg-[#ff6b6b]/10 hover:bg-[#ff6b6b]/20 text-[#ff6b6b] border border-[#ff6b6b]/40 font-semibold text-xs px-4 py-2.5 rounded-lg"
                    >
                      Purge all memory
                    </button>
                  </div>
                </div>

                {/* Sidebar: blocklist + reflections */}
                <div className="space-y-5">
                  <div className="bg-[#151f29] border border-[#20303c] rounded-xl p-5">
                    <h3 className="text-[13px] font-bold text-white mb-1">Sites never tracked</h3>
                    <p className="text-[11px] text-[#84a0ad] mb-4">Recall skips any domain on this list, no matter what.</p>

                    <form
                      onSubmit={e => {
                        e.preventDefault();
                        const form = e.target as HTMLFormElement;
                        const input = form.elements.namedItem("domainInput") as HTMLInputElement;
                        handleAddBlockedDomain(input.value);
                        form.reset();
                      }}
                      className="flex gap-2 mb-3"
                    >
                      <input
                        name="domainInput"
                        type="text"
                        required
                        placeholder="e.g. reddit.com"
                        className="flex-1 bg-[#0e141b] border border-[#20303c] focus:border-[#5fd8e6] text-xs p-2.5 rounded-lg outline-none text-white"
                      />
                      <button type="submit" className="bg-[#0e141b] hover:bg-[#182430] text-white p-2.5 rounded-lg border border-[#20303c]">
                        <Plus className="w-4 h-4" />
                      </button>
                    </form>

                    <div className="space-y-2 max-h-[180px] overflow-y-auto pr-1">
                      {blockedDomains.map(b => (
                        <div key={b.id} className="flex justify-between items-center p-2.5 bg-[#0e141b] border border-[#1a2530] rounded-lg text-xs">
                          <span className="font-semibold text-[#c5d6dc] truncate max-w-[150px]" title={b.domain}>{b.domain}</span>
                          <button onClick={() => handleDeleteBlockedDomain(b.id)} className="text-[#516b78] hover:text-[#ff6b6b] transition-colors">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                      {blockedDomains.length === 0 && (
                        <div className="text-[#516b78] text-xs italic text-center py-4">No custom domains blocked.</div>
                      )}
                    </div>
                  </div>

                  <div className="bg-[#151f29] border border-[#20303c] rounded-xl p-5">
                    <h3 className="text-[13px] font-bold text-white mb-1">What Recall thinks you're learning</h3>
                    <p className="text-[11px] text-[#84a0ad] mb-4">Topics extracted from your processed pages, with how confident Recall is.</p>

                    <div className="space-y-3">
                      {reflections.map((ref, idx) => (
                        <div key={idx} className="p-3 bg-[#0e141b] border border-[#1a2530] rounded-lg">
                          <div className="flex justify-between items-center text-xs font-bold mb-1.5">
                            <span className="text-white">{ref.topic}</span>
                            <span className="text-[#5fd8e6] font-mono tabular-nums">{Math.round(ref.weight * 100)}%</span>
                          </div>
                          <div className="w-full h-[4px] rounded-full bg-[#1a2530] overflow-hidden mb-2">
                            <div className="h-full rounded-full bg-[#5fd8e6]" style={{ width: `${Math.round(ref.weight * 100)}%` }} />
                          </div>
                          <p className="text-[10.5px] text-[#84a0ad] leading-relaxed">{ref.rationale}</p>
                        </div>
                      ))}
                      {reflections.length === 0 && (
                        <div className="text-[#516b78] text-xs italic text-center py-4">
                          Process some pages first to see interest reflections here.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
        </main>
      </div>
    </div>
  );
}
