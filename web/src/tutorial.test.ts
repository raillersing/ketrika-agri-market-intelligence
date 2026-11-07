import { describe, expect, it } from "vitest";
import {
  QUEST_MISSIONS,
  getPlayerLevel,
  loadPlayerStats,
  savePlayerStats,
  resetPlayerStats,
  type PlayerStats,
} from "./lib/tutorial-data";
import { NAVIGATION_ICONS } from "./components/layout/navigation-icons";
import { NAVIGATION_PAGES } from "./lib/navigation";

describe("Gamified Tutorial & Academy Quests", () => {
  it("contains 7 high-detail missions with zero fabricated shortcuts", () => {
    expect(QUEST_MISSIONS.length).toBe(7);
    for (const quest of QUEST_MISSIONS) {
      expect(quest.title).toBeTruthy();
      expect(quest.briefing.context.length).toBeGreaterThan(40);
      expect(quest.briefing.keyPoints.length).toBeGreaterThanOrEqual(2);
      expect(quest.briefing.technicalRules.length).toBeGreaterThanOrEqual(1);
      expect(quest.steps.length).toBeGreaterThanOrEqual(2);
      expect(quest.quiz.options.length).toBe(4);
      expect(quest.quiz.correctIndex).toBeGreaterThanOrEqual(0);
      expect(quest.quiz.correctIndex).toBeLessThan(4);
      expect(quest.teleportUrl.startsWith("/")).toBe(true);
      expect(quest.xpReward).toBeGreaterThanOrEqual(100);
    }
  });

  it("calculates player levels and titles accurately across XP bands", () => {
    expect(getPlayerLevel(0).title).toBe("Apprenti Observateur");
    expect(getPlayerLevel(150).title).toBe("Apprenti Observateur");
    expect(getPlayerLevel(250).title).toBe("Explorateur des Terroirs");
    expect(getPlayerLevel(550).title).toBe("Analyste Prévisionniste");
    expect(getPlayerLevel(850).title).toBe("Grand Stratège des Marchés");
    expect(getPlayerLevel(1000).level).toBe(4);
  });

  it("registers /tutorial in navigation pages and icons", () => {
    const tutorialPage = NAVIGATION_PAGES.find((p) => p.href === "/tutorial");
    expect(tutorialPage).toBeDefined();
    expect(tutorialPage?.label).toBe("Guide & Quêtes");
    expect(NAVIGATION_ICONS["tutorial"]).toBeDefined();
  });

  it("handles player stats lifecycle safely", () => {
    const stats: PlayerStats = {
      level: 1,
      levelTitle: "Apprenti Observateur",
      totalXp: 150,
      completedQuests: ["quest-1-prices"],
      unlockedBadges: ["Gardien de la Provenance"],
      currentQuestId: "quest-2-forecasts",
    };
    savePlayerStats(stats);
    const loaded = loadPlayerStats();
    expect(loaded.totalXp).toBe(150);
    expect(loaded.completedQuests).toContain("quest-1-prices");

    const reset = resetPlayerStats();
    expect(reset.totalXp).toBe(0);
    expect(reset.completedQuests.length).toBe(0);
  });
});
