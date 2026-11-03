/**
 * I tipi dell'API del cruscotto. Nascono da schemas/openapi.json, che nasce dai modelli Pydantic di insights
 * (ADR-0022): qui non si scrive a mano nessuna forma di dato.
 */
import type { operations } from "./schema";

export type * from "./schema";

/** Le operazioni che rispondono in JSON: tutte tranne le immagini, che il browser chiede da sé. */
export type JsonOperation = {
  [Name in keyof operations]: operations[Name]["responses"][200]["content"] extends { "application/json": unknown }
    ? Name
    : never;
}[keyof operations];

/** La risposta 200 di un'operazione JSON, per nome: `Ok<"projectReport">` è un ProjectReport. */
export type Ok<Operation extends JsonOperation> = operations[Operation]["responses"][200]["content"]["application/json"];
