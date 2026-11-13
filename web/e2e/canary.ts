/**
 * A fake key, put into the environment of whoever starts the test servers. The commands remove it with `env -u`:
 * the test checks live that it reaches neither Next.js nor Django. It is not a key and opens nothing.
 */
export const CANARY = "e2e-canary-not-a-key";
