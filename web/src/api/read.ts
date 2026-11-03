import { notFound } from "next/navigation";

import { ApiError } from "./client";

/**
 * Una lettura per una pagina. Un 404 è la pagina del progetto sconosciuto; ogni altro errore dell'API torna
 * indietro, perché la pagina dica cosa è successo. Un errore che non viene dall'API resta un errore.
 */
export async function readForPage<T>(read: () => Promise<T>): Promise<T | ApiError> {
  try {
    return await read();
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    if (error instanceof ApiError) return error;
    throw error;
  }
}
