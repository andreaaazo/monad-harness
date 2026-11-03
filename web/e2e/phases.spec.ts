import { expect, test } from "@playwright/test";

import { PROJECT } from "./project";

test("vista Fasi: dove si è fermato, le fasi in ordine di lavoro, i passi indietro", async ({ page }) => {
  await page.goto(`/projects/${PROJECT}`);
  await page.getByRole("navigation", { name: "Viste del progetto" }).getByRole("link", { name: "Fasi" }).click();
  await expect(page.getByRole("link", { name: "Fasi" })).toHaveAttribute("aria-current", "page");

  const where = page.getByRole("region", { name: "Dove si è fermato" });
  await expect(where).toContainText("T-0001, aperto");
  await expect(where).toContainText("T-0005, Rifinitura X: consegnato, da accettare (identity-designer)");
  await expect(where).toContainText("T-0005 consegnato, 02/11/26, 10:45 UTC");

  // In ordine di lavoro, non di costo; la consegna al cliente non è una fase.
  const phases = page.getByRole("table", { name: "Fasi" });
  await expect(phases.locator("tbody th")).toHaveText([
    "director-plan",
    "explorer",
    "director-select",
    "proposer",
    "director-present",
    "finisher",
    "critic",
  ]);
  // Inizio, chiamate, costo, ticket, consegne, rimandi, bloccati, rifatto, senza esito
  await expect(phases.getByRole("row", { name: /^finisher/ }).getByRole("cell")).toHaveText([
    "02/11/26, 10:31 UTC",
    "2",
    "4,50 $",
    "1",
    "2",
    "1",
    "0",
    "2,10 $",
    "0,00 $",
  ]);
  await expect(phases.getByRole("row", { name: /^critic/ }).getByRole("cell")).toHaveText([
    "02/11/26, 10:38 UTC",
    "1",
    "0,30 $",
    "1",
    "0",
    "0",
    "1",
    "0,00 $",
    "0,30 $",
  ]);

  const setbacks = page.getByRole("list", { name: "Passi indietro" }).getByRole("listitem");
  await expect(setbacks).toHaveCount(2);
  await expect(setbacks.nth(0)).toContainText("T-0006 bloccato da critic: Revisione segno X");
  await expect(setbacks.nth(1)).toContainText("T-0005 rimandato da design-director dopo 1 consegna: Rifinitura X");
  // Il motivo, con le parole di chi lo ha fatto.
  await expect(setbacks.nth(1)).toContainText("La coda sparisce a 16 px: ingrossala di 2 unità.");

  await expect(page.getByRole("list", { name: "Passi di T-0005" }).getByRole("listitem")).toHaveText([
    "aperto",
    "consegnato",
    "rimandato",
    "consegnato",
  ]);
});
