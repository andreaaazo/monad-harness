/**
 * Le parole del registro dette in italiano. Sono solo etichette: nessuna regola dello studio sta qui. Una parola
 * che il cruscotto non conosce si mostra com'è scritta nel registro.
 */
import type { Lifecycle } from "./api";

const STATUSES: Readonly<Record<string, string>> = {
  open: "aperto",
  delivered: "consegnato",
  accepted: "accettato",
  rework: "da rifare",
  blocked: "bloccato",
  cancelled: "annullato",
};

/** Un passo nella storia di un ticket: un nome per ogni azione che il registro scrive. */
const STEPS: Readonly<Record<Lifecycle, string>> = {
  open: "aperto",
  deliver: "consegnato",
  accept: "accettato",
  rework: "rimandato",
  block: "bloccato",
  resume: "ripreso",
  cancel: "annullato",
};

/** Perché il modello ha smesso di scrivere: i motivi dell'API Messages. */
const STOPS: Readonly<Record<string, string>> = {
  tool_use: "ha chiesto uno strumento",
  end_turn: "ha finito il turno",
  max_tokens: "tagliata dal limite di token",
  stop_sequence: "sequenza di stop",
  pause_turn: "turno messo in pausa",
  refusal: "rifiuto",
  model_context_window_exceeded: "contesto pieno",
};

/** Lo stato di un ticket che non ha finito: cosa gli manca. */
const PENDING: Readonly<Record<string, string>> = {
  open: "aperto",
  rework: "da rifare",
  delivered: "consegnato, da accettare",
};

export const status = (value: string): string => STATUSES[value] ?? value;
export const pending = (value: string): string => PENDING[value] ?? status(value);
export const step = (value: Lifecycle): string => STEPS[value];
export const stop = (value: string): string => STOPS[value] ?? value;

const SHA256 = /^[0-9a-f]{64}$/;

/** Un valore dell'impronta come lo scrive agency compare: un hash in 12 caratteri, il vuoto è il predefinito. */
export function fingerprintValue(value: string | null): string {
  if (value === null) return "assente";
  if (value === "") return "predefinito";
  return SHA256.test(value) ? value.slice(0, 12) : value;
}
