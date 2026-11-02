/**
 * I tipi dell'API del cruscotto. Nascono da schemas/openapi.json, che nasce dai modelli Pydantic di insights
 * (ADR-0022): qui non si scrive a mano nessuna forma di dato.
 */
import type { operations } from "./schema";

export type * from "./schema";

/** La risposta 200 di un'operazione, per nome: `Ok<"projectReport">` è un ProjectReport. */
export type Ok<Operation extends keyof operations> =
  operations[Operation]["responses"][200]["content"]["application/json"];
