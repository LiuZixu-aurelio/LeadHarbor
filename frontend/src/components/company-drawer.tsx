"use client";

import { useEffect, useState } from "react";
import {
  Ban,
  BadgeCheck,
  Building2,
  Globe,
  Link as LinkIcon,
  LoaderCircle,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  Save,
  Sparkles,
  X,
} from "lucide-react";

import {
  apiGet,
  apiPatch,
  apiPost,
  companyStatuses,
  countryFlags,
  countryLabel,
  type CompanyDetail,
} from "@/lib/api";

function externalUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}

export default function CompanyDrawer({
  companyId,
  onClose,
  onUpdated,
  notify,
}: {
  companyId: number | null;
  onClose: () => void;
  onUpdated: () => void;
  notify: (m: string) => void;
}) {
  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [enrichStatus, setEnrichStatus] = useState<string[]>([]);

  useEffect(() => {
    if (companyId == null) return;
    setLoading(true);
    setDetail(null);
    apiGet<CompanyDetail>(`/companies/${companyId}`)
      .then((d) => { setDetail(d); setStatus(d.status); })
      .catch(() => notify("加载客户详情失败"))
      .finally(() => setLoading(false));
  }, [companyId, notify]);

  if (companyId == null) return null;

  async function save() {
    if (!detail) return;
    setSaving(true);
    try {
      const updated = await apiPatch<CompanyDetail>(`/companies/${detail.id}`, { status });
      setDetail(updated);
      notify("客户状态已更新");
      onUpdated();
    } catch (err) {
      notify("更新失败：" + (err instanceof Error ? err.message : "未知错误"));
    } finally {
      setSaving(false);
    }
  }

  async function enrich() {
    if (!detail) return;
    setEnriching(true);
    try {
      setEnrichStatus([
        "优先深度抓取官网首页及联系/关于/支持页面…",
        "随后查询已配置的搜索和地图渠道…",
      ]);
      const res = await apiPost<{ found: { email: number; phone: number; address: number }; attempts: { source: string; status: string; message?: string }[]; company: CompanyDetail }>(
        `/companies/${detail.id}/enrich`,
        {},
      );
      setDetail(res.company);
      setStatus(res.company.status);
      setEnrichStatus(res.attempts.map((item) => `${item.source}: ${item.status}${item.message ? `（${item.message}）` : ""}`));
      const total = res.found.email + res.found.phone + res.found.address;
      notify(total ? `已从多渠道补全 ${total} 项联系方式` : "各渠道暂未找到新的联系方式");
      onUpdated();
    } catch (err) {
      notify("补全失败：" + (err instanceof Error ? err.message : "未知错误"));
    } finally {
      setEnriching(false);
    }
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <button className="drawer-close" onClick={onClose} aria-label="关闭"><X size={18} /></button>

        {loading && <div className="drawer-loading"><LoaderCircle className="spin" size={22} /></div>}

        {detail && (
          <>
            <div className="drawer-head">
              <div className="drawer-logo">{detail.name.slice(0, 1)}</div>
              <div className="drawer-title">
                <h2>{detail.name}</h2>
                <span className="drawer-domain">{externalUrl(detail.website) || externalUrl(detail.domain) ? <a href={externalUrl(detail.website) || externalUrl(detail.domain) || "#"} target="_blank" rel="noreferrer">{detail.domain || detail.website}</a> : (detail.domain || "暂无域名")}</span>
              </div>
            </div>

            <div className="drawer-meta">
              <Meta icon={<MapPin size={14} />} label="国家"><span className="flag">{countryFlags[detail.country || ""] || "🌐"}</span> {countryLabel(detail.country)}</Meta>
              <Meta icon={<Building2 size={14} />} label="行业">{detail.industry || "未分类"}</Meta>
              <Meta icon={<Globe size={14} />} label="来源">{detail.source || "—"}</Meta>
              <Meta icon={<BadgeCheck size={14} />} label="AI 匹配度"><strong>{detail.ai_score ?? "—"}</strong></Meta>
              <Meta icon={<Phone size={14} />} label="电话">{detail.phone ? <a href={`tel:${detail.phone}`}>{detail.phone}</a> : <span className="muted">未获取</span>}</Meta>
              <Meta icon={<MapPin size={14} />} label="地址">{detail.address || <span className="muted">未获取</span>}</Meta>
              <Meta icon={<Globe size={14} />} label="官网">{externalUrl(detail.website) || externalUrl(detail.domain) ? <a href={externalUrl(detail.website) || externalUrl(detail.domain) || "#"} target="_blank" rel="noreferrer" className="drawer-website">{(detail.website || detail.domain || "").replace(/^https?:\/\//, "")}</a> : <span className="muted">未获取</span>}</Meta>
            </div>

            <div className="drawer-section">
              <div className="drawer-section-head"><h3>生命周期状态</h3></div>
              <div className="drawer-status-edit">
                <select value={status} onChange={(e) => setStatus(e.target.value)}>
                  {companyStatuses.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
                <button className="primary-button" onClick={save} disabled={saving || status === detail.status}>
                  {saving ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />} 保存
                </button>
              </div>
            </div>

            <div className="drawer-section">
              <div className="drawer-section-head">
                <h3>联系人</h3>
                <div className="drawer-section-actions">
                  <span>{detail.contacts.length}</span>
                  <button
                    className="ghost-button small"
                    onClick={enrich}
                    disabled={enriching || (!detail.website && !detail.domain)}
                    title={!detail.website && !detail.domain ? "该客户没有官网/域名" : "深度抓取官网最多 8 个页面，再查询其他渠道"}
                  >
                    {enriching ? <LoaderCircle className="spin" size={13} /> : <Sparkles size={13} />} 官网优先深度补全
                  </button>
                </div>
              </div>
              {enrichStatus.length > 0 && <div className="enrich-status"><strong>本次补全结果</strong>{enrichStatus.map((item) => <span key={item}>{item}</span>)}</div>}
              {detail.contacts.length === 0 && <div className="drawer-empty">暂无联系人，后续采集/抓取会补充邮箱与电话。</div>}
              <div className="contact-list">
                {detail.contacts.map((contact) => (
                  <div className="contact-card" key={contact.id}>
                    <div className="contact-top">
                      <strong>{contact.name || "未命名联系人"}</strong>
                      <div className="contact-badges">
                        {contact.email_verified && <span className="mini-badge ok"><BadgeCheck size={11} />已验证</span>}
                        {contact.do_not_contact && <span className="mini-badge danger"><Ban size={11} />免打扰</span>}
                      </div>
                    </div>
                    {contact.title && <span className="contact-title">{contact.title}</span>}
                    <div className="contact-lines">
                      {contact.email && <a href={`mailto:${contact.email}`}><Mail size={13} />{contact.email}</a>}
                      {contact.phone && <a href={`tel:${contact.phone}`}><Phone size={13} />{contact.phone}</a>}
                      {contact.whatsapp && <a href={`https://wa.me/${contact.whatsapp.replace(/[^\d]/g, "")}`} target="_blank" rel="noreferrer"><MessageCircle size={13} />{contact.whatsapp}</a>}
                      {contact.linkedin_url && <a href={contact.linkedin_url} target="_blank" rel="noreferrer"><LinkIcon size={13} />LinkedIn</a>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

function Meta({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return <div className="drawer-meta-item"><span className="drawer-meta-label">{icon}{label}</span><span className="drawer-meta-value">{children}</span></div>;
}
