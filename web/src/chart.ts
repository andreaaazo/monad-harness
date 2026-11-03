/**
 * La geometria dei grafici del cruscotto, in unità del `viewBox`: pura, senza React, così le prove girano
 * con node --test. La scala va da zero a `max`, comune a tutti i grafici che si confrontano.
 */

export type Frame = { readonly width: number; readonly height: number; readonly inset: number };
export type Point = { readonly x: number; readonly y: number };

const round = (value: number) => Math.round(value * 100) / 100;

/** I punti di una serie: x per posizione, da sinistra a destra; y dal basso. Un punto solo sta al centro. */
export function points(values: readonly number[], max: number, frame: Frame): Point[] {
  const { width, height, inset } = frame;
  const step = values.length > 1 ? (width - 2 * inset) / (values.length - 1) : 0;
  return values.map((value, index) => ({
    x: round(values.length > 1 ? inset + index * step : width / 2),
    y: round(height - inset - (max > 0 ? (value / max) * (height - 2 * inset) : 0)),
  }));
}

export function line(series: readonly Point[]): string {
  return series.map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`).join("");
}

/** Sotto la linea, fino alla linea di base. */
export function area(series: readonly Point[], frame: Frame): string {
  const first = series[0];
  const last = series.at(-1);
  if (first === undefined || last === undefined) return "";
  const base = round(frame.height - frame.inset);
  return `M${first.x},${base}${line(series).replace(/^M/, "L")}L${last.x},${base}Z`;
}

/** La posizione più vicina a una x del grafico; -1 se la serie è vuota. */
export function nearest(x: number, count: number, frame: Frame): number {
  if (count <= 0) return -1;
  if (count === 1) return 0;
  const step = (frame.width - 2 * frame.inset) / (count - 1);
  return Math.min(Math.max(Math.round((x - frame.inset) / step), 0), count - 1);
}
