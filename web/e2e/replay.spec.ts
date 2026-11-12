import { expect, test } from "@playwright/test";

import { PROJECT, REPLAYED } from "./project";

test("vista Replay: un'istanza turno per turno, con le misure, il ragionamento e le immagini", async ({ page }) => {
  await page.goto(`/projects/${PROJECT}`);
  await page.getByRole("navigation", { name: "Viste del progetto" }).getByRole("link", { name: "Replay" }).click();
  await page.getByRole("table", { name: "Istanze" }).getByRole("link", { name: REPLAYED }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${PROJECT}/replay/${REPLAYED}$`));

  await expect(page.getByLabel("L'istanza")).toContainText("2 turni in trascrizione");
  await expect(page.getByLabel("L'istanza")).toContainText("consegnato");
  await expect(page.getByText("Misure: ogni turno è legato alla sua chiamata dal request_id.")).toBeVisible();

  const turns = page.getByRole("list", { name: "Turni" }).getByRole("listitem");
  await expect(turns).toHaveCount(2);
  const first = page.getByRole("listitem", { name: "Turno 1" });
  await expect(first.getByRole("heading")).toHaveText("Turno 1 4200 token di contesto · 0,90 $ · 9,0 s · tool_use");
  await first.getByText("Ragionamento").click();
  await expect(first).toContainText("Guardo prima il foglio intero, poi il dettaglio");
  await expect(first).toContainText("Apro il foglio");

  // The PNG goes from the browser to Next.js, and from there to Django: it is really drawn.
  const image = first.getByRole("img", { name: "Immagine 1 restituita da view_image" });
  await expect(image).toHaveAttribute("src", `/api/projects/${PROJECT}/instances/${REPLAYED}/images/0`);
  await image.scrollIntoViewIfNeeded();
  await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBe(4);

  const second = page.getByRole("listitem", { name: "Turno 2" });
  await expect(second).toContainText("Immagine image/svg+xml non mostrata");
  await expect(second.getByRole("img")).toHaveCount(0);
  await expect(second).toContainText("L'harness: Ricorda di consegnare con deliver");
});

test("vista Replay: una risposta scartata si vede, e una trascrizione vecchia si lega per ordine", async ({ page }) => {
  await page.goto(`/projects/${PROJECT}/replay/T-0004-a1`);
  await expect(page.getByLabel("Dopo l'ultimo turno")).toContainText(
    "Una risposta scartata: tagliata dal limite di token, 1,60 $. Non è in trascrizione.",
  );
  await page.goto(`/projects/${PROJECT}/replay/T-0006-a1`);
  await expect(page.getByText("Misure: turni e chiamate legati per ordine")).toBeVisible();
  await expect(page.getByRole("listitem", { name: "Turno 1" })).toContainText("write_file ha detto no");
});

test("vista Replay: un'istanza senza trascrizione e un'immagine che non c'è non esistono", async ({ page, request }) => {
  const response = await page.goto(`/projects/${PROJECT}/replay/T-0003-a1`);
  expect(response?.status()).toBe(404);
  expect((await request.get(`/api/projects/${PROJECT}/instances/${REPLAYED}/images/1`)).status()).toBe(404);
  const picture = await request.get(`/api/projects/${PROJECT}/instances/${REPLAYED}/images/0`);
  expect(picture.headers()["content-type"]).toBe("image/png");
  expect(picture.headers()["cache-control"]).toContain("no-store");
});
