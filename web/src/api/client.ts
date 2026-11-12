/**
 * The only part of the interface that talks to the Django API. It runs only on the Next.js server: the pages read
 * here and send the browser ready-made HTML.
 *
 * Every read uses `cache: "no-store"`: without it, Next.js could run it once and serve stale data, or write it
 * into .next/cache (ADR-0024). scripts/check-defenses.mjs checks that no other file calls fetch.
 */
import type { Ok, Problem } from "./index";

/** Where Django listens. Read on every request, not at build time. */
function origin(): string {
  return process.env.AGENCY_API_ORIGIN ?? "http://127.0.0.1:8000";
}

/** How long to wait for Django before saying it does not answer. */
const TIMEOUT_MS = 30_000;

/**
 * A read that failed, with its reason. The status is Django's; when Django does not answer, Next.js acts as a
 * proxy would: 502 if it does not answer at all, 504 if it does not answer in time.
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

/** The dashboard's reads: one per JSON operation of the Django API, typed by the OpenAPI schema. */
export const api = {
  projects: () => read<Ok<"listProjects">>("/api/projects"),
  report: (name: string) => read<Ok<"projectReport">>(`/api/projects/${encodeURIComponent(name)}/report`),
  flow: (name: string) => read<Ok<"projectFlow">>(`/api/projects/${encodeURIComponent(name)}/flow`),
  behaviour: (name: string) => read<Ok<"projectBehaviour">>(`/api/projects/${encodeURIComponent(name)}/behaviour`),
  quality: (name: string) => read<Ok<"projectQuality">>(`/api/projects/${encodeURIComponent(name)}/quality`),
  replay: (name: string, instance: string) =>
    read<Ok<"instanceReplay">>(
      `/api/projects/${encodeURIComponent(name)}/instances/${encodeURIComponent(instance)}/replay`,
    ),
  compare: (before: string, after: string) =>
    read<Ok<"compareProjects">>(
      `/api/compare?before=${encodeURIComponent(before)}&after=${encodeURIComponent(after)}`,
    ),
  provenance: () => read<Ok<"provenance">>("/api/provenance"),
};

/**
 * The paths the browser requests itself, from Next.js, which forwards them to Django through the rewrites
 * (ADR-0033): a transcript's images. They do not go through `fetch`, so not through the Next.js server either.
 */
export const browserPaths = {
  image: (name: string, instance: string, index: number) =>
    `/api/projects/${encodeURIComponent(name)}/instances/${encodeURIComponent(instance)}/images/${index}`,
};
