import assert from "node:assert/strict";
import { test } from "node:test";

import { count, counted, minutes, oneLine, seconds, share, signed, usd, when } from "./format.ts";

test("money, counts and shares in Italian notation", () => {
  assert.equal(usd(10.5), "10,50 $");
  assert.equal(count(81014), "81.014");
  assert.equal(share(0.687), "69%");
});

test("a number with its noun, singular only for one", () => {
  assert.deepEqual(
    [0, 1, 2, 1000].map((value) => counted(value, "turno", "turni")),
    ["0 turni", "1 turno", "2 turni", "1000 turni"],
  );
});

test("durations in tenths below an hour, in hours and minutes from an hour up", () => {
  assert.equal(minutes(44), "44,0 min");
  assert.equal(minutes(59.94), "59,9 min");
  // Rounded to 60.0 it would be an hour written in minutes.
  assert.equal(minutes(59.96), "1 h");
  assert.equal(minutes(60), "1 h");
  assert.equal(minutes(121), "2 h 1 min");
  assert.equal(minutes(980.0667), "16 h 20 min");
});

test("measured times in seconds below a minute, then in minutes; an unmeasured time is a dash", () => {
  assert.equal(seconds(null), "–");
  assert.equal(seconds(2100), "2,1 s");
  assert.equal(seconds(59_940), "59,9 s");
  assert.equal(seconds(59_960), "1,0 min");
  assert.equal(seconds(1_323_300), "22,1 min");
});

test("instants in UTC, and a missing instant is a dash", () => {
  assert.equal(when("2026-11-02T10:30:00+00:00"), "02/11/26, 10:30 UTC");
  assert.equal(when(null), "–");
});

test("a text on one line: line breaks become a middle dot, and the rest is cut and says so", () => {
  assert.equal(oneLine("consegna rifiutata:\nexports/segno.svg: 'svg_audit' è FAIL", 80), "consegna rifiutata: · exports/segno.svg: 'svg_audit' è FAIL");
  assert.equal(oneLine("  troppi   spazi\n\n\n  e righe vuote  ", 80), "troppi spazi · e righe vuote");
  assert.equal(oneLine("abcdefghij", 6), "abcde…");
  assert.equal(oneLine("", 6), "");
});

test("a difference has its sign, and two values that read the same are unchanged", () => {
  assert.equal(signed(1.2, usd), "+1,20 $");
  assert.equal(signed(-0.5, usd), "−0,50 $");
  assert.equal(signed(0.001, usd), "invariato");
  assert.equal(signed(-3, count), "−3");
  assert.equal(signed(90, minutes), "+1 h 30 min");
});
