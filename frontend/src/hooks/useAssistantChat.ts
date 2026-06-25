import { useCallback, useRef, useState } from "react"
import type { ChatMessage } from "../types"
import { streamChat } from "../api/chat"

let idCounter = 0
const nextId = () => `${Date.now()}-${++idCounter}`

/**
 * 工具君对话状态机。状态提升到 App 调用，保证关闭抽屉不丢历史。
 */
export function useAssistantChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isStreaming) return

      const userMsg: ChatMessage = { id: nextId(), role: "user", content: trimmed }
      const assistantId = nextId()
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        streaming: true,
      }
      // 发给后端的历史 = 当前历史 + 本轮用户消息（不含空占位）
      const history = [...messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }))

      setMessages((prev) => [...prev, userMsg, assistantMsg])
      setIsStreaming(true)

      const controller = new AbortController()
      abortRef.current = controller

      await streamChat({
        messages: history,
        signal: controller.signal,
        onDelta: (delta) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + delta } : m
            )
          )
        },
        onDone: () => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
          )
          setIsStreaming(false)
          abortRef.current = null
        },
        onError: (msg) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, streaming: false, error: true, content: m.content || `⚠️ ${msg}` }
                : m
            )
          )
          setIsStreaming(false)
          abortRef.current = null
        },
      })
    },
    [messages, isStreaming]
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const clear = useCallback(() => {
    abortRef.current?.abort()
    setMessages([])
    setIsStreaming(false)
  }, [])

  return { messages, isStreaming, send, stop, clear }
}

export type UseAssistantChat = ReturnType<typeof useAssistantChat>
