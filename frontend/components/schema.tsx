"use client";
import { useState } from "react";
import { ui, type Language } from "@/lib/i18n";
import type { Dataset } from "@/lib/types";

export default function Schema({ dataset, language }: { dataset: Dataset; language: Language }) {
  const t = ui[language];
  const [scroll, setScroll] = useState(0);
  const rowHeight = 44, height = 220;
  const start = Math.max(0, Math.floor(scroll / rowHeight) - 2);
  const columns = dataset.columns.slice(start, start + Math.ceil(height / rowHeight) + 4);
  return <div className="schema">
    <div role="table" aria-label={t.schemaLabel} aria-rowcount={dataset.columns.length + 1} aria-colcount={3}>
      <div className="schema-head" role="row" aria-rowindex={1}><span role="columnheader">{t.field}</span><span role="columnheader">{t.type}</span><span role="columnheader">{t.missing}</span></div>
      <div className="schema-scroll" style={{ maxHeight: height }} onScroll={e => setScroll(e.currentTarget.scrollTop)} role="rowgroup">
        <div role="presentation" style={{ height: dataset.columns.length * rowHeight, position: "relative" }}>
          {columns.map((column, index) => <div className="schema-row" role="row" aria-rowindex={start + index + 2} key={column.name} style={{ position: "absolute", top: (start + index) * rowHeight, height: rowHeight, width: "100%" }}>
            <span role="cell" title={column.name}>{column.name}</span><code role="cell">{column.dtype}</code><span role="cell" className={column.missing_count ? "missing" : "muted"}>{(column.missing_fraction * 100).toFixed(0)}%</span>
          </div>)}
        </div>
      </div>
    </div>
    <details className="preview"><summary>{t.sampleRows}</summary><div className="table-scroll"><table><thead><tr>{dataset.columns.map(c => <th key={c.name}>{c.name}</th>)}</tr></thead><tbody>{dataset.sample_rows.map((row, i) => <tr key={i}>{dataset.columns.map(c => <td key={c.name}>{row[c.name] == null ? "—" : String(row[c.name])}</td>)}</tr>)}</tbody></table></div></details>
  </div>;
}
