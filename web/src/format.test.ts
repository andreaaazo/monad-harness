import assert from "node:assert/strict";
import { test } from "node:test";

import { count, minutes, seconds, share, usd, when } from "./format.ts";

test("soldi, conteggi e quote all'italiana", () => {
  assert.equal(usd(10.5), "10,50 $");
  assert.equal(count(81014), "81.014");
  assert.equal(share(0.687), "69%");
});

test("le durate in decimi sotto l'ora, in ore e minuti da un'ora in su", () => {
  assert.equal(minutes(44), "44,0 min");
  assert.equal(minutes(59.94), "59,9 min");
  // Arrotondata a 60,0 sarebbe un'ora scritta in minuti.
  assert.equal(minutes(59.96), "1 h");
  assert.equal(minutes(60), "1 h");
  assert.equal(minutes(121), "2 h 1 min");
  assert.equal(minutes(980.0667), "16 h 20 min");
});

test("i tempi misurati in secondi sotto il minuto, poi in minuti; un tempo non misurato è un trattino", () => {
  assert.equal(seconds(null), "–");
  assert.equal(seconds(2100), "2,1 s");
  assert.equal(seconds(59_940), "59,9 s");
  assert.equal(seconds(59_960), "1,0 min");
  assert.equal(seconds(1_323_300), "22,1 min");
});

test("gli istanti in UTC, e un istante che manca è un trattino", () => {
  assert.equal(when("2026-11-02T10:30:00+00:00"), "02/11/26, 10:30 UTC");
  assert.equal(when(null), "–");
});
