"use client";

import React, { useState } from "react";
import {
  Database,
  HelpCircle,
  Lightbulb,
  Send,
  ShieldCheck,
  Sparkles,
  Terminal,
} from "lucide-react";
import Link from "next/link";
import { BRAND } from "@/lib/brand";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sql?: string | null;
  citations?: Array<{ observation_id?: string; source_id?: string }>;
  timestamp: string;
}

const EXAMPLE_QUESTIONS = [
  "Quel est le prix médian du riz blanc à Analamanga sur les 6 derniers mois ?",
  "Quelles sont les régions présentant les prix du maïs les plus élevés ?",
  "Existe-t-il une alerte active sur les stocks de farine ou de sucre ?",
  "Quel est le volume d'importation de riz enregistré au dernier trimestre ?",
];

export default function CopilotPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "intro-msg",
      role: "assistant",
      content:
        `Bonjour ! Je suis l’assistant d’${BRAND.product}. Je peux vous aider à explorer les données disponibles sur les marchés vivriers à Madagascar. Les résultats dépendent des sources et de leur état de qualification.`,
      timestamp: "Connecté",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async (questionText?: string) => {
    const textToSend = questionText || input;
    if (!textToSend.trim() || loading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: textToSend,
      timestamp: new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const apiUrl = "/api";
      const res = await fetch(`${apiUrl}/v1/copilot/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ question: textToSend }),
      });

      if (!res.ok) {
        throw new Error("Erreur de traitement de la requête analyste");
      }

      const data = await res.json();
      const botMsg: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.answer_markdown || "Voici les données extraites selon votre requête.",
        sql: data.sql,
        citations: data.citations || [],
        timestamp: new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      const errorMsg: Message = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: `Désolé, une anomalie est survenue lors de l'exécution de la requête : ${err.message}`,
        timestamp: "Erreur",
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-foreground flex items-center gap-2.5">
              <Sparkles className="w-6 h-6 text-purple-700 dark:text-purple-400" />
              Copilote analyste de marché
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/20">
              Gold SQL Guard
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Génération SQL déterministe sur les faits de marché avec zéro chiffre inventé (SPECS §21).
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 glass-panel rounded-xl text-xs font-mono text-primary-readable">
          <ShieldCheck className="w-4 h-4" />
          <span>Garantie anti-hallucination</span>
        </div>
      </div>

      {/* Chat Conversation Box */}
      <div className="glass-card rounded-2xl overflow-hidden flex flex-col h-[600px] border border-border">
        {/* Messages scroll list */}
        <div className="flex-1 p-6 overflow-y-auto space-y-5">
          {messages.map((m) => {
            const isUser = m.role === "user";
            return (
              <div
                key={m.id}
                className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-5 py-3.5 text-xs shadow-md ${
                    isUser
                      ? "bg-primary-action text-primary-foreground rounded-br-none font-medium"
                      : "bg-card/90 text-foreground rounded-bl-none border border-border"
                  }`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>

                  {/* SQL fold / collapsible query */}
                  {m.sql && (
                    <details className="mt-3 p-2.5 bg-background/80 rounded-xl border border-border text-xs cursor-pointer group">
                      <summary className="font-mono text-[11px] font-semibold flex items-center gap-1.5 text-primary-readable group-hover:text-primary-readable transition-colors">
                        <Terminal className="w-3.5 h-3.5" />
                        <span>Inspecter la requête SQL exécutée</span>
                      </summary>
                      <pre className="mt-2 p-3 bg-background text-primary-readable rounded-lg font-mono text-[10px] overflow-x-auto select-all border border-border">
                        {m.sql}
                      </pre>
                    </details>
                  )}

                  {/* Citations link badges */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-border flex flex-wrap items-center gap-1.5 text-xs">
                      <ShieldCheck className="w-3.5 h-3.5 text-primary-readable" />
                      <span className="text-[10px] font-mono text-muted-foreground">
                        Citations certifiées :
                      </span>
                      {m.citations.map((c, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded-full bg-muted border border-border text-[10px] font-mono text-muted-foreground"
                        >
                          {c.observation_id ? (
                            <Link
                              href={`/observations/${c.observation_id}`}
                              className="text-primary-readable hover:underline"
                            >
                              obs:{c.observation_id.slice(0, 8)}
                            </Link>
                          ) : (
                            c.source_id
                          )}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <span className="text-[10px] text-muted-foreground font-mono mt-1 px-1">
                  {m.timestamp}
                </span>
              </div>
            );
          })}

          {loading && (
            <div className="flex items-center gap-2.5 text-xs text-purple-700 dark:text-purple-300 p-3 bg-purple-500/10 rounded-xl border border-purple-500/20 w-fit animate-pulse font-mono">
              <Sparkles className="w-4 h-4 animate-spin text-purple-700 dark:text-purple-400" />
              <span>Génération de la requête SQL certifiée et analyse...</span>
            </div>
          )}
        </div>

        {/* Suggested questions shortcuts */}
        {messages.length <= 2 && (
          <div className="p-3.5 bg-background/60 border-t border-border flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground flex items-center gap-1 font-mono text-[11px] mr-1">
              <Lightbulb className="w-3.5 h-3.5 text-amber-700 dark:text-amber-400" />
              Suggestions :
            </span>
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                className="text-[11px] px-3 py-1 bg-card hover:bg-muted border border-border hover:border-purple-500/40 rounded-full text-muted-foreground hover:text-foreground transition-all shadow-sm"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input bar */}
        <div className="p-4 bg-background/80 border-t border-border flex items-center gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Interroger les prix vivriers, prévisions ou alertes..."
            className="flex-1 bg-card border border-border rounded-xl px-4 py-2.5 text-xs text-foreground placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-purple-500 shadow-inner"
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            className="p-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-primary-foreground rounded-xl shadow-lg shadow-purple-950/50 transition-all hover:scale-105"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
