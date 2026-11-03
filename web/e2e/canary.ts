/**
 * Una chiave finta, messa nell'ambiente di chi avvia i server di prova. I comandi la tolgono con `env -u`: la
 * prova verifica dal vivo che non arrivi né a Next.js né a Django. Non è una chiave e non apre niente.
 */
export const CANARY = "e2e-canary-not-a-key";
