import type { ChatMessage } from "../types"

// dev 下直连后端 8000，绕过 vite dev 代理对 SSE 的缓冲；生产构建走同源 /api。
// 用页面主机名（而非写死 localhost），保证局域网其他设备访问 5174 时也能连到主机后端 8000。
const API_BASE = import.meta.env.DEV
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : ""

interface StreamChatOptions {
  messages: Pick<ChatMessage, "role" | "content">[]
  onDelta: (content: string) => void
  onDone: () => void
  onError: (message: string) => void
  signal?: AbortSignal
}

/**
 * 调用 /api/chat SSE 流式接口，逐帧回调。
 * 与 api/client.ts 的 JSON 请求不同，这里直接用 fetch + ReadableStream 解析 SSE。
 */
export async function streamChat(opts: StreamChatOptions): Promise<void> {
  const { messages, onDelta, onDone, onError, signal } = opts

  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: messages.map((m) => ({ role: m.role, content: m.content })),
      }),
      signal,
    })
  } catch (e) {
    if ((e as Error)?.name === "AbortError") {
      onDone()
      return
    }
    onError((e as Error)?.message || "请求失败")
    return
  }

  if (!res.ok || !res.body) {
    const txt = await res.text().catch(() => "")
    onError(txt || `${res.status} ${res.statusText}`)
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder("utf-8")
  let buffer = ""

  const handleFrame = (frame: string): boolean => {
    // 一帧可能多行，取 data: 开头的那行
    const line = frame
      .split("\n")
      .map((l) => l.trim())
      .find((l) => l.startsWith("data:"))
    if (!line) return false
    const json = line.slice(5).trim()
    if (!json) return false
    try {
      const evt = JSON.parse(json)
      if (evt.type === "delta" && evt.content) {
        onDelta(evt.content)
        return false
      }
      if (evt.type === "done") {
        onDone()
        return true
      }
      if (evt.type === "error") {
        onError(evt.message || "生成失败")
        return true
      }
    } catch {
      /* 忽略畸形帧 */
    }
    return false
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // SSE 帧以空行分隔
      let idx: number
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        if (handleFrame(frame)) return
      }
    }
    // 流自然结束（未见显式 done 帧）
    onDone()
  } catch (e) {
    if ((e as Error)?.name === "AbortError") onDone()
    else onError((e as Error)?.message || "连接中断")
  }
}
