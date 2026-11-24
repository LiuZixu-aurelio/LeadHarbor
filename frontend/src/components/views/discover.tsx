"use client";

import { useMemo, useState } from "react";
import { Check, Database, KeyRound, Layers, LoaderCircle, MapPin, Search, Sparkles, Zap } from "lucide-react";

import {
  apiGet,
  apiPost,
  countryFlags,
  countryNames,
  type AIPipelineResult,
  type BatchCollectResult,
  type CollectConfig,
  type CollectJob,
  type CollectResult,
  jobStatusLabels,
  type SourceMeta,
} from "@/lib/api";

const fallbackSources: SourceMeta[] = [
  { name: "2gis", label: "2GIS", requires_key: "TWOGIS_API_KEY", default_region: "KZ", supported_regions: ["KZ", "UZ", "KG", "TJ", "TM", "RU"] },
  { name: "google_places", label: "Google Places", requires_key: "GOOGLE_PLACES_API_KEY", default_region: "KZ", supported_regions: ["KZ", "UZ", "KG", "TJ", "TM", "DE", "US", "GB", "AE", "TR"] },
  { name: "google_search", label: "Google 搜索", requires_key: "GOOGLE_SEARCH_API_KEY", default_region: "KZ", supported_regions: ["KZ", "UZ", "KG", "TJ", "TM", "RU"] },
  { name: "openstreetmap", label: "OpenStreetMap（免费）", requires_key: null, default_region: "KZ", supported_regions: ["KZ", "UZ", "KG", "TJ", "TM", "RU"] },
  { name: "opencorporates", label: "OpenCorporates", requires_key: "OPENCORPORATES_API_TOKEN", default_region: "KZ", supported_regions: ["KZ", "UZ", "KG", "TJ", "TM", "RU"] },
  { name: "wikidata", label: "Wikidata（免费）", requires_key: null, default_region: "KZ", supported_regions: ["KZ", "UZ", "KG", "TJ", "TM", "RU"] },
  { name: "yandex_maps", label: "Yandex 地图", requires_key: "YANDEX_GEOSEARCH_API_KEY", default_region: "KZ", supported_regions: ["KZ", "UZ", "KG", "TJ", "TM", "RU"] },
  { name: "ai_researcher", label: "AI 研究员（OpenAI）", requires_key: "OPENAI_API_KEY", default_region: "KZ", supported_regions: ["KZ", "UZ", "KG", "TJ", "TM", "RU"] },
  { name: "ai_extractor", label: "AI 网页提取（OpenAI）", requires_key: "OPENAI_API_KEY", default_region: null, supported_regions: [] },
  { name: "website", label: "官网/主页抓取", requires_key: null, default_region: "KZ", supported_regions: ["KZ", "UZ", "KG", "TJ", "TM"] },
];

type Mode = "single" | "batch";

