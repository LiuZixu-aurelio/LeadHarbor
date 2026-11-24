"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Copy, LoaderCircle, RefreshCw } from "lucide-react";

import { apiGet, statusLabels, type LeadRaw, type Stats } from "@/lib/api";

export default function TasksView({ notify, stats }: { notify: (m: string) => void; stats: Stats }) {
  const [leads, setLeads] = useState<LeadRaw[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const data = await apiGet<LeadRaw[]>("/leads?limit=100");
      setLeads(data);
    } catch {
      notify("加载采集记录失败，请确认后端 API 正在运行");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const counts = useMemo(() => {
    const c = { processed: 0, duplicate: 0, failed: 0 };
    leads.forEach((l) => {
      if (l.status === "processed") c.processed += 1;
      else if (l.status === "duplicate") c.duplicate += 1;
      else if (l.status === "failed") c.failed += 1;
    });
    return c;
  }, [leads]);

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">采集任务</p>
          <h1>采集记录</h1>
          <p className="subtitle">累计 {stats.raw_leads} 条采集记录，展示最近 100 条的处理结果。</p>
        </div>
        <button className="primary-button ghost" onClick={load} disabled={loading}>
          {loading ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />} 刷新
        </button>
      </div>

      <div className="metric-grid metrics-3">
        <TaskMetric icon={<CheckCircle2 />} label="已处理" value={counts.processed} tone="green" />
        <TaskMetric icon={<Copy />} label="重复" value={counts.duplicate} tone="orange" />
        <TaskMetric icon={<AlertTriangle />} label="失败" value={counts.failed} tone="red" />
      </div>

      <div className="panel table-panel">
        <div className="table-scroll">
          <table>
            <thead><tr><th>#</th><th>数据源</th><th>状态</th><th>时间</th><th>备注</th></tr></thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id}>
                  <td className="muted-cell">#{lead.id}</td>
                  <td><span className="source-pill">{lead.source}</span></td>
                  <td><span className={`status status-${lead.status}`}>{statusLabels[lead.status] || lead.status}</span></td>
                  <td className="muted-cell">{formatTime(lead.fetched_at)}</td>
                  <td className="muted-cell">{lead.error || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {leads.length === 0 && <div className="empty-state">{loading ? "加载中…" : "还没有采集记录，去「发现线索」开始采集吧"}</div>}
        </div>
      </div>
    </>
  );
}

function TaskMetric({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: number; tone: string }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-label">{label}</div><div className="metric-value">{value}</div></div>;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
