"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Terminal, Loader2, User, Bot } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function Home() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/agent/invoke", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          input: {
            messages: [
              {
                type: "human",
                content: userMessage,
              },
            ],
          },
          config: {
            configurable: {
              thread_id: "web-client-" + Date.now(),
            },
          },
        }),
      });

      if (!response.ok) throw new Error("Network response was not ok");

      const data = await response.json();
      
      const responseMessages = data.output.messages;
      const lastMessage = responseMessages[responseMessages.length - 1];
      
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: lastMessage.content },
      ]);
    } catch (error) {
      console.error("Error:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: Failed to connect to the Agency." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-neutral-950 text-neutral-200 font-mono">
      {/* Header */}
      <header className="flex items-center p-4 border-b border-neutral-800 bg-neutral-900/50 backdrop-blur">
        <Terminal className="w-6 h-6 mr-3 text-emerald-500" />
        <h1 className="text-lg font-bold tracking-tight">
          VIBE CODER <span className="text-neutral-500">AGENCY CONSOLE</span>
        </h1>
      </header>

      {/* Chat Area */}
      <main className="flex-1 overflow-y-auto p-4 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-neutral-500 opacity-50">
            <Bot className="w-16 h-16 mb-4" />
            <p>System Ready. Awaiting Directives.</p>
          </div>
        )}
        
        {messages.map((msg, index) => (
          <div
            key={index}
            className={cn(
              "flex items-start max-w-3xl mx-auto gap-4",
              msg.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20 shrink-0">
                <Bot className="w-5 h-5 text-emerald-500" />
              </div>
            )}
            
            <div
              className={cn(
                "p-4 rounded-lg text-sm leading-relaxed whitespace-pre-wrap",
                msg.role === "user"
                  ? "bg-blue-600/10 border border-blue-500/20 text-blue-100"
                  : "bg-neutral-900 border border-neutral-800 text-neutral-300"
              )}
            >
              {msg.content}
            </div>

            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center border border-blue-500/20 shrink-0">
                <User className="w-5 h-5 text-blue-500" />
              </div>
            )}
          </div>
        ))}
        
        {isLoading && (
          <div className="flex items-start max-w-3xl mx-auto gap-4">
             <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                <Bot className="w-5 h-5 text-emerald-500" />
              </div>
              <div className="flex items-center gap-2 p-4 text-emerald-500/50">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-xs uppercase tracking-widest">Processing...</span>
              </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* Input Area */}
      <div className="p-4 border-t border-neutral-800 bg-neutral-900/50 backdrop-blur">
        <form
          onSubmit={handleSubmit}
          className="max-w-3xl mx-auto flex gap-2 relative"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter directive..."
            className="flex-1 bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all placeholder:text-neutral-700"
            disabled={isLoading}
          />
          <button
            type="submit"
            aria-label="Send Message"
            disabled={isLoading || !input.trim()}
            className="absolute right-2 top-2 bottom-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}