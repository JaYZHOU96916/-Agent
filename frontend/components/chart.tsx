"use client";
import dynamic from "next/dynamic";
import { Component, useEffect, useMemo, useState, type ReactNode } from "react";
import { BarChart3, LineChart, PieChart, Download, Image as ImageIcon, FileJson, ChartNoAxesCombined } from "lucide-react";
import { apiHeaders, download, responseError } from "@/lib/api";
import { chartPalette, chartTextColor } from "@/lib/theme";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false, loading: () => <div className="chart-loading">正在加载图表…</div> });
type Series = { type: string; name?: string; data: unknown[] };
class ChartGuard extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <div className="chart-loading">交互图表暂不可用，请点击上方图片按钮生成静态 PNG。</div> : this.props.children; }
}
export default function Chart({ option, token }: { option: Record<string, unknown> | null; token: string }) {
  const [type, setType] = useState("");
  const [image, setImage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setType(""); setImage(""); setError(""); }, [option]);
  useEffect(() => () => { if (image) URL.revokeObjectURL(image); }, [image]);
  const display = useMemo(() => {
    if (!option) return {};
    const result = JSON.parse(JSON.stringify(option));
    const series: Series[] = result.series || [];
    const originalPie = series[0]?.type === "pie";
    if (type === "pie" && !originalPie) {
      const categories = result.xAxis?.data || [];
      result.series = series.slice(0, 1).map(s => ({ ...s, type: "pie", radius: ["36%", "65%"], data: s.data.map((value, i) => ({ name: String(categories[i] ?? i), value })) }));
      delete result.xAxis; delete result.yAxis; delete result.dataZoom;
    } else if (type && originalPie && type !== "pie") {
      const data = series[0].data as {name: string; value: number}[];
      result.xAxis = { type: "category", data: data.map(d => d.name) }; result.yAxis = { type: "value" };
      result.series = [{ ...series[0], type, data: data.map(d => d.value) }];
    } else if (type) result.series = series.map(s => ({ ...s, type }));
    return { ...result, backgroundColor: "transparent", color: chartPalette,
      grid: { left: 42, right: 28, top: 62, bottom: 55, containLabel: true },
      tooltip: { trigger: type === "pie" || (!type && originalPie) ? "item" : "axis", renderMode: "richText" },
      textStyle: { fontFamily: "system-ui, sans-serif", color: chartTextColor, fontSize: 12 } };
  }, [option, type]);
  async function staticImage() {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/v1/charts/png", { method: "POST", headers: apiHeaders(token, true), body: JSON.stringify({ option: display }) });
      if (!response.ok) throw new Error(await responseError(response));
      setImage(URL.createObjectURL(await response.blob()));
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  function csv() {
    if (!option) return;
    const series = display.series as Series[];
    const pie = series[0]?.type === "pie";
    const categories = (display.xAxis as { data?: unknown[] })?.data ||
      (pie ? series[0].data.map(item => (item as { name?: string }).name ?? "") : []);
    const escape = (value: unknown) => {
      let text = typeof value === "object" ? JSON.stringify(value) : String(value ?? "");
      if (typeof value !== "number" && /^[=+\-@\t\r]/.test(text)) text = "'" + text;
      return '"' + text.replaceAll('"', '""') + '"';
    };
    const rows = [["category", ...series.map((s, i) => s.name || `series_${i + 1}`)], ...Array.from({ length: Math.max(...series.map(s => s.data.length)) }, (_, i) =>
      [categories[i] ?? i, ...series.map(s => pie ? (s.data[i] as { value?: unknown })?.value : s.data[i])])];
    download("analysis-chart.csv", "\ufeff" + rows.map(row => row.map(escape).join(",")).join("\r\n"), "text/csv;charset=utf-8");
  }
  return <section className="chart-card">
    <div className="section-heading"><div><h2>可视化结果</h2><p>切换视图，检查数据的不同侧面</p></div><span className="tag">{option ? "已生成" : "待生成"}</span></div>
    <div className="chart-tools"><div className="segmented">{[["bar", BarChart3, "柱状图"], ["line", LineChart, "折线图"], ["pie", PieChart, "饼图"]].map(([value, Icon, label]) => {
      const Component = Icon as typeof BarChart3;
      const unsupported = (option?.series as Series[] | undefined)?.[0]?.type === "scatter";
      return <button key={String(value)} aria-label={String(label)} title={String(label)} className={type === value ? "active" : ""} disabled={!option || unsupported} onClick={() => { setType(String(value)); setImage(""); }}><Component size={16} /></button>;
    })}</div><div className="export-tools"><button disabled={!option} onClick={csv} title="导出图表数据 CSV" aria-label="导出 CSV"><Download size={16} /> CSV</button><button disabled={!option} onClick={() => download("chart-option.json", JSON.stringify(option, null, 2), "application/json")} aria-label="导出 JSON"><FileJson size={16}/></button><button disabled={!option || busy} onClick={staticImage} title="生成静态 PNG" aria-label="静态 PNG"><ImageIcon size={16}/></button></div></div>
    <div className="chart-stage" data-testid="chart-stage" role="region" aria-label="分析图表">
      {image ? <div className="static-chart"><img src={image} width={1200} height={680} alt="分析图表静态降级图片"/><a href={image} download="analysis.png">下载 PNG</a><button onClick={() => setImage("")}>返回交互图表</button></div> : option ? <ChartGuard key={JSON.stringify(display)}><ReactECharts option={display} notMerge style={{ height: "100%", minHeight: 350 }} opts={{ renderer: "canvas" }} /></ChartGuard> : <div className="chart-empty"><div className="chart-empty-content"><div className="chart-orbit"><ChartNoAxesCombined size={34} strokeWidth={1.4}/></div><h3>图表将在这里生成</h3><p>完成一次分析后，可切换图表类型、缩放查看并导出结果。</p></div></div>}
    </div>
    {busy && <p className="chart-note">正在生成静态图片…</p>}{error && <p role="alert" className="error-text">{error}</p>}
    <footer className="chart-footer"><span><i/> {option ? "基于沙箱计算结果" : "等待分析结果"}</span><span>滚轮缩放 · 悬停查看数值</span></footer>
  </section>;
}
