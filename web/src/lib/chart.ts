/**
 * The geometry of the dashboard's charts, in `viewBox` units: pure, without React, so the tests run with
 * node --test. The scale goes from zero to `max`, shared by every chart that is compared.
 */

export type Frame = { readonly width: number; readonly height: number; readonly inset: number };
export type Point = { readonly x: number; readonly y: number };

const round = (value: number) => Math.round(value * 100) / 100;

/** The points of a series: x by position, from left to right; y from the bottom. A single point sits in the middle. */
export function points(values: readonly number[], max: number, frame: Frame): Point[] {
  const { width, height, inset } = frame;
  const step = values.length > 1 ? (width - 2 * inset) / (values.length - 1) : 0;
  return values.map((value, index) => ({
    x: round(values.length > 1 ? inset + index * step : width / 2),
    y: round(height - inset - (max > 0 ? (value / max) * (height - 2 * inset) : 0)),
  }));
}

/** The series as an SVG path, from point to point. */
export function line(series: readonly Point[]): string {
  return series.map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`).join("");
}

/** The area under the line, down to the baseline. */
export function area(series: readonly Point[], frame: Frame): string {
  const first = series[0];
  const last = series.at(-1);
  if (first === undefined || last === undefined) return "";
  const base = round(frame.height - frame.inset);
  return `M${first.x},${base}${line(series).replace(/^M/, "L")}L${last.x},${base}Z`;
}

/** The position nearest to an x of the chart; -1 if the series is empty. */
export function nearest(x: number, count: number, frame: Frame): number {
  if (count <= 0) return -1;
  if (count === 1) return 0;
  const step = (frame.width - 2 * frame.inset) / (count - 1);
  return Math.min(Math.max(Math.round((x - frame.inset) / step), 0), count - 1);
}
