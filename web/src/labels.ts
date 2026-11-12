/**
 * The registry's words, said in Italian. They are labels only: no studio rule lives here. A word the dashboard
 * does not know is shown as the registry writes it.
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

/** A step in a ticket's history: a name for each action the registry writes. */
const STEPS: Readonly<Record<Lifecycle, string>> = {
  open: "aperto",
  deliver: "consegnato",
  accept: "accettato",
  rework: "rimandato",
  block: "bloccato",
  resume: "ripreso",
  cancel: "annullato",
};

/** Why the model stopped writing: the Messages API's reasons. */
const STOPS: Readonly<Record<string, string>> = {
  tool_use: "ha chiesto uno strumento",
  end_turn: "ha finito il turno",
  max_tokens: "tagliata dal limite di token",
  stop_sequence: "sequenza di stop",
  pause_turn: "turno messo in pausa",
  refusal: "rifiuto",
  model_context_window_exceeded: "contesto pieno",
};

/** The status of a ticket that has not finished: what it is missing. */
const PENDING: Readonly<Record<string, string>> = {
  open: "aperto",
  rework: "da rifare",
  delivered: "consegnato, da accettare",
};

/** A ticket status in Italian, or the registry's word if it is unknown. */
export const status = (value: string): string => STATUSES[value] ?? value;
/** What an unfinished ticket is missing; any other status as `status` says it. */
export const pending = (value: string): string => PENDING[value] ?? status(value);
/** A step of a ticket's history, in Italian. */
export const step = (value: Lifecycle): string => STEPS[value];
/** A stop reason in Italian, or the API's word if it is unknown. */
export const stop = (value: string): string => STOPS[value] ?? value;

const SHA256 = /^[0-9a-f]{64}$/;

/** A fingerprint value as agency compare writes it: a hash in 12 characters; the empty value is the default. */
export function fingerprintValue(value: string | null): string {
  if (value === null) return "assente";
  if (value === "") return "predefinito";
  return SHA256.test(value) ? value.slice(0, 12) : value;
}

/** How an instance's work closed (`contracts.outcome.OutcomeState`). */
const OUTCOMES: Readonly<Record<string, string>> = {
  delivered: "consegnato",
  handed_off: "passato ad altri ticket",
  selected: "idee scelte",
  no_concept: "nessun concetto",
  presented: "presentato al cliente",
  concept_rejected: "concetto respinto",
  blocked: "bloccato",
};

/** An instance's outcome in Italian, or the word for an instance that has not closed. */
export const outcome = (value: string | null): string => (value === null ? "non chiuso" : (OUTCOMES[value] ?? value));
