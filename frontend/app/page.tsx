"use client";
import { useState, useRef, useEffect } from "react";
import { Send, Terminal, Loader2, User, Bot } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import ProjectBoard from "../components/ProjectBoard";

function cn(...inputs: (string | undefined | null | false)[]) { return twMerge(clsx(inputs)); }
interface Message { role: "user" | "assistant"; content: string; }

export default function Home() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string>("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Hydration Safe: Only generate ID on client
    setThreadId("web-client-" + Date.now());
  }, []);

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); };
  useEffect(() => { scrollToBottom(); }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => { e.preventDefault(); if (!input.trim() || isLoading) return; const userMessage = input.trim(); setInput(""); setMessages((prev) => [...prev, { role: "user", content: userMessage }]); setIsLoading(true);
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    try {
      const response = await fetch(`${API_BASE_URL}/agent/invoke`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ input: { messages: [{ type: "human", content: userMessage }] }, config: { configurable: { thread_id: threadId } } }) });
      if (!response.ok) throw new Error("Network response");
      const data = await response.json();
      const lastMessage = data.output.messages[data.output.messages.length - 1];
      setMessages((prev) => [...prev, { role: "assistant", content: lastMessage.content }]);
    } catch (error) { console.error("Error:", error); setMessages((prev) => [...prev, { role: "assistant", content: "Error: Failed to connect." }]); } finally { setIsLoading(false); }
  };

  // Prevent rendering until ID is ready to avoid mismatch
  if (!threadId) return null;

  return (
    <div className="flex h-screen bg-neutral-950 text-neutral-200 font-mono overflow-hidden">
      <div className="flex-1 flex flex-col min-w-0 border-r border-neutral-800">
        <header className="flex items-center p-4 border-b border-neutral-800 bg-neutral-900/50 backdrop-blur">
          <Terminal className="w-5 h-5 mr-3 text-emerald-500" />
          <h1 className="text-lg font-bold tracking-tight">VIBE CODER <span className="text-neutral-500">CONSOLE</span></h1>
        </header>
        <main className="flex-1 overflow-y-auto p-4 space-y-6">
          {messages.length === 0 && <div className="flex flex-col items-center justify-center h-full text-neutral-500 opacity-50"><Bot className="w-10 h-10 mb-4" /><p>System Ready.</p></div>}
          {messages.map((msg, i) => (
            <div key={i} className={cn("flex items-start max-w-2xl gap-3", msg.role === "user" ? "ml-auto justify-end" : "mr-auto justify-start")}>
              {msg.role === "assistant" && <div className="w-8 h-8 rounded bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20 shrink-0"><Bot className="w-4 h-4 text-emerald-500" /></div>}
              <div className={cn("p-3 rounded text-sm leading-relaxed whitespace-pre-wrap", msg.role === "user" ? "bg-blue-900/20 border border-blue-500/20 text-blue-100" : "bg-neutral-900 border border-neutral-800 text-neutral-300")}>{msg.content}</div>
            </div>
          ))}
          {isLoading && <div className="flex items-center gap-2 p-4 text-emerald-500/50"><Loader2 className="w-4 h-4 animate-spin" /><span className="text-xs uppercase">Processing...</span></div>}
          <div ref={messagesEndRef} />
        </main>
        <div className="p-4 border-t border-neutral-800 bg-neutral-900/50">
          <form onSubmit={handleSubmit} className="flex gap-2"><input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Directive..." className="flex-1 bg-neutral-950 border border-neutral-800 rounded px-4 py-2 focus:outline-none focus:border-emerald-500/50" disabled={isLoading} /><button type="submit" aria-label="Send" disabled={isLoading || !input.trim()} className="px-4 bg-emerald-600 text-white rounded hover:bg-emerald-500 disabled:opacity-50"><Send className="w-4 h-4" /></button></form>
        </div>
      </div>
      <div className="w-[350px] hidden md:block">
        <ProjectBoard threadId={threadId} />
      </div>
    </div>
  );
}