import type { NextRequest } from "next/server";

import { isLoopbackHost } from "./loopback";

/**
 * The only code between the browser and the pages (ADR-0033): it refuses every request whose `Host` is not
 * loopback. It runs before the rewrites, so it covers /api too: the Next.js proxy rewrites the Host towards Django,
 * which on its own would not see the hostile page's name. Without a `matcher`, it applies to every request.
 */
export function proxy(request: NextRequest): Response | undefined {
  if (isLoopbackHost(request.headers.get("host"))) return undefined;
  return new Response("Host non ammesso: il cruscotto risponde solo su 127.0.0.1 e localhost.\n", {
    status: 400,
    headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
  });
}
