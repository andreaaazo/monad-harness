/**
 * The dashboard API's types. They come from schemas/openapi.json, which comes from the insights Pydantic models
 * (ADR-0022): no data shape is written by hand here.
 */
import type { operations } from "./schema";

export type * from "./schema";

/** The operations that answer in JSON: all of them but the images, which the browser requests itself. */
export type JsonOperation = {
  [Name in keyof operations]: operations[Name]["responses"][200]["content"] extends { "application/json": unknown }
    ? Name
    : never;
}[keyof operations];

/** The 200 response of a JSON operation, by name: `Ok<"projectReport">` is a ProjectReport. */
export type Ok<Operation extends JsonOperation> = operations[Operation]["responses"][200]["content"]["application/json"];
