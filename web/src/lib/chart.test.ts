import assert from "node:assert/strict";
import { test } from "node:test";

import { area, line, nearest, points } from "./chart.ts";

const frame = { width: 100, height: 50, inset: 5 };

test("a series runs from left to right, and the value rises from the bottom on the shared scale", () => {
  assert.deepEqual(points([0, 50, 100], 100, frame), [
    { x: 5, y: 45 },
    { x: 50, y: 25 },
    { x: 95, y: 5 },
  ]);
  // The scale is shared by every instance: 50 out of 200 sits at a quarter of the height.
  assert.deepEqual(points([50], 200, frame), [{ x: 50, y: 35 }]);
});

test("an empty scale keeps everything on the baseline", () => {
  assert.deepEqual(points([0, 0], 0, frame), [
    { x: 5, y: 45 },
    { x: 95, y: 45 },
  ]);
});

test("the line goes through the points, and the area goes down to the baseline and closes", () => {
  const series = points([0, 50, 100], 100, frame);
  assert.equal(line(series), "M5,45L50,25L95,5");
  assert.equal(area(series, frame), "M5,45L5,45L50,25L95,5L95,45Z");
  assert.equal(line([]), "");
  assert.equal(area([], frame), "");
});

test("the turn nearest to the pointer, even outside the chart", () => {
  assert.deepEqual([0, 20, 30, 52, 94, 200].map((x) => nearest(x, 3, frame)), [0, 0, 1, 1, 2, 2]);
  assert.equal(nearest(70, 1, frame), 0);
  assert.equal(nearest(70, 0, frame), -1);
});
