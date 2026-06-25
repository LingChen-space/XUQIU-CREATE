import { useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Bot, Sparkles, Send, Square, Trash2, X, Wand2, ArrowRight } from "lucide-react"
import type { ChatMessage } from "../types"
import type { UseAssistantChat } from "../hooks/useAssistantChat"

interface Props {
  chat: UseAssistantChat
  onClose: () => void
}

const WELCOME_PILLS = [
  "今日有哪些高潜力工具需求？",
  "总结今日需求挖掘情况",
  "哪些游戏最值得做工具？",
  "今天哪类工具需求最多？",
]

interface CmdTemplate {
  label: string
  prompt: string
}

const COMMAND_TEMPLATES: CmdTemplate[] = [
  { label: "全局需求大盘", prompt: "总结今日需求大盘，给出 S/A 级需求和整体趋势" },
  { label: "某游戏需求", prompt: "分析【某游戏】的需求情况、依据和工具可行性" },
  { label: "某工具类型", prompt: "分析【某工具类型】类需求的情况和高分代表" },
  { label: "多游戏对比", prompt: "对比【游戏A】和【游戏B】的需求潜力" },
  { label: "需求信号", prompt: "【某游戏】的需求信号分分别是多少，说明什么" },
]

const WELCOME_TEXT =
  "你好，我是好游快爆工具君 👋 拓展组的需求分析助手。我可以帮你解读每日的工具需求挖掘结果——哪些游戏值得做工具、某款游戏的需求依据、工具类型分布等。试试问我："

export default function AssistantPanel({ chat, onClose }: Props) {
  const { messages, isStreaming, send, stop, clear } = chat
  const [input, setInput] = useState("")
  const [menuOpen, setMenuOpen] = useState(false)
  const taRef = useRef<HTMLTextAreaElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  // Esc 关闭
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [onClose])

  // 自动滚动到底
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" })
  }, [messages])

  // textarea 自适应高度
  useEffect(() => {
    const ta = taRef.current
    if (!ta) return
    ta.style.height = "auto"
    ta.style.height = Math.min(ta.scrollHeight, 140) + "px"
  }, [input])

  // 点击指令菜单外部关闭
  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [menuOpen])

  const handleSend = () => {
    const text = input.trim()
    if (!text || isStreaming) return
    send(text)
    setInput("")
    if (taRef.current) taRef.current.style.height = "auto"
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const pickTemplate = (prompt: string) => {
    setInput(prompt)
    setMenuOpen(false)
    setTimeout(() => {
      taRef.current?.focus()
      // 把光标移到末尾
      const len = prompt.length
      taRef.current?.setSelectionRange(len, len)
    }, 0)
  }

  const showWelcome = messages.length === 0

  return (
    <>
      <div className="slideover-overlay" onClick={onClose} />
      <div className="slideover-panel chat-panel">
        {/* Header */}
        <div className="chat-header">
          <div className="chat-avatar">
            <Bot size={20} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="chat-title">
              好游快爆工具君
              <Sparkles size={13} style={{ color: "var(--amber)", marginLeft: 4 }} />
            </div>
            <div className="chat-subtitle">每日需求分析助手</div>
          </div>
          <button
            className="btn btn-ghost btn-sm chat-icon-btn"
            onClick={clear}
            title="清空对话"
            aria-label="清空对话"
          >
            <Trash2 size={16} />
          </button>
          <button
            className="btn btn-ghost btn-sm chat-icon-btn"
            onClick={onClose}
            title="关闭"
            aria-label="关闭"
          >
            <X size={16} />
          </button>
        </div>

        {/* Messages */}
        <div className="chat-messages">
          {showWelcome ? (
            <div className="msg-row msg-row--assistant">
              <div className="chat-avatar chat-avatar--sm">
                <Bot size={15} />
              </div>
              <div className="msg-col">
                <div className="msg-bubble msg-bubble--assistant">
                  {WELCOME_TEXT}
                </div>
                <div className="welcome-pills">
                  {WELCOME_PILLS.map((q) => (
                    <button
                      key={q}
                      className="welcome-pill"
                      onClick={() => send(q)}
                      disabled={isStreaming}
                    >
                      {q}
                      <ArrowRight size={12} />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map((m) => (
              <MessageRow key={m.id} message={m} />
            ))
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div className="chat-input-bar">
          <div className="command-toolbar" ref={menuRef}>
            <button
              className="btn btn-ghost btn-sm cmd-lib-btn"
              onClick={() => setMenuOpen((v) => !v)}
              title="分析指令库"
            >
              <Wand2 size={15} />
              指令库
            </button>
            {menuOpen && (
              <div className="cmd-menu">
                <div className="cmd-menu-header">快捷指令模板</div>
                {COMMAND_TEMPLATES.map((t) => (
                  <button
                    key={t.label}
                    className="cmd-menu-item"
                    onClick={() => pickTemplate(t.prompt)}
                  >
                    <span>{t.label}</span>
                    <ArrowRight size={12} />
                  </button>
                ))}
              </div>
            )}
          </div>

          <textarea
            ref={taRef}
            className="chat-textarea"
            placeholder="问工具君任何关于今日需求的问题…"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />

          {isStreaming ? (
            <button
              className="btn btn-danger chat-send-btn"
              onClick={stop}
              title="停止生成"
              aria-label="停止生成"
            >
              <Square size={15} />
            </button>
          ) : (
            <button
              className="btn btn-primary chat-send-btn"
              onClick={handleSend}
              disabled={!input.trim()}
              title="发送"
              aria-label="发送"
            >
              <Send size={15} />
            </button>
          )}
        </div>
      </div>
    </>
  )
}

function MessageRow({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="msg-row msg-row--user">
        <div className="msg-bubble msg-bubble--user">{message.content}</div>
      </div>
    )
  }

  const showTyping = message.streaming && !message.content
  return (
    <div className="msg-row msg-row--assistant">
      <div className="chat-avatar chat-avatar--sm">
        <Bot size={15} />
      </div>
      <div className="msg-col">
        <div className={`msg-bubble msg-bubble--assistant${message.error ? " msg-bubble--error" : ""}`}>
          {showTyping ? (
            <span className="chat-typing">
              <span /> <span /> <span />
            </span>
          ) : (
            <div className="chat-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
