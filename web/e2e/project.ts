/** Il progetto inventato di tests/dashboard_fixture.py, su cui girano tutte le prove del cruscotto. */
export const PROJECT = "officina-e2e";

/** Le viste di un progetto: le prove trasversali (rete, cache, Django spento, 404) le visitano tutte. */
export const VIEWS = ["", "/phases", "/model", "/quality"] as const;

/** Il progetto di prima, per il confronto: lo stesso lavoro il giorno prima, con un'altra impronta. */
export const BEFORE = "officina-prima";

/** Ogni pagina del cruscotto: l'elenco dei progetti, le viste di un progetto, il confronto. */
export const pages = (project: string = PROJECT): string[] => [
  "/",
  ...VIEWS.map((view) => `/projects/${project}${view}`),
  "/compare",
];
