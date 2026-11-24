export type Company = {
  id: number;
  name: string;
  domain?: string | null;
  website?: string | null;
  country?: string | null;
  industry?: string | null;
  phone?: string | null;
  address?: string | null;
  contact_count?: number;
  has_email?: boolean;
  has_phone?: boolean;
  ai_score?: number | null;
  status: string;
  source?: string | null;
  created_at?: string;
};

export type Stats = { companies: number; raw_leads: number };

export type LeadRaw = {
  id: number;
  source: string;
  status: string;
  error?: string | null;
  fetched_at: string;
};

export type SourceMeta = {
  name: string;
  label: string;
  requires_key?: string | null;
  default_region?: string | null;
  supported_regions: string[];
};

export type TemplateMeta = {
  key: string;
  label: string;
  keyword: string;
  description: string;
};

export type CollectConfig = {
  sources: SourceMeta[];
  target_countries: string[];
  default_region: string;
  templates?: TemplateMeta[];
};

export type BatchRegionResult = {
  region: string;
  result?: CollectResult | null;
  error?: string | null;
};

export type BatchCollectResult = {
  source: string;
  text_query: string;
  regions_total: number;
  total_fetched: number;
  total_ingested: number;
  total_duplicates: number;
  total_failed: number;
  items: BatchRegionResult[];
};

export type CollectResult = {
  source: string;
  fetched: number;
  ingested: number;
  duplicates: number;
  failed: number;
};

const BASE = "/api/backend/v1";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    let detail = text || `HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.detail) detail = String(parsed.detail);
    } catch {
      /* keep raw text */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const countryFlags: Record<string, string> = {
  KZ: "🇰🇿", UZ: "🇺🇿", KG: "🇰🇬", TJ: "🇹🇯", TM: "🇹🇲",
  RU: "🇷🇺", DE: "🇩🇪", US: "🇺🇸", GB: "🇬🇧", AE: "🇦🇪", TR: "🇹🇷", CN: "🇨🇳",
};

export const countryNames: Record<string, string> = {
  KZ: "哈萨克斯坦", UZ: "乌兹别克斯坦", KG: "吉尔吉斯斯坦", TJ: "塔吉克斯坦", TM: "土库曼斯坦",
  RU: "俄罗斯", DE: "德国", US: "美国", GB: "英国", AE: "阿联酋", TR: "土耳其", CN: "中国",
};

export const statusLabels: Record<string, string> = {
  lead: "新线索",
  qualified: "已认证",
  contacted: "已触达",
  replied: "已回复",
  meeting: "面谈中",
  won: "已成交",
  lost: "已流失",
  processed: "已处理",
  duplicate: "重复",
  failed: "失败",
};

export function countryLabel(code?: string | null): string {
  if (!code) return "—";
  return countryNames[code] ? `${countryNames[code]}（${code}）` : code;
}

export type ContactOut = {
  id: number;
  name?: string | null;
  title?: string | null;
  email?: string | null;
  phone?: string | null;
  whatsapp?: string | null;
  linkedin_url?: string | null;
  email_verified?: boolean;
  do_not_contact?: boolean;
  source?: string | null;
};

export type CompanyDetail = Company & { contacts: ContactOut[] };

export const companyStatuses: { value: string; label: string }[] = [
  { value: "lead", label: "新线索" },
  { value: "qualified", label: "已认证" },
  { value: "contacted", label: "已触达" },
  { value: "replied", label: "已回复" },
  { value: "meeting", label: "面谈中" },
  { value: "won", label: "已成交" },
  { value: "lost", label: "已流失" },
];

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    let detail = text || `HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.detail) detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
    } catch {
      /* keep raw */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export type JobRegionResult = {
  region: string;
  fetched: number;
  ingested: number;
  duplicates: number;
  failed: number;
  error?: string | null;
};

export type CollectJob = {
  id: number;
  source: string;
  text_query: string;
  regions: string[];
  max_items_per_region: number;
  rounds?: number;
  language: string;
  status: string;
  total_regions: number;
  processed_regions: number;
  total_fetched: number;
  total_ingested: number;
  total_duplicates: number;
  total_failed: number;
  results: JobRegionResult[];
  error?: string | null;
  created_at: string;
  updated_at: string;
};

export const jobStatusLabels: Record<string, string> = {
  pending: "排队中",
  running: "采集中",
  success: "已完成",
  partial: "部分成功",
  failed: "失败",
};

export type SettingsKey = {
  name: string;
  label: string;
  group: string;
  secret: boolean;
  kind: string;
  configured: boolean;
  value?: string | null;
  masked?: string | null;
  display: string;
};

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    let detail = text || `HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.detail) detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
    } catch {
      /* keep raw */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function exportCompaniesUrl(): string {
  return `${BASE}/companies/export`;
}

export type ImportSummary = { created: number; updated: number; skipped: number };

export async function importCompanies(file: File): Promise<ImportSummary> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${BASE}/companies/import`, { method: "POST", body: form });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    let detail = text || `HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.detail) detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
    } catch { /* keep raw */ }
    throw new Error(detail);
  }
  return (await response.json()) as ImportSummary;
}

export type AIPipelineResult = {
  keyword: string;
  region: string;
  pages_found: number;
  pages_processed: number;
  fetched: number;
  ingested: number;
  duplicates: number;
  failed: number;
  urls: string[];
};
