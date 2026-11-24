"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, Globe2, MapPin, Plus, Sparkles, Target, Users } from "lucide-react";

import {
  apiGet,
  countryFlags,
  countryLabel,
  statusLabels,
  type CollectConfig,
  type Company,
  type Stats,
} from "@/lib/api";

type NavTarget = "客户库" | "发现线索" | "采集任务";

export default function OverviewView({
  stats,
  config,
  onNavigate,
}: {
  stats: Stats;
  config: CollectConfig | null;
  onNavigate: (v: NavTarget) => void;
}) {
  const [companies, setCompanies] = useState<Company[]>([]);

  useEffect(() => {
    apiGet<Company[]>("/companies?limit=6")
      .then(setCompanies)
      .catch(() => undefined);
  }, []);

  const highIntent = useMemo(
    () => companies.filter((c) => (c.ai_score ?? 0) >= 80).length,
    [companies],
  );
  const targetCount = config?.target_countries?.length ?? 5;

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">中亚市场 · {new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric" })}</p>
          <h1>早上好，Aurelio。</h1>
          <p className="subtitle">这里是你的获客概览 · 2GIS + Google 双数据源。</p>
        </div>
        <button className="primary-button" onClick={() => onNavigate("发现线索")}><Plus size={17} /> 新建采集</button>
      </div>

      <div className="metric-grid">
        <MetricCard icon={<Users />} label="客户总数" value={stats.companies.toLocaleString()} change="实时" detail="来自数据库" tone="blue" />
        <MetricCard icon={<Target />} label="高意向客户" value={String(highIntent)} change="AI" detail="评分 ≥ 80" tone="purple" />
        <MetricCard icon={<MapPin />} label="重点市场" value={String(targetCount)} change="中亚" detail="区域全覆盖" tone="orange" />
        <MetricCard icon={<Globe2 />} label="原始线索" value={stats.raw_leads.toLocaleString()} change="累计" detail="采集记录" tone="green" />
      </div>

      <div className="section-header">
        <div><h2>高潜客户</h2><p>根据 AI 匹配度，为你优先展示值得跟进的客户。</p></div>
        <button className="text-button" onClick={() => onNavigate("客户库")}>查看全部 <ArrowUpRight size={15} /></button>
      </div>

      <div className="panel table-panel">
        <div className="table-scroll">
          <table>
            <thead><tr><th>公司</th><th>国家 / 地区</th><th>行业</th><th>来源</th><th>AI 匹配度</th><th>状态</th></tr></thead>
            <tbody>
              {companies.map((company) => (
                <tr key={company.id}>
                  <td><div className="company-cell"><div className="company-logo">{company.name.slice(0, 1)}</div><div><strong>{company.name}</strong><span>{company.domain || "暂无域名"}</span></div></div></td>
                  <td><span className="country"><span className="flag">{countryFlags[company.country || ""] || "🌐"}</span>{countryLabel(company.country)}</span></td>
                  <td>{company.industry || "未分类"}</td>
                  <td><span className="source-pill">{company.source || "LeadHarbor"}</span></td>
                  <td><div className="score-cell"><div className="score-bar"><i style={{ width: `${company.ai_score ?? 0}%` }} /></div><strong>{company.ai_score ?? "—"}</strong></div></td>
                  <td><span className={`status status-${company.status}`}>{statusLabels[company.status] || company.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {companies.length === 0 && <div className="empty-state">还没有客户，去「发现线索」采集第一批吧</div>}
        </div>
      </div>

      <div className="bottom-grid">
        <div className="panel activity-panel">
          <div className="panel-heading"><div><h2>采集动态</h2><p>实时了解你的线索流入。</p></div></div>
          <div className="activity-chart">
            <div className="chart-labels"><span>1,200</span><span>800</span><span>400</span><span>0</span></div>
            <div className="chart-area">
              <div className="grid-line line-1" /><div className="grid-line line-2" /><div className="grid-line line-3" />
              <div className="chart-fill" /><div className="chart-line" />
              <div className="chart-point point-1" /><div className="chart-point point-2" /><div className="chart-point point-3" /><div className="chart-point point-4" /><div className="chart-point point-5" />
            </div>
            <div className="chart-dates"><span>—</span><span>—</span><span>—</span><span>—</span><span>—</span><span>—</span><span>今天</span></div>
          </div>
          <div className="chart-legend"><span><i className="legend-dot blue-dot" />累计客户 <strong>{stats.companies}</strong></span><span><i className="legend-dot purple-dot" />采集记录 <strong>{stats.raw_leads}</strong></span></div>
        </div>
        <div className="panel quick-panel">
          <div className="panel-heading"><div><h2>快速开始</h2><p>把下一批中亚客户带回来。</p></div><Sparkles size={18} className="purple-icon" /></div>
          <div className="quick-list">
            <button onClick={() => onNavigate("发现线索")}><span className="quick-icon blue-bg"><Globe2 size={17} /></span><span><strong>发现新客户</strong><small>2GIS / Google 搜索采集</small></span><ArrowUpRight size={16} /></button>
            <button onClick={() => onNavigate("客户库")}><span className="quick-icon purple-bg"><Users size={17} /></span><span><strong>整理客户库</strong><small>筛选并标记高意向客户</small></span><ArrowUpRight size={16} /></button>
          </div>
        </div>
      </div>
    </>
  );
}

function MetricCard({ icon, label, value, change, detail, tone }: { icon: React.ReactNode; label: string; value: string; change: string; detail: string; tone: string }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-label">{label}<span className="metric-info">i</span></div><div className="metric-value">{value}</div><div className="metric-change"><span>↗ {change}</span> {detail}</div></div>;
}
