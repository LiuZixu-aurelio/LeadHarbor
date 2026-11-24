"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Download, Filter, Globe, ListFilter, LoaderCircle, Mail, Phone, RefreshCw, Search, Upload } from "lucide-react";

import CompanyDrawer from "@/components/company-drawer";

import {
  apiGet,
  exportCompaniesUrl,
  importCompanies,
  countryFlags,
  countryLabel,
  countryNames,
  statusLabels,
  type Company,
  type Stats,
} from "@/lib/api";

const PAGE_SIZE = 10;

export default function CustomersView({ notify, stats }: { notify: (m: string) => void; stats: Stats }) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [status, setStatus] = useState("all");
  const [country, setCountry] = useState("all");
  const [contactFilter, setContactFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await apiGet<Company[]>("/companies?limit=200");
      setCompanies(data);
    } catch {
      notify("加载客户失败，请确认后端 API 正在运行");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const countries = useMemo(() => {
    const set = new Set<string>();
    companies.forEach((c) => c.country && set.add(c.country));
    return Array.from(set);
  }, [companies]);

  const filtered = useMemo(() => companies.filter((c) => {
    const matchQuery = [c.name, c.domain, c.industry, c.country]
      .filter(Boolean).join(" ").toLowerCase().includes(query.toLowerCase());
    const matchScore = (c.ai_score ?? 0) >= minScore;
    const matchStatus = status === "all" || c.status === status;
    const matchCountry = country === "all" || c.country === country;
    const hasSite = Boolean(c.website || c.domain);
    const matchContact =
      contactFilter === "all" ||
      (contactFilter === "email" && c.has_email) ||
      (contactFilter === "no-email" && !c.has_email) ||
      (contactFilter === "phone" && c.has_phone) ||
      (contactFilter === "no-phone" && !c.has_phone) ||
      (contactFilter === "website" && hasSite);
    return matchQuery && matchScore && matchStatus && matchCountry && matchContact;
  }), [companies, query, minScore, status, country, contactFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  function resetPage<T>(setter: (v: T) => void) {
    return (value: T) => { setter(value); setPage(1); };
  }

  function exportData() {
    const a = document.createElement("a");
    a.href = exportCompaniesUrl();
    a.download = "leadharbor_companies.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function onImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImporting(true);
    try {
      const res = await importCompanies(file);
      notify(`导入完成：新增 ${res.created}，更新 ${res.updated}，跳过 ${res.skipped}`);
      await load();
    } catch (err) {
      notify("导入失败：" + (err instanceof Error ? err.message : "未知错误"));
    } finally {
      setImporting(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">客户库</p>
          <h1>全部客户</h1>
          <p className="subtitle">共 {stats.companies} 家客户，按 AI 匹配度排序，支持多维筛选。</p>
        </div>
        <div className="heading-actions">
          <input ref={fileInputRef} type="file" accept=".csv,text/csv" hidden onChange={onImportFile} />
          <button className="primary-button ghost" onClick={() => fileInputRef.current?.click()} disabled={importing}>
            {importing ? <LoaderCircle className="spin" size={16} /> : <Upload size={16} />} 导入
          </button>
          <button className="primary-button ghost" onClick={exportData}>
            <Download size={16} /> 导出
          </button>
          <button className="primary-button ghost" onClick={load} disabled={loading}>
            {loading ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />} 刷新
          </button>
        </div>
      </div>

      <div className="panel table-panel">
        <div className="table-toolbar">
          <div className="search-field"><Search size={16} /><input value={query} onChange={(e) => resetPage(setQuery)(e.target.value)} placeholder="搜索公司、域名、行业或国家" /></div>
          <div className="toolbar-actions">
            <div className="filter-select"><Filter size={15} /><select value={minScore} onChange={(e) => resetPage(setMinScore)(Number(e.target.value))}><option value={0}>全部评分</option><option value={60}>评分 60+</option><option value={80}>评分 80+</option><option value={90}>评分 90+</option></select><ChevronDown size={14} /></div>
            <div className="filter-select"><select value={contactFilter} onChange={(e) => resetPage(setContactFilter)(e.target.value)}><option value="all">全部联系方式</option><option value="website">有官网</option><option value="email">有邮箱</option><option value="no-email">缺邮箱</option><option value="phone">有电话</option><option value="no-phone">缺电话</option></select><ChevronDown size={14} /></div>
            <div className="filter-select"><select value={status} onChange={(e) => resetPage(setStatus)(e.target.value)}><option value="all">全部状态</option><option value="lead">新线索</option><option value="qualified">已认证</option><option value="contacted">已触达</option><option value="replied">已回复</option></select><ChevronDown size={14} /></div>
            <div className="filter-select"><select value={country} onChange={(e) => resetPage(setCountry)(e.target.value)}><option value="all">全部国家</option>{countries.map((code) => <option key={code} value={code}>{countryNames[code] ? `${countryNames[code]}（${code}）` : code}</option>)}</select><ChevronDown size={14} /></div>
            <button className="view-button"><ListFilter size={16} /></button>
          </div>
        </div>

        <div className="table-scroll">
          <table>
            <thead><tr><th>公司</th><th>国家 / 地区</th><th>行业</th><th>联系方式</th><th>来源</th><th>AI 匹配度</th><th>状态</th><th /></tr></thead>
            <tbody>
              {pageRows.map((company) => (
                <tr key={company.id} className="clickable-row" onClick={() => setSelectedId(company.id)}>
                  <td><div className="company-cell"><div className="company-logo">{company.name.slice(0, 1)}</div><div><strong>{company.name}</strong><span>{company.domain || "暂无域名"}</span></div></div></td>
                  <td><span className="country"><span className="flag">{countryFlags[company.country || ""] || "🌐"}</span>{countryLabel(company.country)}</span></td>
                  <td>{company.industry || "未分类"}</td>
                  <td>
                    <div className="contact-indicators">
                      <span className={`ci ${company.has_email ? "ok" : "off"}`} title={company.has_email ? "有邮箱" : "无邮箱"}><Mail size={13} /></span>
                      <span className={`ci ${company.has_phone ? "ok" : "off"}`} title={company.has_phone ? "有电话" : "无电话"}><Phone size={13} /></span>
                      <span className={`ci ${(company.website || company.domain) ? "ok" : "off"}`} title={(company.website || company.domain) ? "有官网" : "无官网"}><Globe size={13} /></span>
                      {(company.contact_count ?? 0) > 0 && <span className="ci-count">{company.contact_count}</span>}
                    </div>
                  </td>
                  <td><span className="source-pill">{company.source || "LeadHarbor"}</span></td>
                  <td><div className="score-cell"><div className="score-bar"><i style={{ width: `${company.ai_score ?? 0}%` }} /></div><strong>{company.ai_score ?? "—"}</strong></div></td>
                  <td><span className={`status status-${company.status}`}>{statusLabels[company.status] || company.status}</span></td>
                  <td><button className="row-more" aria-label={`查看 ${company.name}`}>···</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {pageRows.length === 0 && <div className="empty-state">{loading ? "加载中…" : "没有匹配的客户"}</div>}
        </div>

        <div className="table-footer">
          <span>共 {filtered.length} 条 · 第 {safePage}/{totalPages} 页</span>
          <div>
            <button disabled={safePage <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>上一页</button>
            {Array.from({ length: totalPages }).slice(0, 7).map((_, i) => (
              <button key={i} className={safePage === i + 1 ? "current-page" : ""} onClick={() => setPage(i + 1)}>{i + 1}</button>
            ))}
            <button disabled={safePage >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>下一页</button>
          </div>
        </div>
      </div>

      <CompanyDrawer
        companyId={selectedId}
        onClose={() => setSelectedId(null)}
        onUpdated={load}
        notify={notify}
      />
    </>
  );
}
