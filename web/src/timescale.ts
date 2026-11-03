/**
 * Il tempo del cruscotto: minuti fra due istanti, e la scala del lavoro della timeline. Nessuna dipendenza,
 * così le prove girano con node --test senza costruire Next.js.
 */

/** Un'attesa del cliente, come la descrive l'API: il run fermo da `started_at` per `minutes`. */
export type Pause = { readonly started_at: string; readonly minutes: number };

/** Minuti tra due istanti ISO. */
export function between(start: string, end: string): number {
  return (Date.parse(end) - Date.parse(start)) / 60_000;
}

/**
 * Dove cade un istante, in percentuale del lavoro fatto fra `start` e `end`: il tempo delle attese si toglie,
 * così una notte in attesa della decisione non schiaccia le barre del lavoro. Fuori dall'intervallo si ferma
 * a 0 o a 100.
 */
export function workScale(start: string, end: string, pauses: readonly Pause[]): (moment: string) => number {
  const idle = (moment: string) =>
    pauses.reduce((total, pause) => total + Math.min(Math.max(between(pause.started_at, moment), 0), pause.minutes), 0);
  const worked = (moment: string) => between(start, moment) - idle(moment);
  const total = worked(end);
  return (moment) => (total <= 0 ? 0 : Math.min(Math.max((worked(moment) / total) * 100, 0), 100));
}
