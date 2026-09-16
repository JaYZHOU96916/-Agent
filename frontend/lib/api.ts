import { localizeSystemMessage, ui, type Language } from "./i18n";

export function apiHeaders(token: string, json = false): HeadersInit {
  return { ...(token ? { "X-API-Key": token } : {}), ...(json ? { "Content-Type": "application/json" } : {}) };
}
export async function responseError(response: Response, language: Language = "zh") {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? localizeSystemMessage(body.detail, language) : ui[language].requestFailed(response.status);
  } catch { return ui[language].connectionFailed(response.status); }
}
export function download(name: string, body: string, type: string) {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const link = document.createElement("a"); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
