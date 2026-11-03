import type { ReactNode } from "react";

import type { ApiError } from "../api/client";

/** Cosa dire per ogni motivo noto; ogni altro stato è una risposta che il cruscotto non si aspetta. */
const REASONS: Readonly<Record<number, { readonly title: string; readonly hint: ReactNode }>> = {
  502: {
    title: "Django non risponde",
    hint: (
      <>
        Avvia l&apos;API con <code>uv run agency-server</code> e ricarica la pagina.
      </>
    ),
  },
  503: { title: "Il registro non si legge", hint: "Il cruscotto mostra i dati appena il registro torna leggibile." },
  504: {
    title: "Django non risponde in tempo",
    hint: (
      <>
        Controlla che <code>agency-server</code> non sia bloccato e ricarica la pagina.
      </>
    ),
  },
};

/** Quando l'API non risponde, o il registro non si legge: si dice perché, senza nascondere il motivo. */
export function Unavailable({ error }: { readonly error: ApiError }) {
  const reason = REASONS[error.status];
  return (
    <section className="notice" role="alert">
      <h1>{reason?.title ?? "L'API non risponde come atteso"}</h1>
      <p>{error.detail}</p>
      {reason !== undefined ? <p>{reason.hint}</p> : null}
    </section>
  );
}
