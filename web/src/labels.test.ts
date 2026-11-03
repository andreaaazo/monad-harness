import assert from "node:assert/strict";
import { test } from "node:test";

import { fingerprintValue } from "./labels.ts";

test("un valore dell'impronta si legge come in agency compare", () => {
  assert.equal(fingerprintValue(null), "assente");
  assert.equal(fingerprintValue(""), "predefinito");
  assert.equal(fingerprintValue("a".repeat(64)), "aaaaaaaaaaaa");
  assert.equal(fingerprintValue("vectorcraft 1.0"), "vectorcraft 1.0");
});
