/** Numeri e date come li legge una persona: in italiano, con l'unità accanto. Il fuso è sempre UTC. */

const money = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const whole = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0 });
const tenths = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const percent = new Intl.NumberFormat("it-IT", { style: "percent", maximumFractionDigits: 0 });
const moment = new Intl.DateTimeFormat("it-IT", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" });

export const usd = (value: number): string => `${money.format(value)} $`;
export const count = (value: number): string => whole.format(value);
/** Un numero con il suo nome, al singolare o al plurale: "1 turno", "2 turni". */
export const counted = (value: number, one: string, many: string): string =>
  `${count(value)} ${Math.round(value) === 1 ? one : many}`;
export const share = (value: number): string => percent.format(value);
/** Una durata in minuti: in decimi sotto l'ora, in ore e minuti da un'ora in su. */
export function minutes(value: number): string {
  if (Math.round(value * 10) < 600) return `${tenths.format(value)} min`;
  const total = Math.round(value);
  const rest = total % 60;
  return rest === 0 ? `${Math.floor(total / 60)} h` : `${Math.floor(total / 60)} h ${rest} min`;
}
/** Un tempo misurato in millisecondi: in secondi sotto il minuto, poi come `minutes`. "–" se non misurato. */
export function seconds(milliseconds: number | null): string {
  if (milliseconds === null) return "–";
  return Math.round(milliseconds / 100) < 600 ? `${tenths.format(milliseconds / 1000)} s` : minutes(milliseconds / 60_000);
}
/** Un testo su una riga: gli a capo diventano " · ", gli spazi si stringono; oltre `max` si taglia con "…". */
export function oneLine(text: string, max: number): string {
  const flat = text
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter((line) => line !== "")
    .join(" · ");
  return flat.length <= max ? flat : `${flat.slice(0, max - 1)}…`;
}
/** Una differenza con il suo segno, nel formato del valore: due valori che si leggono uguali sono invariati. */
export function signed(value: number, format: (value: number) => string): string {
  const size = format(Math.abs(value));
  if (size === format(0)) return "invariato";
  return `${value > 0 ? "+" : "−"}${size}`;
}
export const when = (iso: string | null): string => (iso === null ? "–" : `${moment.format(new Date(iso))} UTC`);
