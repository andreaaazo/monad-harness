/**
 * L'unico punto dell'interfaccia che parla con l'API Django. Gira solo sul server di Next.js: le pagine
 * leggono qui e mandano al browser HTML già pronto.
 *
 * Ogni lettura usa `cache: "no-store"`: senza, Next.js potrebbe eseguirla una volta sola e servire dati
 * fermi, o scriverli in .next/cache (ADR-0024). scripts/check-defenses.mjs verifica che nessun altro file
 * chiami fetch.
 */
import type { Ok, Problem } from "./index";

/** Dove ascolta Django. Si legge a ogni richiesta, non quando si costruisce. */
function origin(): string {
  return process.env.AGENCY_API_ORIGIN ?? "http://127.0.0.1:8000";
}

/** Quanto si aspetta Django prima di dire che non risponde. */
const TIMEOUT_MS = 30_000;

/**
 * Una lettura che non è andata, con il motivo. Lo stato è quello di Django; quando Django non risponde,
 * Next.js fa come un proxy: 502 se non risponde affatto, 504 se non risponde in tempo.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
  }
}

function isProblem(body: unknown): body is Problem {
  return typeof body === "object" && body !== null && typeof (body as { detail?: unknown }).detail === "string";
}

async function read<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${origin()}${path}`, {
      cache: "no-store",
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError(504, `Django non ha risposto entro ${TIMEOUT_MS / 1000} s su ${origin()}`);
    }
    throw new ApiError(502, `Django non risponde su ${origin()}`);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, isProblem(body) ? body.detail : response.statusText);
  }
  if (body === null) throw new ApiError(502, `Django ha risposto a ${path} senza un JSON leggibile`);
  return body as T;
}

export const api = {
  projects: () => read<Ok<"listProjects">>("/api/projects"),
  report: (name: string) => read<Ok<"projectReport">>(`/api/projects/${encodeURIComponent(name)}/report`),
  flow: (name: string) => read<Ok<"projectFlow">>(`/api/projects/${encodeURIComponent(name)}/flow`),
  behaviour: (name: string) => read<Ok<"projectBehaviour">>(`/api/projects/${encodeURIComponent(name)}/behaviour`),
  quality: (name: string) => read<Ok<"projectQuality">>(`/api/projects/${encodeURIComponent(name)}/quality`),
  provenance: () => read<Ok<"provenance">>("/api/provenance"),
};
