"use client";

import React, { useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Send, Sparkles } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { Button, Card, CardContent, PageHeader } from "@/components/ui";
import { SourceTag } from "../quotes/ai-panels";

interface Turn { role: "user" | "assistant"; text: string; source?: string }

const SUGGESTIONS = [
  "How much is in my open pipeline?",
  "Which quotes expire in the next two weeks?",
  "How many approvals are pending?",
  "Who are my top customers?",
  "Which open quotes have the deepest discounts?",
];

export default function CopilotPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const { data: status } = useQuery<{ gemini_configured: boolean; model: string }>({
    queryKey: ["ai-status"],
    queryFn: () => api.get("/ai/status"),
  });

  const ask = useMutation({
    mutationFn: (question: string) => api.post<{ answer: string; source: string }>("/ai/ask", { question }),
    onSuccess: (r) => {
      setTurns((t) => [...t, { role: "assistant", text: r.answer, source: r.source }]);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    },
    onError: (e) => setTurns((t) => [...t, { role: "assistant", text: errorMessage(e, "The copilot could not answer.") }]),
  });

  const send = (q: string) => {
    if (!q.trim() || ask.isPending) return;
    setTurns((t) => [...t, { role: "user", text: q }]);
    setInput("");
    ask.mutate(q);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="AI Copilot" description="Ask about your pipeline. Answers are grounded in the quotes you have access to." />

      <div className="flex items-center gap-2 text-xs text-slate-600">
        <Sparkles size={13} />
        {status?.gemini_configured
          ? `Gemini (${status.model}) is connected: ask anything about your pipeline.`
          : "Gemini is not configured (set GEMINI_API_KEY in backend/.env). Built-in analytics answer common questions; free-form questions need Gemini."}
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="min-h-[320px] max-h-[520px] overflow-y-auto p-5 space-y-4">
            {turns.length === 0 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-600">Try one of these:</p>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => send(s)} className="text-xs px-3 py-1.5 border border-hairline rounded-md bg-canvas-soft hover:bg-canvas-tint cursor-pointer">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {turns.map((t, i) => (
              <div key={i} className={t.role === "user" ? "flex justify-end" : "flex justify-start"}>
                <div className={`max-w-[80%] px-4 py-2.5 rounded-xl text-sm whitespace-pre-wrap ${t.role === "user" ? "bg-primary text-white" : "bg-canvas-tint text-ink"}`}>
                  {t.text}
                  {t.source && <div className="mt-1.5"><SourceTag source={t.source} /></div>}
                </div>
              </div>
            ))}
            {ask.isPending && <p className="text-xs text-slate-500">Thinking…</p>}
            <div ref={endRef} />
          </div>
          <form
            className="border-t border-hairline p-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <input
              className="flex-1 px-3 py-2.5 bg-canvas border border-field-border rounded-md text-sm focus:outline-none focus:border-ink"
              placeholder="Ask about your pipeline…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <Button type="submit" variant="primary" icon={<Send size={14} />} disabled={!input.trim() || ask.isPending}>
              Ask
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
