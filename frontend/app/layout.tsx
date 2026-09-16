import type { Metadata, Viewport } from "next";
import { workspaceCanvasColor } from "@/lib/theme";
import "./globals.css";

export const metadata: Metadata = { title: "Forma · 数据分析工作台", description: "从数据到洞见，可追溯的 AI 分析工作台" };
export const viewport: Viewport = { themeColor: workspaceCanvasColor };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
