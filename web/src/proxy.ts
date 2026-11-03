import type { NextRequest } from "next/server";

import { isLoopbackHost } from "./loopback";

/**
 * Il solo codice fra il browser e le pagine (ADR-0033): rifiuta ogni richiesta con un `Host` che non è loopback.
 * Gira prima delle rewrites, quindi copre anche /api: il proxy di Next.js riscrive l'Host verso Django, che da
 * solo non vedrebbe il nome della pagina ostile. Senza `matcher`, vale per ogni richiesta.
 */
export function proxy(request: NextRequest): Response | undefined {
  if (isLoopbackHost(request.headers.get("host"))) return undefined;
  return new Response("Host non ammesso: il cruscotto risponde solo su 127.0.0.1 e localhost.\n", {
    status: 400,
    headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
  });
}
