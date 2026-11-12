/**
 * The hosts the dashboard accepts requests from: the same as Django's `ALLOWED_HOSTS` (ADR-0031). Next.js and
 * Django listen only on 127.0.0.1, so any other name is a page that pointed its own domain at that address (DNS
 * rebinding).
 */
const LOOPBACK = new Set(["127.0.0.1", "localhost"]);

/** True if the `Host` header is a loopback host, with or without a port. */
export function isLoopbackHost(host: string | null): boolean {
  const match = /^([^:]+)(?::\d+)?$/.exec(host ?? "");
  return match?.[1] !== undefined && LOOPBACK.has(match[1].toLowerCase());
}
