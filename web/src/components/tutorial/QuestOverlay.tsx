"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Award,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  Gamepad2,
  HelpCircle,
  Maximize2,
  RotateCcw,
  Sparkles,
  Target,
  Trophy,
  X,
  Zap,
} from "lucide-react";
import {
  getPlayerLevel,
  loadPlayerStats,
  QUEST_MISSIONS,
  QuestMission,
  resetPlayerStats,
  savePlayerStats,
  type PlayerStats,
} from "@/lib/tutorial-data";

export function QuestOverlay() {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [selectedQuest, setSelectedQuest] = useState<QuestMission>(QUEST_MISSIONS[0]);
  const [completedSteps, setCompletedSteps] = useState<Record<string, boolean>>({});
  const [selectedQuizAnswer, setSelectedQuizAnswer] = useState<number | null>(null);
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [showCelebration, setShowCelebration] = useState(false);
  const [activeTab, setActiveTab] = useState<"quest" | "tree">("quest");

  useEffect(() => {
    const loaded = loadPlayerStats();
    setStats(loaded);
    const active = QUEST_MISSIONS.find((q) => q.id === loaded.currentQuestId) || QUEST_MISSIONS[0];
    setSelectedQuest(active);
  }, []);

  if (!stats) return null;

  const currentLevelInfo = getPlayerLevel(stats.totalXp);
  const isQuestCompleted = stats.completedQuests.includes(selectedQuest.id);
  const totalQuestsCount = QUEST_MISSIONS.length;
  const completedCount = stats.completedQuests.length;

  const handleStepToggle = (stepId: string) => {
    setCompletedSteps((prev) => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  const handleQuizSubmit = () => {
    if (selectedQuizAnswer === null || quizSubmitted) return;
    setQuizSubmitted(true);

    if (selectedQuizAnswer === selectedQuest.quiz.correctIndex) {
      if (!stats.completedQuests.includes(selectedQuest.id)) {
        const newXp = stats.totalXp + selectedQuest.xpReward;
        const newCompleted = [...stats.completedQuests, selectedQuest.id];
        const newBadges = [...stats.unlockedBadges, selectedQuest.badgeName];
        const nextIndex = QUEST_MISSIONS.findIndex((q) => q.id === selectedQuest.id) + 1;
        const nextQuestId = nextIndex < QUEST_MISSIONS.length ? QUEST_MISSIONS[nextIndex].id : selectedQuest.id;

        const updatedStats: PlayerStats = {
          ...stats,
          totalXp: newXp,
          completedQuests: newCompleted,
          unlockedBadges: newBadges,
          currentQuestId: nextQuestId,
        };

        setStats(updatedStats);
        savePlayerStats(updatedStats);
        setShowCelebration(true);
        setTimeout(() => setShowCelebration(false), 4000);
      }
    }
  };

  const handleSelectQuest = (q: QuestMission) => {
    setSelectedQuest(q);
    setSelectedQuizAnswer(null);
    setQuizSubmitted(false);
    setActiveTab("quest");
  };

  const handleReset = () => {
    if (window.confirm("Voulez-vous réinitialiser votre progression du tutoriel ?")) {
      const reset = resetPlayerStats();
      setStats(reset);
      setSelectedQuest(QUEST_MISSIONS[0]);
      setSelectedQuizAnswer(null);
      setQuizSubmitted(false);
    }
  };

  return (
    <>
      {/* FLOATING ACTION BUTTON (HUD launcher) */}
      <div className="fixed bottom-5 right-5 z-40">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="group relative flex items-center gap-2.5 rounded-full bg-gradient-to-r from-orange-600 via-amber-600 to-orange-500 px-4 py-3 text-white shadow-xl shadow-orange-600/30 ring-2 ring-white/20 transition-all hover:scale-105 hover:shadow-orange-600/50 active:scale-95"
          title="Ouvrir le Guide et Quêtes interactives"
          aria-label="Guide et Quêtes interactives"
        >
          <Gamepad2 className="h-5 w-5 animate-pulse text-amber-200" />
          <span className="text-xs font-bold tracking-wide">
            Missions & Guide
          </span>
          <span className="flex items-center gap-1 rounded-full bg-black/30 px-2 py-0.5 text-[10px] font-mono font-extrabold text-amber-300 border border-amber-300/30">
            {completedCount}/{totalQuestsCount}
          </span>
          {completedCount < totalQuestsCount && (
            <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-amber-500"></span>
            </span>
          )}
        </button>
      </div>

      {/* GAMIFIED MODAL / HUD OVERLAY */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative flex flex-col w-full max-w-3xl max-h-[90vh] rounded-2xl border border-orange-500/30 bg-card text-foreground shadow-2xl overflow-hidden ring-1 ring-border">
            
            {/* HUD HEADER: LEVEL, XP, TITLE */}
            <div className="relative bg-gradient-to-r from-orange-950 via-slate-900 to-stone-900 p-4 sm:p-5 text-white border-b border-orange-500/30">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-orange-600/20 border border-orange-500/40 text-amber-400 shadow-inner">
                    <Trophy className="h-6 w-6" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono uppercase tracking-wider text-amber-400 font-bold">
                        Niveau {currentLevelInfo.level} · {currentLevelInfo.title}
                      </span>
                      <span className="rounded-full bg-orange-500/20 px-2 py-0.5 text-[10px] font-mono text-orange-300 border border-orange-500/30">
                        {stats.totalXp} XP
                      </span>
                    </div>
                    <h2 className="text-lg sm:text-xl font-extrabold tracking-tight text-white flex items-center gap-2">
                      Académie Irooa <span className="text-orange-400 font-normal">| Guide Interactif</span>
                    </h2>
                  </div>
                </div>

                {/* CONTROLS */}
                <div className="flex items-center gap-2">
                  <Link
                    href="/tutorial"
                    onClick={() => setIsOpen(false)}
                    prefetch={false}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/20 transition-colors"
                    title="Ouvrir la page complète de l'Académie"
                  >
                    <Maximize2 className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Plein écran</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => setIsOpen(false)}
                    className="rounded-lg p-1.5 text-white/70 hover:bg-white/10 hover:text-white transition-colors"
                    aria-label="Fermer"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              </div>

              {/* XP PROGRESS BAR */}
              <div className="mt-4 space-y-1">
                <div className="flex justify-between text-[11px] font-mono text-white/70">
                  <span>Progression globale : {completedCount} / {totalQuestsCount} Quêtes achevées</span>
                  <span>{Math.round((stats.totalXp / 1000) * 100)}% de maîtrise</span>
                </div>
                <div className="h-2 w-full rounded-full bg-white/10 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-amber-400 via-orange-500 to-amber-300 transition-all duration-500 shadow-sm"
                    style={{ width: `${Math.min(100, (stats.totalXp / 1000) * 100)}%` }}
                  />
                </div>
              </div>

              {/* NAVIGATION TABS */}
              <div className="flex gap-2 mt-4 pt-1">
                <button
                  type="button"
                  onClick={() => setActiveTab("quest")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    activeTab === "quest"
                      ? "bg-orange-500 text-white shadow-sm"
                      : "bg-white/5 text-white/70 hover:bg-white/10"
                  }`}
                >
                  <Target className="h-3.5 w-3.5" />
                  Mission Active : #{selectedQuest.number}
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("tree")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    activeTab === "tree"
                      ? "bg-orange-500 text-white shadow-sm"
                      : "bg-white/5 text-white/70 hover:bg-white/10"
                  }`}
                >
                  <Award className="h-3.5 w-3.5" />
                  Arbre des Quêtes ({completedCount}/{totalQuestsCount})
                </button>
              </div>
            </div>

            {/* CELEBRATION BANNER */}
            {showCelebration && (
              <div className="bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-500 p-3 text-white text-center font-bold text-sm animate-bounce flex items-center justify-center gap-2 shadow-md">
                <Sparkles className="h-5 w-5 text-amber-300" />
                <span>🎉 QUÊTE ACCOMPLIE ! +{selectedQuest.xpReward} XP et badge débloqué : {selectedQuest.badgeIcon} {selectedQuest.badgeName} !</span>
              </div>
            )}

            {/* MODAL BODY (SCROLLABLE) */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">

              {activeTab === "quest" ? (
                <>
                  {/* QUEST HEADER */}
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-600 dark:text-orange-400 font-bold border border-orange-500/20">
                          Mission {selectedQuest.number} / {totalQuestsCount} · {selectedQuest.category}
                        </span>
                        {isQuestCompleted && (
                          <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-500/30">
                            <Check className="h-3 w-3" /> Validée (+{selectedQuest.xpReward} XP)
                          </span>
                        )}
                      </div>
                      <h3 className="text-xl font-extrabold text-foreground mt-1">
                        {selectedQuest.title}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {selectedQuest.subtitle} · Durée estimée : {selectedQuest.estimatedMinutes} min
                      </p>
                    </div>

                    {/* TELEPORT BUTTON */}
                    <button
                      type="button"
                      onClick={() => {
                        setIsOpen(false);
                        router.push(selectedQuest.teleportUrl);
                      }}
                      className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-orange-600 to-amber-600 px-4 py-2.5 text-xs font-bold text-white shadow-md hover:from-orange-500 hover:to-amber-500 transition-all hover:scale-105 active:scale-95"
                    >
                      <Zap className="h-4 w-4 text-amber-300" />
                      {selectedQuest.teleportLabel}
                    </button>
                  </div>

                  {/* QUEST BRIEFING */}
                  <div className="rounded-xl border border-border bg-card/60 p-4 sm:p-5 space-y-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                      <BookOpen className="h-4 w-4 text-orange-500" />
                      Briefing de la Mission
                    </h4>
                    <p className="text-sm leading-relaxed text-foreground">
                      {selectedQuest.briefing.context}
                    </p>

                    <div className="space-y-1.5 pt-2">
                      <span className="text-xs font-semibold text-foreground">Points clés à retenir :</span>
                      <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground">
                        {selectedQuest.briefing.keyPoints.map((point, idx) => (
                          <li key={idx} className="leading-relaxed">
                            {point}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="space-y-1.5 pt-2 border-t border-border/50">
                      <span className="text-xs font-semibold text-foreground">Règles techniques d&apos;intégrité :</span>
                      <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground">
                        {selectedQuest.briefing.technicalRules.map((rule, idx) => (
                          <li key={idx} className="leading-relaxed">
                            {rule}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {selectedQuest.briefing.warnings && (
                      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200">
                        <strong>Attention :</strong> {selectedQuest.briefing.warnings}
                      </div>
                    )}
                  </div>

                  {/* INTERACTIVE CHECKLIST */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                      <Target className="h-4 w-4 text-orange-500" />
                      Objectifs pratiques de la quête
                    </h4>
                    <div className="space-y-2">
                      {selectedQuest.steps.map((step, idx) => {
                        const isChecked = isQuestCompleted || !!completedSteps[step.id];
                        return (
                          <div
                            key={step.id}
                            className={`flex items-start gap-3 rounded-xl border p-3 transition-colors ${
                              isChecked
                                ? "border-emerald-500/30 bg-emerald-500/5 text-foreground"
                                : "border-border bg-card hover:border-orange-500/30"
                            }`}
                          >
                            <button
                              type="button"
                              onClick={() => handleStepToggle(step.id)}
                              className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-all ${
                                isChecked
                                  ? "border-emerald-600 bg-emerald-600 text-white"
                                  : "border-border hover:border-orange-500"
                              }`}
                              aria-label={`Valider étape ${idx + 1}`}
                            >
                              {isChecked && <Check className="h-3.5 w-3.5" />}
                            </button>
                            <div className="flex-1">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className={`text-sm font-semibold ${isChecked ? "line-through text-muted-foreground" : "text-foreground"}`}>
                                  Étape {idx + 1} : {step.label}
                                </span>
                                {step.actionUrl && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setIsOpen(false);
                                      router.push(step.actionUrl!);
                                    }}
                                    className="text-xs font-semibold text-orange-600 dark:text-orange-400 hover:underline inline-flex items-center gap-1"
                                  >
                                    {step.actionLabel || "Accéder"} <ExternalLink className="h-3 w-3" />
                                  </button>
                                )}
                              </div>
                              <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                                {step.description}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* MINI-QUIZ TO EARN BADGE & XP */}
                  <div className="rounded-xl border border-orange-500/30 bg-gradient-to-br from-card to-orange-500/5 p-4 sm:p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-orange-600 dark:text-orange-400 flex items-center gap-2">
                        <HelpCircle className="h-4 w-4" />
                        Défi de Validation (+{selectedQuest.xpReward} XP)
                      </h4>
                      <span className="text-xs font-mono font-bold text-foreground">
                        Badge : {selectedQuest.badgeIcon} {selectedQuest.badgeName}
                      </span>
                    </div>

                    <p className="text-sm font-semibold text-foreground">
                      {selectedQuest.quiz.question}
                    </p>

                    <div className="space-y-2">
                      {selectedQuest.quiz.options.map((option, optIdx) => {
                        const isSelected = selectedQuizAnswer === optIdx;
                        const isCorrect = optIdx === selectedQuest.quiz.correctIndex;
                        let optionStyle = "border-border bg-card hover:bg-card/80 hover:border-orange-500/40 text-foreground";
                        if (quizSubmitted) {
                          if (isCorrect) {
                            optionStyle = "border-emerald-500 bg-emerald-500/15 text-emerald-900 dark:text-emerald-200 font-bold";
                          } else if (isSelected) {
                            optionStyle = "border-rose-500 bg-rose-500/15 text-rose-900 dark:text-rose-200 line-through";
                          } else {
                            optionStyle = "opacity-50 border-border bg-card";
                          }
                        } else if (isSelected) {
                          optionStyle = "border-orange-500 bg-orange-500/10 text-orange-950 dark:text-orange-100 ring-2 ring-orange-500/30";
                        }

                        return (
                          <button
                            key={optIdx}
                            type="button"
                            onClick={() => !quizSubmitted && setSelectedQuizAnswer(optIdx)}
                            disabled={quizSubmitted}
                            className={`w-full text-left p-3 rounded-lg border text-xs sm:text-sm transition-all flex items-start gap-3 ${optionStyle}`}
                          >
                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-current text-[11px] font-mono font-bold">
                              {String.fromCharCode(65 + optIdx)}
                            </span>
                            <span>{option}</span>
                          </button>
                        );
                      })}
                    </div>

                    {!quizSubmitted ? (
                      <button
                        type="button"
                        onClick={handleQuizSubmit}
                        disabled={selectedQuizAnswer === null}
                        className="w-full rounded-xl bg-orange-600 py-2.5 text-xs font-bold text-white shadow hover:bg-orange-500 disabled:opacity-50 transition-colors"
                      >
                        Valider ma réponse et débloquer les XP
                      </button>
                    ) : (
                      <div className="rounded-lg border border-border bg-card p-3 space-y-1">
                        <div className="flex items-center gap-2">
                          {selectedQuizAnswer === selectedQuest.quiz.correctIndex ? (
                            <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                              <CheckCircle2 className="h-4 w-4" /> Excellente réponse !
                            </span>
                          ) : (
                            <span className="text-xs font-bold text-rose-600 dark:text-rose-400">
                              Pas tout à fait...
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {selectedQuest.quiz.explanation}
                        </p>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                /* TREE / OVERVIEW TAB */
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-base font-bold text-foreground">
                      Arbre de Compétences & Quêtes
                    </h3>
                    <button
                      type="button"
                      onClick={handleReset}
                      className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-rose-500 transition-colors"
                    >
                      <RotateCcw className="h-3.5 w-3.5" /> Réinitialiser
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {QUEST_MISSIONS.map((q) => {
                      const isDone = stats.completedQuests.includes(q.id);
                      const isCurrent = q.id === selectedQuest.id;

                      return (
                        <button
                          key={q.id}
                          type="button"
                          onClick={() => handleSelectQuest(q)}
                          className={`flex flex-col text-left p-4 rounded-xl border transition-all ${
                            isCurrent
                              ? "border-orange-500 bg-orange-500/10 ring-2 ring-orange-500/30"
                              : isDone
                              ? "border-emerald-500/30 bg-card hover:border-emerald-500/50"
                              : "border-border bg-card/60 hover:bg-card hover:border-orange-500/30"
                          }`}
                        >
                          <div className="flex items-center justify-between w-full">
                            <span className="text-2xl">{q.badgeIcon}</span>
                            {isDone ? (
                              <span className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-500/30">
                                <Check className="h-3 w-3" /> Terminé
                              </span>
                            ) : (
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-card border border-border text-muted-foreground font-semibold">
                                +{q.xpReward} XP
                              </span>
                            )}
                          </div>
                          <span className="font-bold text-sm text-foreground mt-2">
                            #{q.number} {q.title}
                          </span>
                          <span className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                            {q.subtitle}
                          </span>
                          <span className="text-[11px] font-mono text-orange-600 dark:text-orange-400 mt-2 font-medium">
                            {q.badgeName}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* FOOTER */}
            <div className="bg-header p-3 sm:p-4 border-t border-border flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5 font-mono">
                <Trophy className="h-4 w-4 text-amber-500" />
                Badges débloqués : {stats.unlockedBadges.length} / {totalQuestsCount}
              </span>
              <div className="flex items-center gap-3">
                <Link
                  href="/tutorial"
                  onClick={() => setIsOpen(false)}
                  prefetch={false}
                  className="font-bold text-orange-600 dark:text-orange-400 hover:underline"
                >
                  Consulter le guide complet & documentation →
                </Link>
              </div>
            </div>

          </div>
        </div>
      )}
    </>
  );
}
