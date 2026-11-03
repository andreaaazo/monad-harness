import assert from "node:assert/strict";
import { test } from "node:test";

import { area, line, nearest, points } from "./chart.ts";

const frame = { width: 100, height: 50, inset: 5 };

test("una serie va da sinistra a destra, e il valore sale dal basso sulla scala comune", () => {
  assert.deepEqual(points([0, 50, 100], 100, frame), [
    { x: 5, y: 45 },
    { x: 50, y: 25 },
    { x: 95, y: 5 },
  ]);
  // La scala è comune a tutte le istanze: 50 su 200 sta a un quarto dell'altezza.
  assert.deepEqual(points([50], 200, frame), [{ x: 50, y: 35 }]);
});

test("una scala vuota tiene tutto sulla linea di base", () => {
  assert.deepEqual(points([0, 0], 0, frame), [
    { x: 5, y: 45 },
    { x: 95, y: 45 },
  ]);
});

test("la linea passa per i punti, l'area scende alla linea di base e si chiude", () => {
  const series = points([0, 50, 100], 100, frame);
  assert.equal(line(series), "M5,45L50,25L95,5");
  assert.equal(area(series, frame), "M5,45L5,45L50,25L95,5L95,45Z");
  assert.equal(line([]), "");
  assert.equal(area([], frame), "");
});

test("il turno più vicino al puntatore, anche fuori dal grafico", () => {
  assert.deepEqual([0, 20, 30, 52, 94, 200].map((x) => nearest(x, 3, frame)), [0, 0, 1, 1, 2, 2]);
  assert.equal(nearest(70, 1, frame), 0);
  assert.equal(nearest(70, 0, frame), -1);
});
