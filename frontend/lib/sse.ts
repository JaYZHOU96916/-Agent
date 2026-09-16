import type { StreamEvent } from "./types";

/** Decode arbitrary UTF-8/chunk boundaries, comments and CRLF without losing tail frames. */
export async function consumeSSE(response: Response, onEvent: (event: StreamEvent) => void) {
  if (!response.body) throw new Error("服务端未返回数据流。");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;
  function parse(frame: string) {
    let event = "message";
    const data: string[] = [];
    for (const line of frame.replace(/\r/g, "").split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (data.length) {
      const parsed = JSON.parse(data.join("\n"));
      if (!parsed || typeof parsed !== "object") throw new Error("无效的 SSE 数据。");
      onEvent({ event, data: parsed });
      if (event === "done") finished = true;
    }
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary: RegExpMatchArray | null;
      while ((boundary = buffer.match(/\r?\n\r?\n/))) {
        const index = boundary.index!;
        parse(buffer.slice(0, index));
        buffer = buffer.slice(index + boundary[0].length);
      }
      if (buffer.length > 1_000_000) throw new Error("流式响应超出大小限制。");
      if (done) break;
    }
    if (buffer.trim()) parse(buffer);
    if (!finished) throw new Error("连接已中断，分析尚未完成。请重试。");
  } finally { reader.releaseLock(); }
}
