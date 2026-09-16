export function apiHeaders(token: string, json = false): HeadersInit {
  return { ...(token ? { "X-API-Key": token } : {}), ...(json ? { "Content-Type": "application/json" } : {}) };
}
export async function responseError(response: Response) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : `请求失败 (${response.status})`;
  } catch { return `服务连接失败 (${response.status})`; }
}
export function download(name: string, body: string, type: string) {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const link = document.createElement("a"); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
