import { expect, test } from "@playwright/test";

import { PROJECT } from "./project";

test("vista Strumenti e QA: dove sbaglia, con le parole di chi ha detto no", async ({ page }) => {
  await page.goto(`/projects/${PROJECT}`);
  await page.getByRole("navigation", { name: "Viste del progetto" }).getByRole("link", { name: "Strumenti e QA" }).click();
  await expect(page.getByRole("link", { name: "Strumenti e QA" })).toHaveAttribute("aria-current", "page");

  const brief = page.getByLabel("In breve");
  await expect(brief).toContainText("50%");
  await expect(brief).toContainText("2 di 4 file controllati");
  await expect(brief).toContainText("su 7 usi");
  await expect(brief).toContainText("e 2 passi indietro in tutto");

  // Proofs, FAILs, passed at once: more FAILs first, then more proofs at equal FAILs.
  const checks = page.getByRole("table", { name: "Controlli" });
  await expect(checks.locator("tbody th")).toHaveText(["svg_audit", "visual_review", "master_open"]);
  await expect(checks.getByRole("row", { name: /^svg_audit/ }).getByRole("cell")).toHaveText(["3", "1", "1 di 2"]);

  // The failed proofs per check and the refusals per tool: closed, with the count in the title.
  await page.getByText("svg_audit: 1 prova FAIL").click();
  const failures = page.getByRole("list", { name: "Prove fallite di svg_audit" }).getByRole("listitem");
  await expect(failures).toHaveCount(1);
  await expect(failures.nth(0)).toContainText("su exports/segno.svg, T-0005 Rifinitura X");
  // The reason on one line; the whole text, line breaks included, once it is opened.
  const reason = failures.nth(0).getByRole("group");
  await expect(reason.locator("summary")).toHaveText("3 nodi sottotracciati · nodi=24");
  await reason.locator("summary").click();
  await expect(reason.locator("pre")).toHaveText("3 nodi sottotracciati\nnodi=24");
  await expect(page.getByText("visual_review: 1 prova FAIL")).toBeVisible();

  const tools = page.getByRole("table", { name: "Strumenti" });
  await expect(tools.locator("tbody th")).toHaveText(["deliver", "write_file", "view_image", "block", "render"]);
  await expect(tools.getByRole("row", { name: /^deliver/ }).getByRole("cell")).toHaveText(["2", "1", "1"]);
  await page.getByText("deliver ha detto no 1 volta su 2 usi").click();
  const delivery = page.getByRole("list", { name: "Rifiuti di deliver" }).getByRole("listitem");
  await expect(delivery).toHaveCount(1);
  await expect(delivery.nth(0)).toContainText("T-0005-a1, turno 1");
  await expect(delivery.nth(0)).toContainText("consegna rifiutata: · exports/segno.svg: 'svg_audit' è FAIL");
  await page.getByText("write_file ha detto no 1 volta su 1 uso").click();
  const writing = page.getByRole("list", { name: "Rifiuti di write_file" }).getByRole("listitem");
  await expect(writing.nth(0)).toContainText("a critic");
  await expect(writing.nth(0)).toContainText("un revisore scrive solo in reviews/: non modifica il lavoro che giudica");

  const setbacks = page.getByRole("list", { name: "Passi indietro" }).getByRole("listitem");
  await expect(setbacks.nth(0)).toContainText(
    "Il contratto chiede review/critica.md, ma posso scrivere solo in reviews/. · Il referto è pronto.",
  );
  await expect(setbacks.nth(1)).toContainText("La coda sparisce a 16 px: ingrossala di 2 unità.");
});

test("le parole che non dicono un no restano nel registro", async ({ page }) => {
  for (const view of ["phases", "quality"]) {
    await page.goto(`/projects/${PROJECT}/${view}`);
    await expect(page.getByRole("main")).not.toContainText("Le parole di una consegna restano nel registro");
  }
});
