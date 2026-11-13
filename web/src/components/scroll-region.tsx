import type { ReactNode } from "react";

/** A table that scrolls sideways: a named region the keyboard can reach and scroll. */
export function ScrollRegion({ label, children }: { readonly label: string; readonly children: ReactNode }) {
  return (
    <div className="scroll" role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}
