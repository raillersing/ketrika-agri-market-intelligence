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
  Flame,
  Gamepad2,
  GraduationCap,
  HelpCircle,
  Layers,
  MapPin,
  Package,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
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

export default function TutorialAcademyPage() {
  const router = useRouter();
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [activeMission, setActiveMission] = useState<QuestMission>(QUEST_MISSIONS[0]);
  const [completedSteps, setCompletedSteps] = useState<Record<string, boolean>>({});
  const [quizAnswer, setQuizAnswer] = useState<number | null>(null);
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [celebration, setCelebration] = useState(false);

  useEffect(() => {
    const loaded = loadPlayerStats();
    setStats(loaded);
    const m = QUEST_MISSIONS.find((q) => q.id === loaded.currentQuestId) || QUEST_MISSIONS[0];
    setActiveMission(m);
  }, []);

  if (!stats) {
    return (
      <div className="p-16 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
        <Sparkles className="h-4 w-4 animate-spin text-orange-500" />
        Initialisation de l&apos;Académie Irooa...
      </div>
    );
  }

  const levelInfo = getPlayerLevel(stats.totalXp);
  const isMissionCompleted = stats.completedQuests.includes(activeMission.id);
  const totalCount = QUEST_MISSIONS.length;
  const completedCount = stats.completedQuests.length;

  const handleStepToggle = (stepId: string) => {
    setCompletedSteps((prev) => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  const handleQuizSubmit = () => {
    if (quizAnswer === null || quizSubmitted) return;
    setQuizSubmitted(true);

    if (quizAnswer === activeMission.quiz.correctIndex) {
      if (!stats.completedQuests.includes(activeMission.id)) {
        const newXp = stats.totalXp + activeMission.xpReward;
        const newCompleted = [...stats.completedQuests, activeMission.id];
        const newBadges = [...stats.unlockedBadges, activeMission.badgeName];
        const nextIdx = QUEST_MISSIONS.findIndex((q) => q.id === activeMission.id) + 1;
        const nextId = nextIdx < QUEST_MISSIONS.length ? QUEST_MISSIONS[nextIdx].id : activeMission.id;

        const updated: PlayerStats = {
          ...stats,
          totalXp: newXp,
          completedQuests: newCompleted,
          unlockedBadges: newBadges,
          currentQuestId: nextId,
        };

        setStats(updated);
        savePlayerStats(updated);
        setCelebration(true);
        setTimeout(() => setCelebration(false), 4500);
      }
    }
  };

  const handleSelectMission = (m: QuestMission) => {
    setActiveMission(m);
    setQuizAnswer(null);
    setQuizSubmitted(false);
  };

  const handleReset = () => {
    if (window.confirm("Voulez-vous réinitialiser votre score d'Académie et recommencer au niveau 1 ?")) {
      const reset = resetPlayerStats();
      setStats(reset);
      setActiveMission(QUEST_MISSIONS[0]);
      setQuizAnswer(null);
      setQuizSubmitted(false);
    }
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-16 animate-in fade-in duration-300">
      
      {/* HERO / GAMIFIED HEADER */}
      <div className="relative overflow-hidden rounded-3xl border border-orange-500/30 bg-gradient-to-br from-stone-950 via-slate-900 to-orange-950 p-6 sm:p-10 text-white shadow-2xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-3 max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-orange-500/20 px-3 py-1 text-xs font-mono font-bold text-amber-300 border border-orange-500/30">
              <Gamepad2 className="h-4 w-4" />
              TUTORIEL INTERACTIF GAMIFIÉ
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
              Académie Irooa Ketrika
            </h1>
            <p className="text-sm sm:text-base text-stone-300 leading-relaxed">
              Explorez toutes les fonctionnalités de la plateforme à travers 7 missions guidées immersives.
              Accomplissez les objectifs, réussissez les défis pour gagner des points d&apos;expérience (XP) et débloquer vos badges d&apos;Analyste.
            </p>
          </div>

          {/* PLAYER CARD */}
          <div className="rounded-2xl border border-white/15 bg-white/10 p-5 backdrop-blur-md min-w-[280px] space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-600/30 border border-orange-400/40 text-amber-300">
                  <Trophy className="h-5 w-5" />
                </div>
                <div>
                  <span className="text-[11px] font-mono uppercase tracking-wider text-amber-300 font-bold block">
                    Niveau {levelInfo.level}
                  </span>
                  <span className="font-extrabold text-sm text-white block">
                    {levelInfo.title}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={handleReset}
                className="text-white/60 hover:text-rose-300 transition-colors"
                title="Réinitialiser la progression"
              >
                <RotateCcw className="h-4 w-4" />
              </button>
            </div>

            {/* XP BAR */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono text-white/80">
                <span>Expérience : {stats.totalXp} XP</span>
                <span>{completedCount} / {totalCount} Quêtes</span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-black/40 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-amber-400 via-orange-500 to-amber-300 transition-all duration-500 shadow-md"
                  style={{ width: `${Math.min(100, (stats.totalXp / 1000) * 100)}%` }}
                />
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5 pt-1">
              {QUEST_MISSIONS.map((q) => {
                const isDone = stats.completedQuests.includes(q.id);
                return (
                  <span
                    key={q.id}
                    title={`${q.title} : ${isDone ? "Validé" : "En attente"}`}
                    className={`inline-flex items-center justify-center h-8 w-8 rounded-lg text-sm transition-all border ${
                      isDone
                        ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300 shadow"
                        : "bg-white/5 border-white/10 text-white/40 opacity-60"
                    }`}
                  >
                    {q.badgeIcon}
                  </span>
                );
              })}
            </div>
          </div>
        </div>

        {/* GLOW DECORATIONS */}
        <div className="absolute -top-24 -right-24 h-72 w-72 rounded-full bg-orange-600/20 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-amber-600/10 blur-3xl pointer-events-none" />
      </div>

      {/* CELEBRATION ALERT */}
      {celebration && (
        <div className="rounded-2xl bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-500 p-4 text-white text-center font-bold text-base shadow-lg animate-bounce flex items-center justify-center gap-3">
          <Sparkles className="h-6 w-6 text-amber-300 animate-spin" />
          <span>FÉLICITATIONS ! Quête validée : +{activeMission.xpReward} XP ! Badge débloqué : {activeMission.badgeIcon} {activeMission.badgeName}</span>
        </div>
      )}

      {/* MAIN TWO-COLUMN WORKSPACE */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* LEFT COLUMN: QUEST ROSTER (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Target className="h-4 w-4 text-orange-500" />
              Missions d&apos;apprentissage ({completedCount}/{totalCount})
            </h2>
          </div>

          <div className="space-y-2.5">
            {QUEST_MISSIONS.map((q) => {
              const isDone = stats.completedQuests.includes(q.id);
              const isActive = q.id === activeMission.id;

              return (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => handleSelectMission(q)}
                  className={`w-full text-left p-4 rounded-2xl border transition-all flex items-start gap-3.5 ${
                    isActive
                      ? "border-orange-500 bg-orange-500/10 shadow-sm ring-2 ring-orange-500/30"
                      : isDone
                      ? "border-emerald-500/30 bg-card hover:border-emerald-500/60"
                      : "border-border bg-card/60 hover:bg-card hover:border-orange-500/30"
                  }`}
                >
                  <span className="text-2xl mt-0.5">{q.badgeIcon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-card border border-border text-muted-foreground font-bold">
                        Mission {q.number}
                      </span>
                      {isDone ? (
                        <span className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-500/30">
                          <Check className="h-3 w-3" /> Fait
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono text-amber-600 dark:text-amber-400 font-bold">
                          +{q.xpReward} XP
                        </span>
                      )}
                    </div>
                    <h3 className="font-bold text-sm text-foreground mt-1 truncate">
                      {q.title}
                    </h3>
                    <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
                      {q.subtitle}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>

          {/* EXTRA DOCUMENTATION CARD */}
          <div className="rounded-2xl border border-border bg-card p-5 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <BookOpen className="h-4 w-4 text-orange-500" />
              Documentation de référence
            </h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              L&apos;intégralité de l&apos;audit technique des 12 modules et le guide de formation textuel sont archivés dans le dépôt sous <code className="font-mono text-foreground font-semibold">docs/AUDIT_ET_GUIDE_UTILISATEUR.md</code>.
            </p>
            <div className="pt-1">
              <span className="text-xs font-semibold text-orange-600 dark:text-orange-400">
                100% Provenance Bronze · Zéro Donnée Fictive
              </span>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: ACTIVE MISSION DETAIL & CHALLENGE (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          
          {/* MISSION HERO CARD */}
          <div className="rounded-3xl border border-border bg-card p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded-full bg-orange-500/10 text-orange-600 dark:text-orange-400 border border-orange-500/20">
                    Mission #{activeMission.number} · {activeMission.category}
                  </span>
                  {isMissionCompleted && (
                    <span className="flex items-center gap-1 text-xs font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30">
                      <Check className="h-3.5 w-3.5" /> Accomplie (+{activeMission.xpReward} XP)
                    </span>
                  )}
                </div>
                <h2 className="text-2xl sm:text-3xl font-extrabold text-foreground mt-2">
                  {activeMission.title}
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  {activeMission.subtitle} · Temps estimé : {activeMission.estimatedMinutes} minutes
                </p>
              </div>

              {/* TELEPORT ACTION BUTTON */}
              <button
                type="button"
                onClick={() => router.push(activeMission.teleportUrl)}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-orange-600 to-amber-600 px-5 py-3 text-xs sm:text-sm font-bold text-white shadow-md hover:from-orange-500 hover:to-amber-500 transition-all hover:scale-105 active:scale-95"
              >
                <Zap className="h-4 w-4 text-amber-200" />
                {activeMission.teleportLabel}
              </button>
            </div>

            {/* MISSION BRIEFING */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-orange-500" />
                Briefing Opérationnel & Contexte
              </h3>
              <p className="text-sm sm:text-base leading-relaxed text-foreground">
                {activeMission.briefing.context}
              </p>

              {/* KEY POINTS */}
              <div className="rounded-2xl border border-border bg-card/60 p-4 space-y-2">
                <span className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Éléments clés à retenir :
                </span>
                <ul className="list-disc list-inside space-y-1.5 text-xs sm:text-sm text-muted-foreground">
                  {activeMission.briefing.keyPoints.map((pt, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {pt}
                    </li>
                  ))}
                </ul>
              </div>

              {/* TECHNICAL RULES */}
              <div className="rounded-2xl border border-border bg-card/60 p-4 space-y-2">
                <span className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Règles techniques et constitutionnelles :
                </span>
                <ul className="list-disc list-inside space-y-1.5 text-xs sm:text-sm text-muted-foreground">
                  {activeMission.briefing.technicalRules.map((rule, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {rule}
                    </li>
                  ))}
                </ul>
              </div>

              {activeMission.briefing.warnings && (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs sm:text-sm text-amber-900 dark:text-amber-200">
                  <strong>Règle d&apos;intégrité :</strong> {activeMission.briefing.warnings}
                </div>
              )}
            </div>

            {/* INTERACTIVE CHECKLIST STEPS */}
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                <Target className="h-4 w-4 text-orange-500" />
                Checklist des actions sur la plateforme
              </h3>

              <div className="space-y-2.5">
                {activeMission.steps.map((st, idx) => {
                  const isChecked = isMissionCompleted || !!completedSteps[st.id];

                  return (
                    <div
                      key={st.id}
                      className={`flex items-start gap-3.5 rounded-xl border p-4 transition-all ${
                        isChecked
                          ? "border-emerald-500/30 bg-emerald-500/5"
                          : "border-border bg-card hover:border-orange-500/30"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => handleStepToggle(st.id)}
                        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-all ${
                          isChecked
                            ? "border-emerald-600 bg-emerald-600 text-white"
                            : "border-border hover:border-orange-500"
                        }`}
                        aria-label={`Valider ${st.label}`}
                      >
                        {isChecked && <Check className="h-3.5 w-3.5" />}
                      </button>

                      <div className="flex-1">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className={`text-sm font-semibold ${isChecked ? "line-through text-muted-foreground" : "text-foreground"}`}>
                            Étape {idx + 1} : {st.label}
                          </span>
                          {st.actionUrl && (
                            <button
                              type="button"
                              onClick={() => router.push(st.actionUrl!)}
                              className="text-xs font-bold text-orange-600 dark:text-orange-400 hover:underline inline-flex items-center gap-1"
                            >
                              {st.actionLabel || "Accéder"} <ExternalLink className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                        <p className="text-xs sm:text-sm text-muted-foreground mt-1 leading-relaxed">
                          {st.description}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* VALIDATION QUIZ TO EARN BADGE */}
            <div className="rounded-2xl border border-orange-500/30 bg-gradient-to-br from-card to-orange-500/5 p-6 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-orange-600 dark:text-orange-400 flex items-center gap-2">
                  <HelpCircle className="h-4 w-4" />
                  Défi de validation des connaissances (+{activeMission.xpReward} XP)
                </h3>
                <span className="text-xs font-mono font-bold text-foreground">
                  Badge en jeu : {activeMission.badgeIcon} {activeMission.badgeName}
                </span>
              </div>

              <p className="text-sm sm:text-base font-bold text-foreground">
                {activeMission.quiz.question}
              </p>

              <div className="space-y-2.5">
                {activeMission.quiz.options.map((option, optIdx) => {
                  const isSelected = quizAnswer === optIdx;
                  const isCorrect = optIdx === activeMission.quiz.correctIndex;
                  let style = "border-border bg-card hover:bg-card/80 hover:border-orange-500/40 text-foreground";

                  if (quizSubmitted) {
                    if (isCorrect) {
                      style = "border-emerald-500 bg-emerald-500/15 text-emerald-950 dark:text-emerald-200 font-bold";
                    } else if (isSelected) {
                      style = "border-rose-500 bg-rose-500/15 text-rose-950 dark:text-rose-200 line-through";
                    } else {
                      style = "opacity-50 border-border bg-card";
                    }
                  } else if (isSelected) {
                    style = "border-orange-500 bg-orange-500/10 text-orange-950 dark:text-orange-100 ring-2 ring-orange-500/30";
                  }

                  return (
                    <button
                      key={optIdx}
                      type="button"
                      onClick={() => !quizSubmitted && setQuizAnswer(optIdx)}
                      disabled={quizSubmitted}
                      className={`w-full text-left p-3.5 rounded-xl border text-xs sm:text-sm transition-all flex items-start gap-3.5 ${style}`}
                    >
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-current text-[11px] font-mono font-bold mt-0.5">
                        {String.fromCharCode(65 + optIdx)}
                      </span>
                      <span className="leading-relaxed">{option}</span>
                    </button>
                  );
                })}
              </div>

              {!quizSubmitted ? (
                <button
                  type="button"
                  onClick={handleQuizSubmit}
                  disabled={quizAnswer === null}
                  className="w-full rounded-xl bg-orange-600 py-3 text-xs sm:text-sm font-bold text-white shadow-md hover:bg-orange-500 disabled:opacity-50 transition-colors"
                >
                  Valider ma réponse et réclamer mon badge
                </button>
              ) : (
                <div className="rounded-xl border border-border bg-card p-4 space-y-2">
                  <div className="flex items-center gap-2">
                    {quizAnswer === activeMission.quiz.correctIndex ? (
                      <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                        <CheckCircle2 className="h-5 w-5" /> Excellente réponse !
                      </span>
                    ) : (
                      <span className="text-sm font-bold text-rose-600 dark:text-rose-400">
                        Pas tout à fait...
                      </span>
                    )}
                  </div>
                  <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                    {activeMission.quiz.explanation}
                  </p>
                </div>
              )}
            </div>

          </div>
        </div>

      </div>

    </div>
  );
}
