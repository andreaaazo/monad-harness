/**
 * Gli host da cui il cruscotto accetta richieste: gli stessi di `ALLOWED_HOSTS` in Django (ADR-0031). Next.js e
 * Django ascoltano solo su 127.0.0.1, quindi qualunque altro nome è una pagina che ha fatto puntare il suo
 * dominio a quell'indirizzo (DNS rebinding).
 */
const LOOPBACK = new Set(["127.0.0.1", "localhost"]);

/** Vero se l'intestazione `Host` è un host di loopback, con o senza porta. */
export function isLoopbackHost(host: string | null): boolean {
  const match = /^([^:]+)(?::\d+)?$/.exec(host ?? "");
  return match?.[1] !== undefined && LOOPBACK.has(match[1].toLowerCase());
}
