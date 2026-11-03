/** Il progetto inventato di tests/dashboard_fixture.py, su cui girano tutte le prove del cruscotto. */
export const PROJECT = "officina-e2e";

/** Le viste di un progetto: le prove trasversali (rete, cache, Django spento, 404) le visitano tutte. */
export const VIEWS = ["", "/phases", "/model", "/quality"] as const;

/** Ogni pagina del cruscotto per un progetto, a partire dall'elenco dei progetti. */
export const pages = (project: string = PROJECT): string[] => ["/", ...VIEWS.map((view) => `/projects/${project}${view}`)];
