import { notFound } from "next/navigation";

import { ApiError } from "./client";

/**
 * One read for a page. A 404 becomes the unknown-project page; every other API error comes back, so the page can
 * say what happened. An error that does not come from the API stays an error.
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
