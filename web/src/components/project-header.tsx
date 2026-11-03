import Link from "next/link";

/** Le viste di un progetto, nell'ordine in cui si leggono. */
const VIEWS = [
  { id: "run", label: "Run", path: "" },
  { id: "phases", label: "Fasi", path: "/phases" },
  { id: "model", label: "Modello", path: "/model" },
] as const;

export type View = (typeof VIEWS)[number]["id"];

/** Il nome del progetto e le sue viste; quella aperta lo dice anche a chi non vede. */
export function ProjectHeader({ project, view }: { readonly project: string; readonly view: View }) {
  const base = `/projects/${encodeURIComponent(project)}`;
  return (
    <header className="project">
      <h1>{project}</h1>
      <nav aria-label="Viste del progetto">
        <ul>
          {VIEWS.map((item) => (
            <li key={item.id}>
              <Link href={`${base}${item.path}`} aria-current={item.id === view ? "page" : undefined}>
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
