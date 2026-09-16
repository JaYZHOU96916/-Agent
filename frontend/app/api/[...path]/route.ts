import { NextRequest } from "next/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const path = (await params).path.join("/");
  if (!/^v1\/(datasets(?:\/[a-f0-9-]+)?|analyses|system|sessions\/[a-f0-9-]+|charts\/png)$/.test(path))
    return Response.json({ detail: "Not found" }, { status: 404 });
  const origin = request.headers.get("origin");
  if (request.method === "POST" && origin && new URL(origin).host !== request.headers.get("host"))
    return Response.json({ detail: "Origin mismatch" }, { status: 403 });
  const headers = new Headers();
  for (const name of ["content-type", "x-api-key"]) {
    const value = request.headers.get(name); if (value) headers.set(name, value);
  }
  try {
    const options: RequestInit & { duplex?: string } = {
      method: request.method, headers, cache: "no-store", signal: request.signal,
      ...(request.method !== "GET" ? { body: request.body, duplex: "half" } : {}),
    };
    const upstream = await fetch(`${process.env.BACKEND_URL || "http://127.0.0.1:8000"}/api/${path}`, options);
    const resultHeaders = new Headers({ "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no" });
    for (const name of ["content-type", "x-session-id"]) {
      const value = upstream.headers.get(name); if (value) resultHeaders.set(name, value);
    }
    return new Response(upstream.body, { status: upstream.status, headers: resultHeaders });
  } catch {
    return Response.json({ detail: "后端服务尚未连接，请启动 FastAPI 服务。" }, { status: 502 });
  }
}
export { proxy as GET, proxy as POST };
