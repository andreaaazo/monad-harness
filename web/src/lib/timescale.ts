/**
 * The dashboard's time: minutes between two instants, and the work scale of the timeline. No dependencies, so the
 * tests run with node --test without building Next.js.
 */

/** A client wait, as the API describes it: the run stopped from `started_at` for `minutes`. */
export type Pause = { readonly started_at: string; readonly minutes: number };

/** Minutes between two ISO instants. */
export function between(start: string, end: string): number {
  return (Date.parse(end) - Date.parse(start)) / 60_000;
}

/**
 * Where an instant falls, as a percentage of the work done between `start` and `end`: the waiting time is
 * removed, so a night waiting for the decision does not squash the bars of the work. Outside the interval it
 * stops at 0 or 100.
 */
export function workScale(start: string, end: string, pauses: readonly Pause[]): (moment: string) => number {
  const idle = (moment: string) =>
    pauses.reduce((total, pause) => total + Math.min(Math.max(between(pause.started_at, moment), 0), pause.minutes), 0);
  const worked = (moment: string) => between(start, moment) - idle(moment);
  const total = worked(end);
  return (moment) => (total <= 0 ? 0 : Math.min(Math.max((worked(moment) / total) * 100, 0), 100));
}
