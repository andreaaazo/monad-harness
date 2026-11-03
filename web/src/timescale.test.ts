import assert from "node:assert/strict";
import { test } from "node:test";

import { between, workScale } from "./timescale.ts";

const at = (minute: number) => new Date(Date.UTC(2026, 10, 2, 10, minute)).toISOString();

test("i minuti fra due istanti", () => {
  assert.equal(between("2026-11-02T10:00:00+00:00", "2026-11-02T10:30:00+00:00"), 30);
  assert.equal(between("2026-11-02T10:30:00+00:00", "2026-11-02T10:00:00+00:00"), -30);
});

test("senza attese la scala è il tempo", () => {
  const place = workScale(at(0), at(40), []);
  assert.deepEqual([at(0), at(10), at(40)].map(place), [0, 25, 100]);
});

test("un'attesa non occupa spazio: prima, durante e dopo cadono dove finisce il lavoro fatto", () => {
  // Un'ora: 20 minuti di lavoro, 30 di attesa, 10 di lavoro.
  const place = workScale(at(0), at(60), [{ started_at: at(20), minutes: 30 }]);
  assert.equal(place(at(10)), (10 / 30) * 100);
  assert.equal(place(at(20)), (20 / 30) * 100);
  assert.equal(place(at(35)), (20 / 30) * 100);
  assert.equal(place(at(50)), (20 / 30) * 100);
  assert.equal(place(at(55)), (25 / 30) * 100);
  assert.equal(place(at(60)), 100);
});

test("fuori dal run la scala si ferma ai bordi, e un run di un istante sta tutto a sinistra", () => {
  const place = workScale(at(10), at(20), []);
  assert.deepEqual([place(at(0)), place(at(30))], [0, 100]);
  assert.equal(workScale(at(10), at(10), [])(at(10)), 0);
});
