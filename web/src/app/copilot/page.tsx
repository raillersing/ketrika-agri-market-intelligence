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
        "Bonjour ! Je suis le Copilote Analyste de Ketrika. Je réponds à vos questions sur les marchés vivriers à Madagascar en interrogeant directement la base certifiée Gold via SQL sécurisé en lecture seule (copilot_ro).\n\nToutes les valeurs numériques citées sont vérifiées mécaniquement : aucun chiffre généré ou halluciné.",
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
            <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
              <Sparkles className="w-6 h-6 text-purple-400" />
              Copilote analyste de marché
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-purple-500/10 text-purple-300 border border-purple-500/20">
              Gold SQL Guard
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Génération SQL déterministe sur les faits de marché avec zéro chiffre inventé (SPECS §21).
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 glass-panel rounded-xl text-xs font-mono text-emerald-400">
          <ShieldCheck className="w-4 h-4" />
          <span>Garantie anti-hallucination</span>
        </div>
      </div>

      {/* Chat Conversation Box */}
      <div className="glass-card rounded-2xl overflow-hidden flex flex-col h-[600px] border border-white/[0.08]">
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
                      ? "bg-emerald-600 text-white rounded-br-none font-medium"
                      : "bg-slate-900/90 text-slate-200 rounded-bl-none border border-white/[0.08]"
                  }`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>

                  {/* SQL fold / collapsible query */}
                  {m.sql && (
                    <details className="mt-3 p-2.5 bg-slate-950/80 rounded-xl border border-white/[0.06] text-xs cursor-pointer group">
                      <summary className="font-mono text-[11px] font-semibold flex items-center gap-1.5 text-emerald-400 group-hover:text-emerald-300 transition-colors">
                        <Terminal className="w-3.5 h-3.5" />
                        <span>Inspecter la requête SQL exécutée</span>
                      </summary>
                      <pre className="mt-2 p-3 bg-slate-950 text-emerald-300 rounded-lg font-mono text-[10px] overflow-x-auto select-all border border-white/[0.05]">
                        {m.sql}
                      </pre>
                    </details>
                  )}

                  {/* Citations link badges */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-white/[0.08] flex flex-wrap items-center gap-1.5 text-xs">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-[10px] font-mono text-slate-400">
                        Citations certifiées :
                      </span>
                      {m.citations.map((c, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded-full bg-slate-800 border border-white/[0.06] text-[10px] font-mono text-slate-300"
                        >
                          {c.observation_id ? (
                            <Link
                              href={`/observations/${c.observation_id}`}
                              className="text-emerald-400 hover:underline"
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
                <span className="text-[10px] text-slate-400 font-mono mt-1 px-1">
                  {m.timestamp}
                </span>
              </div>
            );
          })}

          {loading && (
            <div className="flex items-center gap-2.5 text-xs text-purple-300 p-3 bg-purple-500/10 rounded-xl border border-purple-500/20 w-fit animate-pulse font-mono">
              <Sparkles className="w-4 h-4 animate-spin text-purple-400" />
              <span>Génération de la requête SQL certifiée et analyse...</span>
            </div>
          )}
        </div>

        {/* Suggested questions shortcuts */}
        {messages.length <= 2 && (
          <div className="p-3.5 bg-slate-950/60 border-t border-white/[0.06] flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-400 flex items-center gap-1 font-mono text-[11px] mr-1">
              <Lightbulb className="w-3.5 h-3.5 text-amber-400" />
              Suggestions :
            </span>
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                className="text-[11px] px-3 py-1 bg-slate-900 hover:bg-slate-800 border border-white/[0.08] hover:border-purple-500/40 rounded-full text-slate-300 hover:text-white transition-all shadow-sm"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input bar */}
        <div className="p-4 bg-slate-950/80 border-t border-white/[0.08] flex items-center gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Interroger les prix vivriers, prévisions ou alertes..."
            className="flex-1 bg-slate-900 border border-white/[0.1] rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-purple-500 shadow-inner"
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            className="p-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white rounded-xl shadow-lg shadow-purple-950/50 transition-all hover:scale-105"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
