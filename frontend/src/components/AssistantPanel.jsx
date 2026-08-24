import { Bot, Send, ShieldAlert, User } from "lucide-react";
import { useState } from "react";

import { Assistant } from "../api/client";

export default function AssistantPanel({ applicationId, compact = false }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: applicationId
        ? "Ask me about this application's score, validation flags, fraud signals, or audit history."
        : "Select an application, or ask a general question about how scoring and review works.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send() {
    const question = input.trim();
    if (!question || loading) return;
    setMessages((m) => [...m, { role: "user", text: question }]);
    setInput("");
    setLoading(true);
    try {
      const res = await Assistant.ask(question, applicationId);
      setMessages((m) => [...m, { role: "assistant", text: res.answer, note: res.guardrail_note }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", text: "The assistant is unavailable right now.", error: true }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`panel flex flex-col ${compact ? "h-[420px]" : "h-[560px]"}`}>
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Bot size={16} className="text-gold" />
        <span className="text-sm font-medium text-ink_text-primary">Reviewer Assistant</span>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "flex-row-reverse text-right" : ""}`}>
            <div
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                m.role === "user" ? "bg-teal/20 text-teal-soft" : "bg-gold/15 text-gold"
              }`}
            >
              {m.role === "user" ? <User size={12} /> : <Bot size={12} />}
            </div>
            <div className={`max-w-[85%] ${m.role === "user" ? "text-right" : ""}`}>
              <p className="whitespace-pre-line rounded-lg bg-surface-raised px-3 py-2 text-sm text-ink_text-primary">
                {m.text}
              </p>
              {m.note && (
                <p className="mt-1 flex items-center gap-1 text-[10px] text-ink_text-faint">
                  <ShieldAlert size={10} /> {m.note}
                </p>
              )}
            </div>
          </div>
        ))}
        {loading && <p className="text-xs text-ink_text-faint">Thinking…</p>}
      </div>

      <div className="flex items-center gap-2 border-t border-border p-3">
        <input
          className="input"
          placeholder="Ask a question..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button className="btn-primary px-3" onClick={send} disabled={loading}>
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}
