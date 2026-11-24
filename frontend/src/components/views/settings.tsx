"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, KeyRound, LoaderCircle, PlugZap, RotateCcw, Save, ShieldCheck, X } from "lucide-react";

import { apiGet, apiPost, apiPut, type CollectConfig, type SettingsKey, type SourceMeta } from "@/lib/api";

type TestState = { ok: boolean; message: string; sample?: { name?: string | null } | null };

export default function SettingsView({ notify }: { notify: (m: string) => void }) {
  const [keys, setKeys] = useState<SettingsKey[]>([]);
  const [sources, setSources] = useState<SourceMeta[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [cleared, setCleared] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [testResult, setTestResult] = useState<Record<string, TestState>>({});

  async function load() {
    setLoading(true);
    try {
      const [keyData, config] = await Promise.all([
        apiGet<SettingsKey[]>("/settings/keys"),
        apiGet<CollectConfig>("/collect/config"),
      ]);
      setKeys(keyData);
      setSources(config.sources ?? []);
    } catch {
      notify("加载配置失败，请确认后端运行");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const groups = useMemo(() => {
    const map = new Map<string, SettingsKey[]>();
    for (const key of keys) {
      const arr = map.get(key.group) ?? [];
      arr.push(key);
      map.set(key.group, arr);
    }
    return Array.from(map.entries());
  }, [keys]);

  async function save() {
    const updates: Record<string, string> = {};
    for (const [name, value] of Object.entries(draft)) {
      if (value !== "") updates[name] = value;
    }
    // 只对明确标记为「清除」(true) 的字段发空值
    for (const [name, isCleared] of Object.entries(cleared)) {
      if (isCleared) updates[name] = "";
    }
    if (Object.keys(updates).length === 0) {
      notify("没有需要保存的修改");
      return;
    }
    setSaving(true);
    try {
      const data = await apiPut<SettingsKey[]>("/settings/keys", { updates });
      setKeys(data);
      setDraft({});
      setCleared({});
      notify("配置已保存并生效");
    } catch (err) {
      notify("保存失败：" + (err instanceof Error ? err.message : "未知错误"));
    } finally {
      setSaving(false);
    }
  }

  async function testSource(source: string) {
    setTesting((p) => ({ ...p, [source]: true }));
    setTestResult((p) => { const n = { ...p }; delete n[source]; return n; });
    try {
      const res = await apiPost<TestState>("/settings/test", { source });
      setTestResult((p) => ({ ...p, [source]: res }));
    } catch (err) {
      setTestResult((p) => ({ ...p, [source]: { ok: false, message: err instanceof Error ? err.message : "测试失败" } }));
    } finally {
      setTesting((p) => ({ ...p, [source]: false }));
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">设置</p>
          <h1>数据源密钥配置</h1>
          <p className="subtitle">在此填写各渠道密钥，保存后立即生效（API 与后台任务共用）。</p>
        </div>
        <button className="primary-button" onClick={save} disabled={saving}>
          {saving ? <LoaderCircle className="spin" size={16} /> : <Save size={16} />} 保存配置
        </button>
      </div>

      <div className="settings-note">
        <ShieldCheck size={16} />
        <span>密钥仅保存在你自己的数据库（app_setting 表），接口返回为打码值。请勿在不可信环境使用。</span>
      </div>

      {loading && <div className="panel settings-loading"><LoaderCircle className="spin" size={20} /> 加载中…</div>}

      <div className="settings-grid">
        {groups.map(([group, fields]) => (
          <div className="panel settings-group" key={group}>
            <div className="panel-heading"><div><h2>{group}</h2></div></div>
            {fields.map((field) => {
              const isBool = field.kind === "bool";
              const boolOn = draft[field.name] !== undefined ? draft[field.name] === "true" : field.configured;
              const isCleared = cleared[field.name];
              return (
                <div className="settings-row" key={field.name}>
                  <div className="settings-label">
                    <span>{field.label}</span>
                    <code>{field.name}</code>
                  </div>
                  <div className="settings-control">
                    {isBool ? (
                      <button className={`toggle ${boolOn ? "on" : ""}`} onClick={() => setDraft((p) => ({ ...p, [field.name]: boolOn ? "false" : "true" }))}>
                        <i />{boolOn ? "已启用" : "未启用"}
                      </button>
                    ) : (
                      <input
                        type={field.secret ? "password" : "text"}
                        className="settings-input"
                        value={isCleared ? "" : draft[field.name] ?? (field.secret ? "" : field.value ?? "")}
                        placeholder={
                          isCleared
                            ? "已清除，保存后生效"
                            : field.secret
                              ? field.configured
                                ? `当前 ${field.masked ?? ""} · 输入新值可覆盖`
                                : "未配置 · 输入后点击右上角保存"
                              : "未配置"
                        }
                        onChange={(e) => { setCleared((p) => ({ ...p, [field.name]: false })); setDraft((p) => ({ ...p, [field.name]: e.target.value })); }}
                      />
                    )}
                    <span className={`key-status ${(isBool ? boolOn : field.configured) && !isCleared ? "ok" : ""}`}>
                      {isBool ? (boolOn ? <><Check size={12} />启用</> : "关闭") : field.configured && !isCleared ? <><Check size={12} />已配置</> : "未配置"}
                    </span>
                    {field.secret && field.configured && !isCleared && (
                      <button className="icon-clear" title="清除" onClick={() => { setCleared((p) => ({ ...p, [field.name]: true })); setDraft((p) => { const n = { ...p }; delete n[field.name]; return n; }); }}>
                        <RotateCcw size={14} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {!loading && keys.length === 0 && <div className="panel empty-state">暂无可配置项</div>}

      <div className="panel settings-group test-panel">
        <div className="panel-heading">
          <div><h2>渠道连接测试</h2><p>对每个渠道发一个最小请求，验证密钥与网络是否可用（不写库）。</p></div>
          <PlugZap size={18} className="purple-icon" />
        </div>
        <div className="test-list">
          {sources.map((src) => {
            const res = testResult[src.name];
            const busy = testing[src.name];
            return (
              <div className="test-row" key={src.name}>
                <div className="test-meta">
                  <span className="test-name">{src.label}</span>
                  <span className={`test-keyflag ${src.requires_key ? "req" : ""}`}>{src.requires_key ? `需 ${src.requires_key}` : "免密钥"}</span>
                </div>
                <div className="test-action">
                  {res && (
                    <span className={`test-result ${res.ok ? "ok" : "err"}`}>
                      {res.ok ? <Check size={13} /> : <X size={13} />}
                      {res.ok ? (res.sample?.name ? `成功：${res.sample.name}` : res.message) : res.message}
                    </span>
                  )}
                  <button className="ghost-button small" onClick={() => testSource(src.name)} disabled={busy}>
                    {busy ? <LoaderCircle className="spin" size={14} /> : <PlugZap size={14} />} 测试
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="settings-foot">
        <KeyRound size={14} /> 提示：未配置的渠道可在「发现线索」中使用免密钥的 OpenStreetMap / Wikidata / 官网抓取。
      </div>
    </>
  );
}
