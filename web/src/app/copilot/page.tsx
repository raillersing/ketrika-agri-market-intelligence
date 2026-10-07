"use client";

import React, { useState } from "react";
import { Sparkles, Send, Terminal, ShieldCheck, Database, HelpCircle } from "lucide-react";
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
        "Bonjour ! Je suis le copilote analyste de Ketrika. Je peux répondre à vos questions sur les marchés vivriers à Madagascar en interrogeant directement la base de données certifiée Gold. Chaque réponse s'appuie sur une requête SQL vérifiée et cite ses sources.",
      timestamp: "Maintenant",
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
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
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
        content: `Désolé, une erreur est survenue lors de l'exécution de la requête : ${err.message}`,
        timestamp: "Erreur",
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-emerald-600" />
          Copilote analyste de marché
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Assistant d&apos;analyse PPN connecté au schéma certifié Gold. SQL guardé et citations vérifiées.
        </p>
      </div>

      {/* Chat conversation area */}
      <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col h-[560px]">
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
                  className={`max-w-[85%] rounded-2xl px-5 py-3 text-sm shadow-sm ${
                    isUser
                      ? "bg-emerald-700 text-white rounded-br-none"
                      : "bg-muted text-foreground rounded-bl-none border border-border"
                  }`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>

                  {/* SQL fold / collapsible query */}
                  {m.sql && (
                    <details className="mt-3 p-2 bg-background/80 rounded border border-border/80 text-xs text-foreground cursor-pointer">
                      <summary className="font-semibold flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400">
                        <Terminal className="w-3.5 h-3.5" />
                        <span>Voir la requête SQL exécutée</span>
                      </summary>
                      <pre className="mt-2 p-2 bg-slate-950 text-emerald-400 rounded font-mono text-[11px] overflow-x-auto select-all">
                        {m.sql}
                      </pre>
                    </details>
                  )}

                  {/* Citations link badges */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-border/50 flex flex-wrap items-center gap-1.5 text-xs">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                      <span className="text-[11px] font-semibold text-muted-foreground">
                        Citations :
                      </span>
                      {m.citations.map((c, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded bg-background border border-border text-[11px] font-mono"
                        >
                          {c.observation_id ? (
                            <Link
                              href={`/observations/${c.observation_id}`}
                              className="text-emerald-700 hover:underline"
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
                <span className="text-[10px] text-muted-foreground mt-1 px-1">
                  {m.timestamp}
                </span>
              </div>
            );
          })}

          {loading && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground p-2">
              <Sparkles className="w-4 h-4 animate-spin text-emerald-600" />
              <span>Génération de la requête SQL et analyse en cours...</span>
            </div>
          )}
        </div>

        {/* Suggested questions shortcuts */}
        {messages.length <= 2 && (
          <div className="p-3 bg-muted/40 border-t border-border flex flex-wrap gap-2">
            <span className="text-xs text-muted-foreground flex items-center gap-1 self-center mr-1">
              <HelpCircle className="w-3.5 h-3.5" />
              Exemples :
            </span>
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                className="text-xs px-2.5 py-1 bg-background hover:bg-muted border border-border rounded-full text-foreground transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input input bar */}
        <div className="p-4 bg-background border-t border-border flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Posez votre question sur les prix vivriers, les stocks ou les prévisions..."
            className="flex-1 bg-muted/50 border border-input rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary shadow-sm"
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            className="p-2.5 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white rounded-lg shadow transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
