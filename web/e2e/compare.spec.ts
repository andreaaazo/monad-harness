import { expect, test } from "@playwright/test";

import { BEFORE, PROJECT } from "./project";

test("vista Confronto: due progetti affiancati, l'impronta che cambia, il giudizio alla cieca", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Cruscotto" }).getByRole("link", { name: "Confronto" }).click();
  // Senza una scelta: i due progetti che hanno lavorato per ultimi, prima il più vecchio.
  await expect(page.getByRole("combobox", { name: "Prima", exact: true })).toHaveValue(BEFORE);
  await expect(page.getByRole("combobox", { name: "Dopo", exact: true })).toHaveValue(PROJECT);

  const sides = page.getByRole("table", { name: "Affiancati" });
  const row = (name: string) => sides.getByRole("row", { name: new RegExp(`^${name}`) }).getByRole("cell");
  await expect(row("Costo")).toHaveText(["6,00 $", "10,80 $", "+4,80 $"]);
  await expect(row("Lavoro")).toHaveText(["9,0 min", "38,0 min", "+29,0 min"]);
  await expect(row("Fino alla presentazione")).toHaveText(["–", "6,00 $ in 24,0 min", ""]);
  await expect(row("Rifatto")).toHaveText(["0,00 $", "2,10 $", "+2,10 $"]);
  await expect(row("Controlli al primo colpo")).toHaveText(["0 di 0", "2 di 4", ""]);
  await expect(row("Rifiuti degli strumenti")).toHaveText(["0 su 0 usi", "2 su 7 usi", ""]);

  const phases = page.getByRole("table", { name: "Fasi affiancate" });
  await expect(phases.getByRole("row", { name: /^finisher/ }).getByRole("cell")).toHaveText(["5,50 $", "4,50 $", "−1,00 $"]);
  await expect(phases.getByRole("row", { name: /^explorer/ }).getByRole("cell")).toHaveText(["–", "3,50 $", ""]);

  await expect(
    page.getByText(`Dall'ultima esecuzione di ${BEFORE} (#3) alla prima di ${PROJECT} (#1): 2 differenze.`),
  ).toBeVisible();
  const changes = page.getByRole("table", { name: "Differenze di impronta" });
  await expect(changes.getByRole("row", { name: /^explorers/ }).getByRole("cell")).toHaveText(["", "5", "3"]);
  await expect(changes.getByRole("row", { name: /^prompts/ }).getByRole("cell")).toHaveText([
    "prompts/roles/identity-designer.md",
    "111111111111",
    "222222222222",
  ]);
  await expect(page.getByRole("list", { name: `Esecuzioni di ${PROJECT}` }).getByRole("listitem")).toHaveText([
    /^#1 run .*8 chiamate, 6,00 \$: la prima$/,
    /^#2 decide .*3 chiamate, 4,80 \$: identica alla precedente$/,
  ]);

  const votes = page.getByRole("table", { name: "Voti del confronto prima-dopo" });
  await expect(votes.getByRole("row", { name: /^B/ })).toContainText("il migliore");
  await expect(votes.getByRole("row", { name: /^B/ })).toContainText(PROJECT);
  await expect(votes.getByRole("row", { name: /^A/ })).toContainText("non regge: generico");
});

test("vista Confronto: si sceglie chi confrontare, e un progetto con sé stesso non si confronta", async ({ page }) => {
  await page.goto("/compare");
  await page.getByRole("combobox", { name: "Prima", exact: true }).selectOption(PROJECT);
  await page.getByRole("combobox", { name: "Dopo", exact: true }).selectOption(BEFORE);
  await page.getByRole("button", { name: "Confronta" }).click();
  await expect(page).toHaveURL(new RegExp(`before=${PROJECT}&after=${BEFORE}`));
  await expect(
    page.getByRole("table", { name: "Affiancati" }).getByRole("row", { name: /^Costo/ }).getByRole("cell"),
  ).toHaveText(["10,80 $", "6,00 $", "−4,80 $"]);

  // Una scelta sbagliata non è un guasto dell'API: si dice cosa scegliere, e la scelta resta lì.
  await page.goto(`/compare?before=${PROJECT}&after=${PROJECT}`);
  await expect(page.getByRole("main").getByRole("alert")).toContainText("scegli due progetti diversi");
  await expect(page.getByRole("heading", { name: "L'API non risponde come atteso" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Confronta" })).toBeVisible();
  const response = await page.goto(`/compare?before=fantasma&after=${PROJECT}`);
  expect(response?.status()).toBe(404);
});
