/**
 * AI Sidebar / Command Palette
 *
 * Slide-out panel accessible from any project view.
 * Features:
 * - Natural language query input with streaming response
 * - Quick action buttons for common AI operations
 * - Context-aware (knows which trial/CRO you're viewing)
 */

import React, { useCallback, useRef, useState } from "react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  toolCalls?: Array<{ name: string; input: Record<string, unknown> }>;
}

interface QuickAction {
  label: string;
  icon: string;
  query: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  { label: "What's blocking our IND?", icon: "🔍", query: "What's blocking our IND filing?" },
  { label: "Enrollment forecast", icon: "📈", query: "What's our enrollment rate vs. forecast?" },
  { label: "CRO performance", icon: "📊", query: "Which CRO is behind on deliverables?" },
  { label: "Missing TMF docs", icon: "📋", query: "What essential TMF documents are missing?" },
  { label: "Trial status", icon: "📝", query: "Give me a high-level trial status update" },
  { label: "Overdue items", icon: "⚠️", query: "What deliverables and submissions are overdue?" },
];

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-2.5 ${
          isUser ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-900"
        }`}
      >
        <div className="text-sm whitespace-pre-wrap">{message.content}</div>
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 border-t border-gray-200 pt-2">
            <p className="text-xs text-gray-500">Data sources queried:</p>
            {message.toolCalls.map((tc, i) => (
              <span
                key={i}
                className="inline-block text-xs bg-gray-200 text-gray-600 rounded px-1.5 py-0.5 mr-1 mt-1"
              >
                {tc.name.replace("query_", "").replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
        <p className={`text-xs mt-1 ${isUser ? "text-blue-200" : "text-gray-400"}`}>
          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </p>
      </div>
    </div>
  );
}

export default function AISidebar({
  workspaceId,
  isOpen,
  onClose,
  context,
}: {
  workspaceId: string;
  isOpen: boolean;
  onClose: () => void;
  context?: { trialId?: string; croId?: string; page?: string };
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  async function handleSend(query?: string) {
    const question = query || input.trim();
    if (!question || loading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`/api/v1/workspaces/${workspaceId}/ai/query/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (res.ok) {
        const data = await res.json();
        const aiMessage: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.answer,
          timestamp: new Date(),
          toolCalls: data.tool_calls,
        };
        setMessages((prev) => [...prev, aiMessage]);
      } else {
        const aiMessage: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Sorry, I encountered an error. Please check your AI configuration and try again.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiMessage]);
      }
    } catch {
      const aiMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "Network error. Please check your connection.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
    } finally {
      setLoading(false);
      setTimeout(scrollToBottom, 100);
    }
  }

  async function handleGenerateReport(reportType: string) {
    setLoading(true);

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: `Generate ${reportType.replace(/_/g, " ")} report`,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);

    try {
      const res = await fetch(`/api/v1/workspaces/${workspaceId}/ai/status-report/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          report_type: reportType,
          trial_id: context?.trialId || undefined,
          audience: "team",
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const aiMessage: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.content,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiMessage]);
      }
    } finally {
      setLoading(false);
      setTimeout(scrollToBottom, 100);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white shadow-2xl border-l border-gray-200 flex flex-col z-50">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div>
          <h2 className="font-semibold text-gray-900">AI Assistant</h2>
          <p className="text-xs text-gray-500">Ask about your clinical trials</p>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 p-1"
          aria-label="Close AI sidebar"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Quick Actions */}
      {messages.length === 0 && (
        <div className="px-4 py-3 border-b border-gray-100">
          <p className="text-xs font-medium text-gray-500 mb-2">Quick Actions</p>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.label}
                onClick={() => handleSend(action.query)}
                className="text-xs bg-gray-100 hover:bg-blue-50 hover:text-blue-600 text-gray-700 rounded-full px-2.5 py-1 transition"
              >
                {action.icon} {action.label}
              </button>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <p className="text-xs font-medium text-gray-500 w-full mb-1">Generate Report</p>
            {["trial_status", "executive_summary", "cro_oversight"].map((type) => (
              <button
                key={type}
                onClick={() => handleGenerateReport(type)}
                className="text-xs bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-full px-2.5 py-1 transition"
              >
                {type.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {loading && (
          <div className="flex justify-start mb-3">
            <div className="bg-gray-100 rounded-lg px-4 py-2.5 flex items-center gap-2">
              <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600" />
              <span className="text-sm text-gray-500">Analyzing...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 px-4 py-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your trials..."
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
