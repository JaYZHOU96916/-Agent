"use client";
import { useState } from "react";
import type { Dataset } from "@/lib/types";

export default function Schema({ dataset }: { dataset: Dataset }) {
  const [scroll, setScroll] = useState(0);
  const rowHeight = 44, height = 220;
  const start = Math.max(0, Math.floor(scroll / rowHeight) - 2);
  const columns = dataset.columns.slice(start, start + Math.ceil(height / rowHeight) + 4);
  return <div className="schema">
    <div className="schema-head"><span>字段</span><span>类型</span><span>缺失</span></div>
    <div className="schema-scroll" style={{ maxHeight: height }} onScroll={e => setScroll(e.currentTarget.scrollTop)} role="table" aria-label="数据字段概要">
      <div style={{ height: dataset.columns.length * rowHeight, position: "relative" }}>
        {columns.map((column, index) => <div className="schema-row" role="row" key={column.name} style={{ position: "absolute", top: (start + index) * rowHeight, height: rowHeight, width: "100%" }}>
          <span title={column.name}>{column.name}</span><code>{column.dtype}</code><span className={column.missing_count ? "missing" : "muted"}>{(column.missing_fraction * 100).toFixed(0)}%</span>
        </div>)}
      </div>
    </div>
    <details className="preview"><summary>查看前 5 行样例</summary><div className="table-scroll"><table><thead><tr>{dataset.columns.map(c => <th key={c.name}>{c.name}</th>)}</tr></thead><tbody>{dataset.sample_rows.map((row, i) => <tr key={i}>{dataset.columns.map(c => <td key={c.name}>{row[c.name] == null ? "—" : String(row[c.name])}</td>)}</tr>)}</tbody></table></div></details>
  </div>;
}
