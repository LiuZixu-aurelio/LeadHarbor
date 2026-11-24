"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bell,
  Check,
  ChevronDown,
  CircleHelp,
  Command,
  Compass,
  Gauge,
  LayoutGrid,
  Search,
  Settings2,
  Sparkles,
  Users,
  X,
} from "lucide-react";

import { apiGet, type CollectConfig, type Stats } from "@/lib/api";
import OverviewView from "@/components/views/overview";
import CustomersView from "@/components/views/customers";
import DiscoverView from "@/components/views/discover";
import TasksView from "@/components/views/tasks";
import SettingsView from "@/components/views/settings";

type NavKey = "概览" | "客户库" | "发现线索" | "采集任务" | "设置";

const NAV: { label: NavKey; icon: typeof LayoutGrid }[] = [
  { label: "概览", icon: LayoutGrid },
  { label: "客户库", icon: Users },
  { label: "发现线索", icon: Compass },
  { label: "采集任务", icon: Gauge },
];

export default function Dashboard() {
  const [activeNav, setActiveNav] = useState<NavKey>("概览");
  const [stats, setStats] = useState<Stats>({ companies: 0, raw_leads: 0 });
  const [config, setConfig] = useState<CollectConfig | null>(null);
  const [notice, setNotice] = useState("");

  const notify = useCallback((message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 4500);
  }, []);

  useEffect(() => {
    Promise.all([apiGet<Stats>("/stats"), apiGet<CollectConfig>("/collect/config")])
      .then(([s, c]) => {
        setStats(s);
        setConfig(c);
      })
      .catch(() => undefined);
  }, []);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><Sparkles size={17} strokeWidth={2.5} /></div><span>LeadHarbor</span></div>
        <div className="workspace-switcher"><span className="workspace-dot" /> <span>我的工作区</span><ChevronDown size={14} /></div>
        <nav className="nav-list" aria-label="主导航">
          {NAV.map(({ label, icon: Icon }) => (
            <button className={`nav-item ${activeNav === label ? "active" : ""}`} key={label} onClick={() => setActiveNav(label)}>
              <Icon size={17} /><span>{label}</span>
              {label === "采集任务" && stats.raw_leads > 0 && <span className="nav-badge">{stats.raw_leads > 99 ? "99+" : stats.raw_leads}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className={`nav-item ${activeNav === "设置" ? "active" : ""}`} onClick={() => setActiveNav("设置")}><Settings2 size={17} /><span>设置</span></button>
          <button className="nav-item"><CircleHelp size={17} /><span>帮助中心</span></button>
          <div className="user-card"><div className="avatar">AU</div><div><strong>Aurelio</strong><span>管理员</span></div><ChevronDown size={14} /></div>
        </div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div className="breadcrumbs"><span>工作区</span><span className="crumb-separator">/</span><strong>{activeNav}</strong></div>
          <div className="top-actions">
            <button className="icon-button" aria-label="搜索"><Search size={18} /></button>
            <button className="icon-button notification" aria-label="通知"><Bell size={18} /><i /></button>
            <div className="command-hint"><Command size={13} /> K</div>
          </div>
        </header>

        <div className="page-wrap">
          {notice && <div className="toast"><Check size={16} /> {notice}<button onClick={() => setNotice("")}><X size={14} /></button></div>}
          {activeNav === "概览" && <OverviewView stats={stats} config={config} onNavigate={(v) => setActiveNav(v)} />}
          {activeNav === "客户库" && <CustomersView notify={notify} stats={stats} />}
          {activeNav === "发现线索" && <DiscoverView config={config} notify={notify} />}
          {activeNav === "采集任务" && <TasksView notify={notify} stats={stats} />}
          {activeNav === "设置" && <SettingsView notify={notify} />}
        </div>
      </section>
    </main>
  );
}
