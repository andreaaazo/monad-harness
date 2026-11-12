import { expect, test } from "@playwright/test";

import { PROJECT } from "./project";

test("vista Modello: perché il modello si è fermato e come ha lavorato ogni ruolo", async ({ page }) => {
  await page.goto(`/projects/${PROJECT}/model`);
  await expect(page.getByRole("link", { name: "Modello" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("list", { name: "Motivi di fine" }).getByRole("listitem")).toHaveText([
    /^9 tool_use/,
    /^1 end_turn/,
    /^1 max_tokens/,
  ]);
  await expect(page.getByText("Risposte non arrivate intere: 1.")).toBeVisible();
  // Calls, cost, average and peak context, cache, reasoning, average duration, median TTFT, effort, stop
  await expect(
    page.getByRole("table", { name: "Ruoli" }).getByRole("row", { name: /^identity-designer/ }).getByRole("cell"),
  ).toHaveText(["3", "6,10 $", "4200", "4200", "86%", "180", "9,8 s", "2,6 s", "high", "tool_use 2, max_tokens 1"]);
});

test("vista Modello: il contesto turno per turno, col puntatore, con la tastiera e in tabella", async ({ page }) => {
  await page.goto(`/projects/${PROJECT}/model`);
  await page.waitForLoadState("networkidle");
  const cards = page.getByRole("list", { name: "Istanze" }).getByRole("listitem");
  await expect(cards).toHaveCount(9);
  const explorer = cards.filter({ hasText: "T-0002-a1" });
  await expect(explorer).toContainText("2 turni, picco 5800 token");
  // One scale: director-plan's peak of 4200 sits lower than the exploration's peak of 5800.
  const plan = cards.filter({ hasText: "T-0001-a1-plan" });
  const height = async (card: typeof plan) => Number(await card.locator("circle.dot").getAttribute("cy"));
  expect(await height(plan)).toBeGreaterThan(await height(explorer));

  const chart = explorer.getByRole("img", { name: /^Contesto per turno di T-0002-a1/ });
  // hover scrolls the chart into view; the position is relative to the chart: near the right edge, the last turn.
  const box = await chart.boundingBox();
  expect(box).not.toBeNull();
  await chart.hover({ position: { x: box!.width * 0.95, y: box!.height / 2 } });
  await expect(explorer.getByRole("status")).toContainText("5800 token");
  await expect(explorer.getByRole("status")).toContainText("turno 2 di 2");

  await chart.focus();
  await page.keyboard.press("Home");
  await expect(explorer.getByRole("status")).toContainText("4200 token");
  await expect(explorer.getByRole("status")).toContainText("turno 1 di 2");

  // What the chart shows is also in the table, without a pointer.
  await explorer.getByText("Turni in tabella").click();
  await expect(explorer.getByRole("table", { name: "Turni di T-0002-a1" }).locator("tbody tr")).toHaveText([
    /^1\s*4200\s*3600/,
    /^2\s*5800\s*5200/,
  ]);
});