export default function DiscoverView({ config, notify }: { config: CollectConfig | null; notify: (m: string) => void }) {
  const sources = config?.sources?.length ? config.sources : fallbackSources;
  const templates = config?.templates ?? [];
  const targetCountries = config?.target_countries ?? ["KZ", "UZ", "KG", "TJ", "TM"];

  const [mode, setMode] = useState<Mode>("batch");
  const [source, setSource] = useState("2gis");
  const [keyword, setKeyword] = useState("LED lighting distributor");
  const [region, setRegion] = useState(config?.default_region || "KZ");
  const [maxItems, setMaxItems] = useState(20);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<CollectResult | null>(null);

  const [batchMax, setBatchMax] = useState(10);
  const [rounds, setRounds] = useState(1);
  const [regions, setRegions] = useState<string[]>(targetCountries);
  const [batchResult, setBatchResult] = useState<BatchCollectResult | null>(null);
  const [job, setJob] = useState<CollectJob | null>(null);
  const [aiPipelineRunning, setAiPipelineRunning] = useState(false);
  const [aiMaxPages, setAiMaxPages] = useState(5);

  const selected = sources.find((s) => s.name === source) ?? sources[0];
  const isWebsite = selected?.name === "website" || selected?.name === "ai_extractor";
  const isUrlCollector = selected?.name === "website";
  const isAIExtractor = selected?.name === "ai_extractor";
  const regionOptions = useMemo(() => {
    const r = selected?.supported_regions?.length ? selected.supported_regions : targetCountries;
    return Array.from(new Set(r));
  }, [selected, targetCountries]);

  function onSourceChange(name: string) {
    setSource(name);
    const src = sources.find((s) => s.name === name);
    if (src?.default_region) setRegion(src.default_region);
    setResult(null);
    setBatchResult(null);
  }

  function toggleRegion(code: string) {
    setRegions((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  }

  async function runSingle() {
    if (!keyword.trim()) { notify("请填写关键词或目标网址"); return; }
    setRunning(true);
    setResult(null);
    try {
      const query = isWebsite
        ? { urls: keyword.split(/[\s,]+/).filter(Boolean) }
        : { text_query: keyword, region };
      const res = await apiPost<CollectResult>("/collect", { source, query, max_items: maxItems });
      setResult(res);
      notify(`采集完成：新增 ${res.ingested} 条，重复 ${res.duplicates}，失败 ${res.failed}`);
    } catch (err) {
      notify("采集失败：" + (err instanceof Error ? err.message : "未知错误"));
    } finally {
      setRunning(false);
    }
  }

  async function runAIPipeline() {
    if (!keyword.trim()) { notify("请填写 AI 搜索关键词"); return; }
    setAiPipelineRunning(true);
    try {
      const res = await apiPost<AIPipelineResult>("/collect/ai-pipeline", {
        keyword,
        region,
        max_pages: aiMaxPages,
        max_items_per_page: batchMax,
        language: "en",
      });
      notify(`AI 完成：发现 ${res.pages_found} 页，处理 ${res.pages_processed} 页，新增 ${res.ingested} 条`);
      setResult({ source: "ai_pipeline", fetched: res.fetched, ingested: res.ingested, duplicates: res.duplicates, failed: res.failed });
    } catch (err) {
      notify("AI 串联失败：" + (err instanceof Error ? err.message : "未知错误"));
    } finally {
      setAiPipelineRunning(false);
    }
  }

  async function runBatch() {
    if (!keyword.trim()) { notify(isUrlCollector ? "请填写网址" : "请选择模板或填写关键词"); return; }
    if (isUrlCollector || isAIExtractor) {
      const urls = keyword.split(/[\s,]+/).filter(Boolean);
      setRunning(true);
      try {
        const query = isAIExtractor
          ? { text_query: keyword, region, max_pages: aiMaxPages, language: "en" }
          : { urls };
        const res = await apiPost<CollectResult>("/collect", { source, query, max_items: batchMax * Math.max(1, rounds) });
        setResult(res);
        notify(`${isAIExtractor ? "AI 网页搜索提取" : "批量网址采集"}完成：新增 ${res.ingested} 条，重复 ${res.duplicates}，失败 ${res.failed}`);
      } catch (err) { notify("采集失败：" + (err instanceof Error ? err.message : "未知错误")); } finally { setRunning(false); }
      return;
    }
    if (regions.length === 0) { notify("请至少选择一个国家"); return; }
    setRunning(true);
    setBatchResult(null);
    setJob(null);
    try {
      const created = await apiPost<CollectJob>("/collect/batch/async", {
        source,
        text_query: keyword,
        regions,
        max_items_per_region: batchMax,
        rounds,
        language: "en",
      });
      setJob(created);
      notify(`任务已加入队列：${regions.length} 国，正在后台采集`);
      void pollJob(created.id);
    } catch (err) {
      setRunning(false);
      notify("任务创建失败：" + (err instanceof Error ? err.message : "未知错误"));
    }
  }

  async function pollJob(jobId: number) {
    for (let attempt = 0; attempt < 300; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      try {
        const current = await apiGet<CollectJob>(`/collect/jobs/${jobId}`);
        setJob(current);
        if (["success", "partial", "failed"].includes(current.status)) {
          setRunning(false);
          setBatchResult({
            source: current.source,
            text_query: current.text_query,
            regions_total: current.total_regions,
            total_fetched: current.total_fetched,
            total_ingested: current.total_ingested,
            total_duplicates: current.total_duplicates,
            total_failed: current.total_failed,
            items: current.results.map((item) => ({ region: item.region, result: { source: current.source, fetched: item.fetched, ingested: item.ingested, duplicates: item.duplicates, failed: item.failed }, error: item.error })),
          });
          notify(current.status === "failed" ? `批量任务失败：${current.error || "请检查数据源配置"}` : `批量完成：新增 ${current.total_ingested} 条`);
          return;
        }
      } catch {
        // 网络短暂中断时继续轮询，避免误报任务失败
      }
    }
    setRunning(false);
    notify("任务仍在后台运行，可到「采集任务」查看进度");
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">发现线索</p>
          <h1>从数据源发现新客户</h1>
          <p className="subtitle">单次精准采集，或按国家一键批量采集中亚市场。</p>
        </div>
        <div className="mode-tabs">
          <button className={mode === "batch" ? "active" : ""} onClick={() => setMode("batch")}><Layers size={15} /> 按国家批量</button>
        </div>
      </div>

      <div className="discover-grid">
        <div className="panel discover-form">
          <div className="panel-heading"><div><h2>{mode === "single" ? "采集配置" : isUrlCollector ? "批量网址采集" : "批量采集模板"}</h2><p>{mode === "single" ? "选择数据源、关键词与区域。" : isUrlCollector ? "输入多个网址，一次性抓取并入库。" : "选行业模板 + 多国，一键跑完。"}</p></div><Sparkles size={18} className="purple-icon" /></div>

          <div className="source-tabs">
            {sources.map((s) => (
              <button key={s.name} className={`source-tab ${source === s.name ? "active" : ""}`} onClick={() => onSourceChange(s.name)}>
                <span className="source-tab-title">{s.label}</span>
                <span className="source-tab-sub">{s.requires_key ? "需密钥" : "免密钥"}</span>
              </button>
            ))}
          </div>

          {mode === "batch" && templates.length > 0 && (
            <div className="template-block">
              <span className="block-label">行业模板</span>
              <div className="template-chips">
                {templates.map((t) => (
                  <button key={t.key} className={`chip ${keyword === t.keyword ? "active" : ""}`} onClick={() => setKeyword(t.keyword)} title={t.description}>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <label className="field">
            {isUrlCollector ? "目标网址（多个用逗号或空格分隔）" : "搜索关键词 / 网址"}
            <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder={isUrlCollector ? "如 acme.kz, partner.uz" : "如 wholesaler / lighting distributors"} />
          </label>

          {mode === "single" ? (
            <div className="form-row">
              {!isWebsite && (
                <label className="field">目标区域
                  <div className="select-wrap"><MapPin size={15} />
                    <select value={region} onChange={(e) => setRegion(e.target.value)}>
                      {regionOptions.map((code) => <option key={code} value={code}>{countryNames[code] ? `${countryNames[code]}（${code}）` : code}</option>)}
                    </select>
                  </div>
                </label>
              )}
              <label className="field">最大条数<input type="number" min={1} max={200} value={maxItems} onChange={(e) => setMaxItems(Number(e.target.value))} /></label>
            </div>
          ) : (
            <>
              <div className="template-block">
                <span className="block-label">目标国家</span>
                <div className="country-checks">
                  {targetCountries.map((code) => (
                    <button key={code} className={`country-check ${regions.includes(code) ? "active" : ""}`} onClick={() => toggleRegion(code)}>
                      {regions.includes(code) && <Check size={12} />}
                      <span className="flag">{countryFlags[code] || "🌐"}</span>
                      {countryNames[code] ? `${countryNames[code]}` : code}
                    </button>
                  ))}
                </div>
              </div>
              <label className="field">每国最大条数<input type="number" min={1} max={50} value={batchMax} onChange={(e) => setBatchMax(Number(e.target.value))} /></label>
              <label className="field">采集轮次<input type="number" min={1} max={20} value={rounds} onChange={(e) => setRounds(Number(e.target.value))} /><small>每轮自动翻页，尽量获取不同客户</small></label>
              <label className="field">AI 搜索页数<input type="number" min={1} max={20} value={aiMaxPages} onChange={(e) => setAiMaxPages(Number(e.target.value))} /><small>需要 Google 搜索 + OpenAI Key</small></label>
            </>
          )}

          <button className="ai-pipeline-button" onClick={runAIPipeline} disabled={running || aiPipelineRunning}>
            {aiPipelineRunning ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />} AI 搜索并提取入库
          </button>

          <button className="primary-button modal-submit" onClick={mode === "single" ? runSingle : runBatch} disabled={running}>
            {running ? <LoaderCircle className="spin" size={17} /> : mode === "single" ? <Zap size={17} /> : <Layers size={17} />}
            {running ? (job ? `后台采集中 ${job.processed_regions}/${job.total_regions} 国…` : "正在创建任务…") : mode === "single" ? "开始采集" : isUrlCollector ? "批量抓取网址" : isAIExtractor ? "AI 搜索网页并提取" : `一键批量采集（${regions.length} 国）`}
          </button>

          {selected?.requires_key && (
            <p className="hint-line"><KeyRound size={14} /> 需要配置 <code>{selected.requires_key}</code>，否则该数据源会返回报错。</p>
          )}
        </div>

        <div className="panel discover-side">
          <div className="panel-heading"><div><h2>{mode === "batch" ? "批量结果" : "采集结果"}</h2><p>本次任务的入库统计。</p></div><Database size={18} className="purple-icon" /></div>

          {mode === "single" && (
            result ? (
              <div className="result-grid">
                <ResultStat label="抓取" value={result.fetched} tone="blue" />
                <ResultStat label="入库" value={result.ingested} tone="green" />
                <ResultStat label="重复" value={result.duplicates} tone="orange" />
                <ResultStat label="失败" value={result.failed} tone="red" />
              </div>
            ) : <div className="result-placeholder"><Search size={22} /><p>还没有本次结果，点击「开始采集」试试。</p></div>
          )}

          {mode === "batch" && job && running && (
            <div className="job-progress">
              <div className="job-progress-top"><span>{jobStatusLabels[job.status] || job.status}</span><strong>{job.processed_regions}/{job.total_regions}</strong></div>
              <div className="job-progress-track"><i style={{ width: `${job.total_regions ? (job.processed_regions / job.total_regions) * 100 : 0}%` }} /></div>
              <p>任务在后台运行中，可以切换到其他模块。</p>
            </div>
          )}

          {mode === "batch" && (
            batchResult ? (
              <>
                <div className="result-grid">
                  <ResultStat label="抓取" value={batchResult.total_fetched} tone="blue" />
                  <ResultStat label="入库" value={batchResult.total_ingested} tone="green" />
                  <ResultStat label="重复" value={batchResult.total_duplicates} tone="orange" />
                  <ResultStat label="失败" value={batchResult.total_failed} tone="red" />
                </div>
                <div className="region-results">
                  {batchResult.items.map((item) => (
                    <div className="region-row" key={item.region}>
                      <span className="country"><span className="flag">{countryFlags[item.region] || "🌐"}</span>{countryNames[item.region] || item.region}</span>
                      {item.error ? <span className="region-error">{item.error}</span> : <span className="region-ok">+{item.result?.ingested ?? 0} 入库</span>}
                    </div>
                  ))}
                </div>
              </>
            ) : <div className="result-placeholder"><Layers size={22} /><p>选择模板与国家，点击「一键批量采集」。</p></div>
          )}
        </div>
      </div>
    </>
  );
}

function ResultStat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return <div className={`result-stat ${tone}`}><span className="result-value">{value}</span><span className="result-label">{label}</span></div>;
}
