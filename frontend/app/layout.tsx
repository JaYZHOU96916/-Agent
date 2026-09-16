import type { Metadata, Viewport } from "next";
import { ui } from "@/lib/i18n";
import { getServerLanguage } from "@/lib/server-language";
import { workspaceCanvasColor } from "@/lib/theme";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = ui[await getServerLanguage()];
  return { title: t.documentTitle, description: t.description };
}
export const viewport: Viewport = { themeColor: workspaceCanvasColor };
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const language = await getServerLanguage();
  return <html lang={language === "zh" ? "zh-CN" : "en"}><body>{children}</body></html>;
}
