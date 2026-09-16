import { test, expect } from "@playwright/test";
import { consumeSSE } from "../lib/sse";

const dataset = { dataset_id: "11111111-1111-4111-8111-111111111111", filename: "sales.csv", row_count: 6, column_count: 2, size_bytes: 100,
  columns: [{ name: "region", dtype: "object", missing_count: 0, missing_fraction: 0 }, { name: "sales", dtype: "int64", missing_count: 0, missing_fraction: 0 }],
  sample_rows: [{ region: "A", sales: 120 }], warnings: [] };
const events = [
  { event: "plan", data: { steps: ["汇总各区域销售额", "比较差异"] } },
  { event: "code", data: { code: "print('sales')", attempt: 0 } },
  { event: "error", data: { message: "KeyError: sale", recoverable: true, attempt: 0 } },
  { event: "code", data: { code: "print('fixed')", diff: "-sale\n+sales", attempt: 1 } },
  { event: "stdout", data: { text: "计算完成\n", stream: "stdout" } },
  { event: "chart", data: { option: { animation: false, title: { text: "区域销售额" }, xAxis: { type: "category", data: ["A", "B"] }, yAxis: { type: "value" }, series: [{ name: "sales", type: "bar", data: [120, 80] }] } } },
  { event: "insight", data: { text: "A 区域销售额领先。" } },
  { event: "done", data: { status: "completed" } },
];

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/system", route => route.fulfill({ json: { model_configured: true, redis_available: true, model: "Test fixture model" } }));
  await page.route("**/api/v1/datasets", route => route.fulfill({ status: 201, json: dataset }));
});

test("upload, self-repair stream, chart, type switch and CSV export", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/api/v1/analyses", route => route.fulfill({ contentType: "text/event-stream", body: events.map(e => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join("") }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "把数据，变成下一个好决策。" })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({ name: "sales.csv", mimeType: "text/csv", buffer: Buffer.from("region,sales\nA,120") });
  await expect(page.getByText("6 行 · 2 列 · 0.1 KB")).toBeVisible();
  await page.getByLabel("分析问题").fill("分析销售额");
  await page.getByLabel("发送分析").click();
  await expect(page.getByText("A 区域销售额领先。")).toBeVisible();
  await expect(page.getByText("分析完成", { exact: true })).toBeVisible();
  await expect(page.getByText("正在自动修复：KeyError: sale")).toBeVisible();
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.getByLabel("折线图", { exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByLabel("导出 CSV", { exact: true }).click();
  expect((await download).suggestedFilename()).toBe("analysis-chart.csv");
  await page.getByLabel("饼图", { exact: true }).click();
  const pieDownload = page.waitForEvent("download");
  await page.getByLabel("导出 CSV", { exact: true }).click();
  const pie = await pieDownload;
  const fs = await import("node:fs/promises");
  const contents = await fs.readFile(await pie.path(), "utf8");
  expect(contents).toContain('"A","120"');
  expect(errors).toEqual([]);
  await page.screenshot({ path: "test-results/workspace-analysis.png", fullPage: true });
});

test("mobile layout and upload errors", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/v1/datasets", route => route.fulfill({ status: 422, json: { detail: "CSV 列名重复" } }));
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "data.csv", mimeType: "text/csv", buffer: Buffer.from("x,x\n1,2") });
  await expect(page.locator(".error-banner")).toContainText("CSV 列名重复");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByLabel("发送分析")).toBeDisabled();
});

test("empty desktop screenshot", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 980 });
  await page.goto("/");
  await page.screenshot({ path: "test-results/workspace-desktop.png", fullPage: true });
});

test("SSE decoder preserves UTF-8 across byte boundaries and rejects truncated completion", async () => {
  const bytes = new TextEncoder().encode(': heartbeat\r\n\r\nevent: insight\r\ndata: {"text":"中文洞见"}\r\n\r\nevent: done\r\ndata: {"status":"completed"}\r\n\r\n');
  const stream = new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(Uint8Array.of(byte)); controller.close(); } });
  const received: string[] = [];
  await consumeSSE(new Response(stream), event => { if (event.data.text) received.push(event.data.text); });
  expect(received).toEqual(["中文洞见"]);
  await expect(consumeSSE(new Response('event: plan\ndata: {"steps":[]}\n\n'), () => {})).rejects.toThrow("连接已中断");
});
