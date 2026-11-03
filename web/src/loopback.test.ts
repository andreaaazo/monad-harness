import assert from "node:assert/strict";
import { test } from "node:test";

import { isLoopbackHost } from "./loopback.ts";

test("gli host di loopback, con o senza porta: gli stessi di ALLOWED_HOSTS in Django", () => {
  for (const host of ["127.0.0.1", "127.0.0.1:3000", "localhost", "localhost:13765", "LOCALHOST:3000"]) {
    assert.equal(isLoopbackHost(host), true, host);
  }
});

test("ogni altro host no: è il nome che una pagina ostile fa puntare a 127.0.0.1", () => {
  for (const host of [
    null,
    "",
    "evil.example",
    "evil.example:3000",
    "127.0.0.1.evil.example",
    "localhost.evil.example:3000",
    "127.0.0.1:3000@evil.example",
    "127.0.0.1:",
    "127.0.0.1:porta",
    "[::1]:3000",
    "192.168.1.20:3000",
  ]) {
    assert.equal(isLoopbackHost(host), false, String(host));
  }
});
