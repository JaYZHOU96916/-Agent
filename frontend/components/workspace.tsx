"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, ArrowUpRight, Check, ChevronRight, CircleHelp, Database, FileSpreadsheet, Layers3, LoaderCircle, Plus, Settings2, ShieldCheck, Sparkles, Square, UploadCloud, X } from "lucide-react";
import Chart from "@/components/chart";
import Schema from "@/components/schema";
import { apiHeaders, responseError } from "@/lib/api";
import { languageCookieName, localizeSystemMessage, ui, type Language } from "@/lib/i18n";
import { consumeSSE } from "@/lib/sse";
import type { Dataset, StreamEvent } from "@/lib/types";

type Run = { question: string; events: StreamEvent[]; state: string; session?: string };
export default function Workspace({ initialLanguage }: { initialLanguage: Language }) {
  const [language, setLanguage] = useState<Language>(initialLanguage);
  const t = ui[language];
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
  const settingsClose = useRef<HTMLButtonElement>(null);
  const settingsDialog = useRef<HTMLElement>(null);
  const controller = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    document.title = t.documentTitle;
    document.querySelector('meta[name="description"]')?.setAttribute("content", t.description);
  }, [language, t.documentTitle, t.description]);
  function changeLanguage(next: Language) {
    setLanguage(next);
    document.cookie = `${languageCookieName}=${next}; Path=/; Max-Age=31536000; SameSite=Lax`;
  }
  useEffect(() => { fetch("/api/v1/system", { headers: apiHeaders(token) }).then(async r => {
    if (r.status === 401) { setSettings(true); return; }
    if (r.ok) setStatus(await r.json());
  }).catch(() => setStatus(null)); }, [token]);
  useEffect(() => { if (runs.length) bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [runs]);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!settings) return;
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    settingsClose.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setSettings(false); return; }
      if (event.key !== "Tab") return;
      const focusable = settingsDialog.current?.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled)");
      if (!focusable?.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => { window.removeEventListener("keydown", onKeyDown); returnFocus?.focus(); };
  }, [settings]);
  async function upload(file?: File) {
    if (!file || busy || uploading) return;
    if (!/\.(csv|xlsx|xls|parquet)$/i.test(file.name)) { setError(t.unsupportedFile); return; }
    if (file.size > 20 * 1024 * 1024) { setError(t.fileTooLarge); return; }
    setUploading(true); setError("");
    try {
      const data = new FormData(); data.append("file", file);
      const response = await fetch("/api/v1/datasets", { method: "POST", headers: apiHeaders(token), body: data });
      if (!response.ok) throw new Error(await responseError(response, language));
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
      if (!response.ok) throw new Error(await responseError(response, language));
      await consumeSSE(response, event => {
        if (event.event === "chart" && event.data.option) setChart(event.data.option);
        update(run => ({ ...run, events: [...run.events, event], session: event.data.session_id || run.session,
          state: event.event === "done" ? event.data.status || "completed" : run.state }));
      }, language);
    } catch (error) {
      const stopped = (error as Error).name === "AbortError";
      update(run => ({ ...run, state: stopped ? "cancelled" : "failed" }));
      if (!stopped) setError((error as Error).message);
    } finally { setBusy(false); controller.current = null; }
  }
  return <div className="workspace">
    <a className="skip-link" href="#workspace-main">{t.skipLink}</a>
    <aside className="sidebar">
      <a className="brand" href="/" aria-label={t.home}><span className="brand-mark"><Layers3 size={22}/></span>ANZ</a>
      <div className="workspace-label">{t.workspaceLabel} <span>{t.local}</span></div>
      <button className="new-button" disabled={busy} onClick={() => { setRuns([]); setChart(null); setError(""); }}><Plus size={17}/> {t.newAnalysis} <span>↗</span></button>
      <div className="sidebar-section"><span className="eyebrow">{t.workspace}</span><div className="nav-active"><Sparkles size={17}/> {t.analysisWorkspace}</div></div>
      <div className="sidebar-section"><div className="sidebar-title"><span>{t.dataSources}</span><button onClick={() => fileInput.current?.click()} disabled={busy || uploading} aria-label={t.addDataSource}><Plus size={15}/></button></div>
        {dataset ? <div className="dataset-link"><FileSpreadsheet size={18}/><span title={dataset.filename}>{dataset.filename}</span><i/></div> : <p className="sidebar-muted">{t.dataSourceHint}</p>}
      </div>
      <div className="privacy-note"><ShieldCheck size={20}/><h4>{t.privacyTitle}</h4><p>{t.privacyBody}</p></div>
      <div className="sidebar-bottom"><button onClick={() => setSettings(true)}><Settings2 size={17}/> {t.settings}</button><a href="https://github.com/JaYZHOU96916/-Agent" target="_blank" rel="noreferrer"><CircleHelp size={17}/> {t.documentation} <ArrowUpRight size={14}/></a><div className="profile"><span>Z</span><div>{t.localWorkspace}<small>{t.singleUser}</small></div></div></div>
    </aside>
    <main className="main" id="workspace-main" tabIndex={-1}>
      <header className="topbar"><div>{t.workspace} <ChevronRight size={14}/><strong>{t.analysisWorkspace}</strong></div><div className="topbar-actions"><div className="service-status" aria-live="polite"><i className={status?.model_configured ? "online" : ""}/>{status?.model_configured ? t.modelConnected : t.modelWaiting}<span className="divider"/><span className="execution-label">{t.isolatedExecution}</span></div><button className="topbar-settings" onClick={() => setSettings(true)} aria-label={t.settings}><Settings2 size={18}/></button></div></header>
      <div className="page-heading"><div><h1>{t.heroTitle}</h1><p>{t.heroBody}</p></div><div className="flow-hint" aria-label={t.analysisFlow}><span>{t.dataset}</span><ChevronRight size={15}/><span>{t.compute}</span><ChevronRight size={15}/><span>{t.insight}</span></div></div>
      <div className="work-grid">
        <section className="conversation-card">
          <div className="section-heading"><div className="heading-icon"><Sparkles size={18}/><h2>{t.conversation}</h2></div><span className={`small-status ${dataset ? "" : "is-idle"}`} aria-live="polite">{busy ? t.analyzing : dataset ? t.readyToAsk : t.waitingForDataset}</span></div>
          <div className="conversation-body">
            {!runs.length && <div className="intro"><span className="assistant-avatar"><Sparkles size={21}/></span><h3>{dataset ? t.introWithDataset : t.introWithoutDataset}</h3><p>{dataset ? t.introWithDatasetBody : t.introWithoutDatasetBody}</p><div className="starter-label">{t.exampleQuestions}</div><div className="starter-prompts">{t.suggestions.map((text, i) => <button key={text} disabled={!dataset || busy} onClick={() => setQuestion(text)}><span>{String(i+1).padStart(2,"0")}</span>{text}<ArrowUpRight size={15}/></button>)}</div></div>}
            {runs.map((run, i) => <article className="run" key={i}><div className="user-message">{run.question}</div><div className="assistant-run"><span className="assistant-avatar"><Sparkles size={16}/></span><div className="run-content">
              {run.events.filter(e => e.event === "plan").map((event, j) => <div className="plan" key={`p${j}`}><h4>{t.plan}</h4>{event.data.steps?.map((step, k) => <div key={k}><span>{k+1}</span>{step}</div>)}</div>)}
              <div className="step-pills">{run.events.filter(e => e.event === "status" && e.data.state !== "started").map((event, j) => <span key={j}>{({ CodeGenerator: t.codeGenerator, SandboxExecutor: t.sandboxExecutor, ChartFormatter: t.chartFormatter, cache_hit: t.cacheHit } as Record<string,string>)[event.data.state || ""] || event.data.state}{event.data.attempt ? t.repairAttempt(event.data.attempt) : ""}</span>)}</div>
              {run.events.filter(e => e.event === "code").map((event, j) => <details className="code-block" key={`c${j}`}><summary><code>PYTHON</code>{event.data.attempt ? t.repairVersion(event.data.attempt) : t.viewCode}<ChevronRight size={14}/></summary><pre>{event.data.code}</pre>{event.data.diff && <pre className="diff">{event.data.diff}</pre>}</details>)}
              {run.events.some(e => e.event === "stdout") && <details className="terminal" open><summary>{t.terminal}</summary><pre>{run.events.filter(e => e.event === "stdout").map(e => `[${e.data.stream}] ${e.data.text}`).join("")}</pre></details>}
              {run.events.filter(e => e.event === "error").map((event,j) => <div className={event.data.recoverable ? "repair-note" : "error-text"} key={`e${j}`}>{event.data.recoverable ? t.repairing : t.analysisFailed}{localizeSystemMessage(event.data.message || "", language)}</div>)}
              {run.events.some(e => e.event === "insight") && <div className="insight"><h4>{t.analysisInsight}</h4><p>{run.events.filter(e => e.event === "insight").map(e => e.data.text).join("")}</p></div>}
              <div className="run-status">{run.state === "running" ? <><LoaderCircle size={13} className="spin"/> {t.calculating}</> : run.state === "completed" ? <><Check size={13}/> {t.completed}</> : run.state === "cancelled" ? t.cancelled : t.incomplete}</div>
            </div></div></article>)}<div ref={bottom}/>
          </div>
          <div className="composer-wrap">{error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label={t.closeError}><X size={14}/></button></div>}<div className="composer"><textarea aria-label={t.question} name="analysis-question" autoComplete="off" placeholder={dataset ? t.questionPlaceholder : t.uploadFirst} value={question} maxLength={4000} disabled={!dataset || busy} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void analyze(); } }}/><div className="composer-bottom"><span>{dataset ? <><Database size={12}/> {dataset.filename}</> : t.supportsChinese}</span>{busy ? <button className="send-button" aria-label={t.stopAnalysis} onClick={() => controller.current?.abort()}><Square size={15}/></button> : <button className="send-button" aria-label={t.sendAnalysis} disabled={!dataset || !question.trim() || uploading} onClick={() => void analyze()}><ArrowUp size={19}/></button>}</div></div><p className="input-note">{t.inputNote}</p></div>
        </section>
        <div className="right-column"><section className="data-card"><div className="section-heading"><div className="heading-icon"><Database size={17}/><h2>{t.currentDataset}</h2></div><span className="tag">{dataset ? t.fieldCount(dataset.column_count) : t.uploadStep}</span></div>
          <input ref={fileInput} type="file" accept=".csv,.xlsx,.xls,.parquet" hidden onChange={e => void upload(e.target.files?.[0])}/>
          <button className={`upload-zone ${dragging ? "dragging" : ""} ${dataset ? "compact" : ""}`} disabled={busy || uploading} onClick={() => fileInput.current?.click()} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); void upload(e.dataTransfer.files[0]); }}>
            {uploading ? <LoaderCircle className="spin" size={25}/> : dataset ? <FileSpreadsheet size={24}/> : <UploadCloud size={28} strokeWidth={1.4}/>}
            <div><strong>{uploading ? t.parsing : dataset ? dataset.filename : t.dropFile}</strong><span>{dataset ? t.datasetSize(dataset.row_count.toLocaleString(language === "zh" ? "zh-CN" : "en-US"), dataset.column_count, (dataset.size_bytes / 1024).toFixed(1)) : t.uploadLimit}</span></div>{dataset && <span className="replace-text">{t.replace}</span>}
          </button>{dataset && <Schema dataset={dataset} language={language}/>}</section>
          <Chart option={chart} token={token} language={language}/>
      <div className="workspace-footnote"><ShieldCheck size={14}/><span>{t.isolatedEnvironment}</span><i/>{t.maxRepairs}<i/>{t.traceableCode}</div>
        </div>
      </div>
    </main>
    {settings && <div className="modal-overlay">
      <button className="modal-dismiss" aria-label={t.closeSettings} onClick={() => setSettings(false)}/>
      <section ref={settingsDialog} className="settings-dialog" role="dialog" aria-modal="true" aria-label={t.settings}>
        <button ref={settingsClose} className="close-dialog" aria-label={t.closeSettings} onClick={() => setSettings(false)}><X size={18}/></button>
        <Settings2 size={24}/><h2>{t.settings}</h2><p>{t.modelSecretHint}</p>
        <fieldset className="language-settings">
          <legend>{t.language}</legend>
          <div className="language-options">
            <button type="button" lang="zh-CN" aria-pressed={language === "zh"} onClick={() => changeLanguage("zh")}>中文</button>
            <button type="button" lang="en" aria-pressed={language === "en"} onClick={() => changeLanguage("en")}>English</button>
          </div>
          <small>{t.languageHint}</small>
        </fieldset>
        <label htmlFor="workspace-token">{t.workspaceToken}</label>
        <input id="workspace-token" name="workspace-token" type="password" value={token} onChange={e => setToken(e.target.value)} placeholder={t.tokenPlaceholder} autoComplete="off" spellCheck={false}/>
        <small>{t.tokenHint}</small>
        <div className="connection-summary">{t.model}: {status?.model || t.notConfigured}<br/>{t.redis}: {status?.redis_available ? t.redisConnected : t.redisDisconnected}</div>
        <button className="primary-button" onClick={() => setSettings(false)}>{t.done}</button>
      </section>
    </div>}
  </div>;
}
