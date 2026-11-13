/** The invented project of tests/support/dashboard_fixture.py, which every dashboard test runs on. */
export const PROJECT = "officina-e2e";

/** A project's views: the cross-cutting tests (network, cache, Django down, 404) visit them all. */
export const VIEWS = ["", "/phases", "/model", "/quality", "/replay"] as const;

/** The replay view's instance with images: a PNG the dashboard serves, an SVG it does not. */
export const REPLAYED = "T-0002-a1";

/** The earlier project, for the comparison: the same work the day before, with another fingerprint. */
export const BEFORE = "officina-prima";

/** Every page of the dashboard: the project list, a project's views, the comparison. */
export const pages = (project: string = PROJECT): string[] => [
  "/",
  ...VIEWS.map((view) => `/projects/${project}${view}`),
  `/projects/${project}/replay/${REPLAYED}`,
  "/compare",
];
