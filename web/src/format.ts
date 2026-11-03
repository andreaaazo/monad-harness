/** Numeri e date come li legge una persona: in italiano, con l'unità accanto. Il fuso è sempre UTC. */

const money = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const whole = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0 });
const tenths = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const percent = new Intl.NumberFormat("it-IT", { style: "percent", maximumFractionDigits: 0 });
const moment = new Intl.DateTimeFormat("it-IT", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" });

export const usd = (value: number): string => `${money.format(value)} $`;
export const count = (value: number): string => whole.format(value);
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
export const when = (iso: string | null): string => (iso === null ? "–" : `${moment.format(new Date(iso))} UTC`);
