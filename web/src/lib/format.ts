/** Numbers and dates as a person reads them: in Italian, with the unit beside them. The time zone is always UTC. */

const money = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const whole = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0 });
const tenths = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const percent = new Intl.NumberFormat("it-IT", { style: "percent", maximumFractionDigits: 0 });
const moment = new Intl.DateTimeFormat("it-IT", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" });

/** Dollars with two decimals, in Italian notation: "1,50 $". */
export const usd = (value: number): string => `${money.format(value)} $`;
/** A number rounded to a whole one, in Italian notation. */
export const count = (value: number): string => whole.format(value);
/** A number with its noun, singular or plural: "1 turno", "2 turni". */
export const counted = (value: number, one: string, many: string): string =>
  `${count(value)} ${Math.round(value) === 1 ? one : many}`;
/** A fraction as a whole percentage: 0.25 is "25%". */
export const share = (value: number): string => percent.format(value);
/** A duration in minutes: in tenths below an hour, in hours and minutes from an hour up. */
export function minutes(value: number): string {
  if (Math.round(value * 10) < 600) return `${tenths.format(value)} min`;
  const total = Math.round(value);
  const rest = total % 60;
  return rest === 0 ? `${Math.floor(total / 60)} h` : `${Math.floor(total / 60)} h ${rest} min`;
}
/** A time measured in milliseconds: in seconds below a minute, then as `minutes`. "–" if not measured. */
export function seconds(milliseconds: number | null): string {
  if (milliseconds === null) return "–";
  return Math.round(milliseconds / 100) < 600 ? `${tenths.format(milliseconds / 1000)} s` : minutes(milliseconds / 60_000);
}
/** A text on one line: line breaks become " · ", spaces collapse; past `max` it is cut with "…". */
export function oneLine(text: string, max: number): string {
  const flat = text
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter((line) => line !== "")
    .join(" · ");
  return flat.length <= max ? flat : `${flat.slice(0, max - 1)}…`;
}
/** A difference with its sign, in the value's format: two values that read the same are unchanged. */
export function signed(value: number, format: (value: number) => string): string {
  const size = format(Math.abs(value));
  if (size === format(0)) return "invariato";
  return `${value > 0 ? "+" : "−"}${size}`;
}
/** An instant as a short Italian date and time, in UTC; "–" without one. */
export const when = (iso: string | null): string => (iso === null ? "–" : `${moment.format(new Date(iso))} UTC`);
