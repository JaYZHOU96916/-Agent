"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, ArrowUpRight, Check, ChevronRight, CircleHelp, Database, FileSpreadsheet, Layers3, LoaderCircle, Plus, Settings2, ShieldCheck, Sparkles, Square, UploadCloud, X } from "lucide-react";
import Chart from "@/components/chart";
import Schema from "@/components/schema";
import { apiHeaders, responseError } from "@/lib/api";
import { consumeSSE } from "@/lib/sse";
import type { Dataset, StreamEvent } from "@/lib/types";

type Run = { question: string; events: StreamEvent[]; state: string; session?: string };
const suggestions = ["概括数据的关键特征与异常值", "找出最值得关注的增长趋势", "对比不同类别的表现"];
export default function Workspace() {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [question, setQuestion] = useState("");
  const [runs, setRuns] = useState<Run[]>([]);
  const [chart, setChart] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [token, setToken] = useState("");
  const [settings, setSettings] = useState(false);
  const [status, setStatus] = useState<{ model_configured: boolean; redis_available: boolean; model: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const controller = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => { fetch("/api/v1/system", { headers: apiHeaders(token) }).then(async r => {
    if (r.status === 401) { setSettings(true); return; }
    if (r.ok) setStatus(await r.json());
  }).catch(() => setStatus(null)); }, [token]);
  useEffect(() => { if (runs.length) bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [runs]);
  useEffect(() => () => controller.current?.abort(), []);
  async function upload(file?: File) {
    if (!file || busy || uploading) return;
    if (!/\.(csv|xlsx|xls|parquet)$/i.test(file.name)) { setError("请选择 CSV、Excel 或 Parquet 文件。"); return; }
    if (file.size > 20 * 1024 * 1024) { setError("文件不能超过 20 MB。"); return; }
    setUploading(true); setError("");
    try {
      const data = new FormData(); data.append("file", file);
      const response = await fetch("/api/v1/datasets", { method: "POST", headers: apiHeaders(token), body: data });
      if (!response.ok) throw new Error(await responseError(response));
      setDataset(await response.json()); setRuns([]); setChart(null);
    } catch (error) { setError((error as Error).message); } finally { setUploading(false); if (fileInput.current) fileInput.current.value = ""; }
  }
  async function analyze(prompt = question) {
    if (!dataset || !prompt.trim() || busy) return;
    setError(""); setBusy(true); setQuestion(""); setChart(null);
    const abort = new AbortController(); controller.current = abort;
    setRuns(previous => [...previous, { question: prompt, events: [], state: "running" }]);
    const update = (fn: (run: Run) => Run) => setRuns(previous => previous.map((run, i) => i === previous.length - 1 ? fn(run) : run));
    try {
      const response = await fetch("/api/v1/analyses", { method: "POST", headers: apiHeaders(token, true), body: JSON.stringify({ dataset_id: dataset.dataset_id, question: prompt }), signal: abort.signal });
      if (!response.ok) throw new Error(await responseError(response));
      await consumeSSE(response, event => {
        if (event.event === "chart" && event.data.option) setChart(event.data.option);
        update(run => ({ ...run, events: [...run.events, event], session: event.data.session_id || run.session,
          state: event.event === "done" ? event.data.status || "completed" : run.state }));
      });
    } catch (error) {
      const stopped = (error as Error).name === "AbortError";
      update(run => ({ ...run, state: stopped ? "cancelled" : "failed" }));
      if (!stopped) setError((error as Error).message);
    } finally { setBusy(false); controller.current = null; }
  }
  return <div className="workspace">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Forma 首页"><span className="brand-mark"><Layers3 size={22}/></span>forma<span className="brand-dot">.</span></a>
      <div className="workspace-label">数据分析工作空间 <span>个人版</span></div>
      <button className="new-button" disabled={busy} onClick={() => { setRuns([]); setChart(null); setError(""); }}><Plus size={17}/> 新建分析 <span>↗</span></button>
      <div className="sidebar-section"><span className="eyebrow">WORKSPACE</span><div className="nav-active"><Sparkles size={17}/> 分析工作台 <span>01</span></div></div>
      <div className="sidebar-section"><div className="sidebar-title"><span>数据源</span><button onClick={() => fileInput.current?.click()} disabled={busy || uploading} aria-label="添加数据源"><Plus size={15}/></button></div>
        {dataset ? <div className="dataset-link"><FileSpreadsheet size={18}/><span title={dataset.filename}>{dataset.filename}</span><i/></div> : <p className="sidebar-muted">上传文件后，数据源将在这里显示。</p>}
      </div>
      <div className="privacy-note"><ShieldCheck size={20}/><h4>计算有边界，洞见有依据</h4><p>代码在独立沙箱运行。模型接收数据概要与样例，完整文件用于隔离计算。</p></div>
      <div className="sidebar-bottom"><button onClick={() => setSettings(true)}><Settings2 size={17}/> 连接设置</button><a href="https://github.com/JaYZHOU96916/-Agent" target="_blank" rel="noreferrer"><CircleHelp size={17}/> 项目文档 <ArrowUpRight size={14}/></a><div className="profile"><span>U</span><div>我的工作空间<small>DATA ANALYST</small></div><span className="profile-dots">···</span></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div>工作空间 <ChevronRight size={14}/><strong>分析工作台</strong></div><div className="service-status"><i className={status?.model_configured ? "online" : ""}/>{status?.model_configured ? "模型已连接" : "等待模型配置"}<span className="divider"/>Code Interpreter</div></header>
      <div className="page-heading"><div><div className="eyebrow">YOUR DATA, A CLEARER PICTURE</div><h1>把数据，变成下一个好决策<span>。</span></h1><p>上传一份数据，说出你的问题。让分析从这里开始。</p></div><span className="version-tag">AI ANALYSIS / 04</span></div>
      <div className="work-grid">
        <section className="conversation-card">
          <div className="section-heading"><div className="heading-icon"><Sparkles size={18}/><h2>分析助手</h2></div><span className="small-status">{busy ? "正在分析" : "准备就绪"}</span></div>
          <div className="conversation-body">
            {!runs.length && <div className="intro"><span className="assistant-avatar"><Sparkles size={20}/></span><h3>每份数据，都藏着一个好问题。</h3><p>我会规划分析、编写代码，并在沙箱中验证结果。你可以随时查看每一步。</p><div className="starter-prompts">{suggestions.map((text, i) => <button key={text} disabled={!dataset || busy} onClick={() => setQuestion(text)}><span>0{i+1}</span>{text}<ArrowUpRight size={15}/></button>)}</div></div>}
            {runs.map((run, i) => <article className="run" key={i}><div className="user-message">{run.question}</div><div className="assistant-run"><span className="assistant-avatar"><Sparkles size={16}/></span><div className="run-content">
              {run.events.filter(e => e.event === "plan").map((event, j) => <div className="plan" key={`p${j}`}><h4>分析规划</h4>{event.data.steps?.map((step, k) => <div key={k}><span>{k+1}</span>{step}</div>)}</div>)}
              <div className="step-pills">{run.events.filter(e => e.event === "status" && e.data.state !== "started").map((event, j) => <span key={j}>{({ CodeGenerator: "生成代码", SandboxExecutor: "沙箱执行", ChartFormatter: "整理图表", cache_hit: "缓存命中" } as Record<string,string>)[event.data.state || ""] || event.data.state}{event.data.attempt ? ` · 修复 ${event.data.attempt}` : ""}</span>)}</div>
              {run.events.filter(e => e.event === "code").map((event, j) => <details className="code-block" key={`c${j}`}><summary><code>PYTHON</code>{event.data.attempt ? `修复版本 ${event.data.attempt}` : "查看执行代码"}<ChevronRight size={14}/></summary><pre>{event.data.code}</pre>{event.data.diff && <pre className="diff">{event.data.diff}</pre>}</details>)}
              {run.events.some(e => e.event === "stdout") && <details className="terminal" open><summary>● 运行日志</summary><pre>{run.events.filter(e => e.event === "stdout").map(e => `[${e.data.stream}] ${e.data.text}`).join("")}</pre></details>}
              {run.events.filter(e => e.event === "error").map((event,j) => <div className={event.data.recoverable ? "repair-note" : "error-text"} key={`e${j}`}>{event.data.recoverable ? "正在自动修复：" : "分析失败："}{event.data.message}</div>)}
              {run.events.some(e => e.event === "insight") && <div className="insight"><h4>分析洞见</h4><p>{run.events.filter(e => e.event === "insight").map(e => e.data.text).join("")}</p></div>}
              <div className="run-status">{run.state === "running" ? <><LoaderCircle size={13} className="spin"/> 正在计算与验证…</> : run.state === "completed" ? <><Check size={13}/> 分析完成</> : run.state === "cancelled" ? "已停止分析" : "分析未完成"}</div>
            </div></div></article>)}<div ref={bottom}/>
          </div>
          <div className="composer-wrap">{error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="关闭错误"><X size={14}/></button></div>}<div className="composer"><textarea aria-label="分析问题" placeholder={dataset ? "想从这份数据中了解什么？" : "先上传数据，再开始提问…"} value={question} maxLength={4000} disabled={!dataset || busy} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void analyze(); } }}/><div className="composer-bottom"><span>{dataset ? <><Database size={12}/> {dataset.filename}</> : "支持中文提问"}</span>{busy ? <button className="send-button" aria-label="停止分析" onClick={() => controller.current?.abort()}><Square size={15}/></button> : <button className="send-button" aria-label="发送分析" disabled={!dataset || !question.trim() || uploading} onClick={() => void analyze()}><ArrowUp size={19}/></button>}</div></div><p className="input-note">Enter 发送 · Shift + Enter 换行 · 结论请结合业务背景判断</p></div>
        </section>
        <div className="right-column"><section className="data-card"><div className="section-heading"><div className="heading-icon"><Database size={17}/><h2>当前数据集</h2></div><span className="tag">{dataset ? `${dataset.column_count} 个字段` : "01 / 上传数据"}</span></div>
          <input ref={fileInput} type="file" accept=".csv,.xlsx,.xls,.parquet" hidden onChange={e => void upload(e.target.files?.[0])}/>
          <button className={`upload-zone ${dragging ? "dragging" : ""} ${dataset ? "compact" : ""}`} disabled={busy || uploading} onClick={() => fileInput.current?.click()} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); void upload(e.dataTransfer.files[0]); }}>
            {uploading ? <LoaderCircle className="spin" size={25}/> : dataset ? <FileSpreadsheet size={24}/> : <UploadCloud size={28} strokeWidth={1.4}/>}
            <div><strong>{uploading ? "正在解析与提取概要…" : dataset ? dataset.filename : "拖入数据文件，或点击上传"}</strong><span>{dataset ? `${dataset.row_count.toLocaleString()} 行 · ${dataset.column_count} 列 · ${(dataset.size_bytes / 1024).toFixed(1)} KB` : "CSV / Excel / Parquet · 最大 20 MB"}</span></div>{dataset && <span className="replace-text">更换</span>}
          </button>{dataset && <Schema dataset={dataset}/>}</section>
          <Chart option={chart} token={token}/>
          <div className="workspace-footnote"><ShieldCheck size={14}/><span>独立执行环境</span><i/>最多 3 次自动纠错<i/>完整代码可追溯</div>
        </div>
      </div>
    </main>
    {settings && <div className="modal-overlay" onClick={() => setSettings(false)}><section className="settings-dialog" role="dialog" aria-modal="true" aria-label="连接设置" onClick={e => e.stopPropagation()}><button className="close-dialog" aria-label="关闭设置" onClick={() => setSettings(false)}><X size={18}/></button><Settings2 size={24}/><h2>连接设置</h2><p>模型密钥仅在后端 .env 中配置：LLM_API_KEY、LLM_MODEL、LLM_BASE_URL。</p><label>工作台访问令牌（可选）<input type="password" value={token} onChange={e => setToken(e.target.value)} placeholder="服务端 API_TOKEN" autoComplete="off"/></label><small>仅保存在当前页面内存中，刷新后需重新输入。</small><div className="connection-summary">模型：{status?.model || "尚未配置"}<br/>Redis：{status?.redis_available ? "已连接" : "未连接，会话和缓存暂不可用"}</div><button className="primary-button" onClick={() => setSettings(false)}>完成</button></section></div>}
  </div>;
}
