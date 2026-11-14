# Matrice di parità

Tutto ciò che esiste nel setup Claude Code v1 (`legacy/claude-code-v1/`) e dove arriva nell'harness.
M2 si chiude solo quando ogni riga è `fatto` o `dismesso` con il motivo. `tests/test_registry.py` fallisce se un elemento del backup manca da qui.

Legenda stato: `da portare`, `in corso`, `fatto`, `dismesso`. `fatto` vuol dire che esiste e che un test o una prova reale lo
verifica. Riallineata il 2026-11-01, prima di M2, e il 2026-11-13 dopo l'audit deep-review.

## Ruoli

| Ruolo | Destinazione | Traguardo | Stato |
|---|---|---|---|
| `art-director` | `prompts/roles/art-director.md`, `registry/roles.json` | M2 | da portare |
| `brand-strategist` | `prompts/roles/brand-strategist.md`, `registry/roles.json` | M2 | da portare |
| `copywriter` | `prompts/roles/copywriter.md`, `registry/roles.json` | M2 | da portare |
| `creative-director` | `prompts/roles/creative-director.md`, `registry/roles.json` | M2 | da portare |
| `critic` | `prompts/roles/critic.md`, `registry/roles.json` | M1 | fatto |
| `design-director` | `prompts/roles/design-director.md`, `registry/roles.json` | M1 | fatto |
| `digital-director` | `prompts/roles/digital-director.md`, `registry/roles.json` | M2 | da portare |
| `direction-a` | `prompts/roles/explorer.md`, `registry/roles.json`: oggi esplorano segni, in M2 direzioni complete | M2 | in corso |
| `direction-b` | `prompts/roles/explorer.md`, `registry/roles.json`: oggi esplorano segni, in M2 direzioni complete | M2 | in corso |
| `direction-c` | `prompts/roles/explorer.md`, `registry/roles.json`: oggi esplorano segni, in M2 direzioni complete | M2 | in corso |
| `editorial-designer` | `prompts/roles/editorial-designer.md`, `registry/roles.json` | M2 | da portare |
| `identity-designer` | `prompts/roles/identity-designer.md`, `registry/roles.json` | M1 | fatto |
| `illustrator` | `prompts/roles/illustrator.md`, `registry/roles.json` | M2 | da portare |
| `legal-reviewer` | `prompts/roles/legal-reviewer.md`, `registry/roles.json` | M2 | da portare |
| `mockup-artist` | `prompts/roles/mockup-artist.md`, `registry/roles.json` | M2 | da portare |
| `motion-designer` | `prompts/roles/motion-designer.md`, `registry/roles.json` | M2 | da portare |
| `packaging-designer` | `prompts/roles/packaging-designer.md`, `registry/roles.json` | M2 | da portare |
| `production-director` | `prompts/roles/production-director.md`, `registry/roles.json` | M2 | da portare |
| `production-manager` | `prompts/roles/production-manager.md`, `registry/roles.json` | M2 | da portare |
| `qa-inspector` | `prompts/roles/qa-inspector.md`, `registry/roles.json` | M1 | fatto |
| `researcher` | `prompts/roles/researcher.md`, `registry/roles.json` | M2 | da portare |
| `strategy-director` | `prompts/roles/strategy-director.md`, `registry/roles.json` | M2 | da portare |
| `typographer` | `prompts/roles/typographer.md`, `registry/roles.json` | M2 | da portare |
| `ui-designer` | `prompts/roles/ui-designer.md`, `registry/roles.json` | M2 | da portare |
| `ux-designer` | `prompts/roles/ux-designer.md`, `registry/roles.json` | M2 | da portare |

## Skill

Restano Markdown versionati: il gateway le carica a richiesta.

| Skill | Destinazione | Traguardo | Stato |
|---|---|---|---|
| `brand-guidelines` | `prompts/skills/brand-guidelines/` | M2 | da portare |
| `brand-strategy` | `prompts/skills/brand-strategy/` | M2 | da portare |
| `campaign-social` | `prompts/skills/campaign-social/` | M2 | da portare |
| `client-review` | `prompts/skills/client-review/` | M2 | da portare |
| `client-world` | `prompts/skills/client-world/` | M2 | da portare |
| `color-system` | `prompts/skills/color-system/` | M2 | da portare |
| `concept-divergence` | `prompts/skills/concept-divergence/` | M2 | da portare |
| `critique` | `prompts/skills/critique/` | M1 | fatto |
| `design-agency` | `prompts/skills/design-agency/` | M2 | da portare |
| `design-handoff` | `prompts/skills/design-handoff/` | M2 | da portare |
| `design-preflight` | `prompts/skills/design-preflight/` | M2 | da portare |
| `design-tokens` | `prompts/skills/design-tokens/` | M2 | da portare |
| `direction-sprint` | `prompts/skills/direction-sprint/` | M2 | da portare |
| `editorial-layout` | `prompts/skills/editorial-layout/` | M2 | da portare |
| `illustration-iconography` | `prompts/skills/illustration-iconography/` | M2 | da portare |
| `image-direction` | `prompts/skills/image-direction/` | M2 | da portare |
| `intake` | `prompts/skills/intake/` | M2 | da portare |
| `legal-ip` | `prompts/skills/legal-ip/` | M2 | da portare |
| `logo-design` | `prompts/skills/logo-design/` | M1 | fatto |
| `mockup` | `prompts/skills/mockup/` | M2 | da portare |
| `motion-identity` | `prompts/skills/motion-identity/` | M2 | da portare |
| `packaging` | `prompts/skills/packaging/` | M2 | da portare |
| `presentation` | `prompts/skills/presentation/` | M2 | da portare |
| `print-production` | `prompts/skills/print-production/` | M2 | da portare |
| `production-3d` | `prompts/skills/production-3d/` | M2 | da portare |
| `rebrand` | `prompts/skills/rebrand/` | M2 | da portare |
| `research` | `prompts/skills/research/` | M2 | da portare |
| `type-system` | `prompts/skills/type-system/` | M2 | da portare |
| `ux-design` | `prompts/skills/ux-design/` | M2 | da portare |
| `verbal-identity` | `prompts/skills/verbal-identity/` | M2 | da portare |
| `visual-qa` | `prompts/skills/visual-qa/` | M1 | fatto |
| `web-design` | `prompts/skills/web-design/` | M2 | da portare |
| `web-qa` | `prompts/skills/web-qa/` | M2 | da portare |

## Script e hook

| Elemento | Destinazione | Traguardo | Stato |
|---|---|---|---|
| `budget-guard.py` | `agency.gateway.client`: l'unico vincolo è il budget del cliente (ADR-0015, ADR-0016) | M1 | fatto |
| `budget.py` | `agency.gateway.client`: l'unico vincolo è il budget del cliente (ADR-0015, ADR-0016) | M1 | fatto |
| `client.py` | `agency.graph.gates`, `agency.ledger` | M2 | da portare |
| `contract_lint.py` | `agency.qa` | M2 | da portare |
| `craft-guard.py` | `agency.agents.toolbox`: il campo `craft` dei ruoli è applicato (`tests/test_registry.py`); manca un `app` per strumento, quando arrivano gli altri Craft | M2 | in corso |
| `craft_lock.py` | `agency.workshop.craft` (sostituito da istanze per lavoro, se il collaudo regge) | M3 | da portare |
| `eval_kit.py` | `evals/` | M2 | da portare |
| `evidence.py` | `agency.qa.evidence` | M1 | fatto |
| `facts.py` | `agency.context.facts` | M2 | da portare |
| `identity-guard.py` | gateway: l'attore lo imposta l'harness | M1 | fatto |
| `isolation-guard.py` | `bwrap`: ogni esploratore monta solo la propria cartella | M2 | in corso |
| `master.py` | `agency.workshop.master` | M2 | in corso |
| `node` | `agency.workshop.node` | M2 | da portare |
| `observe-reminder.py` | `agency.agents.toolbox`: niente giudizio senza un'immagine guardata | M1 | fatto |
| `py` | dismesso: `uv run` | M0 | dismesso |
| `render.py` | `agency.workshop.render` | M2 | in corso |
| `render_web.mjs` | `agency.workshop.render` | M2 | da portare |
| `selftest.py` | `tests/` | M2 | in corso |
| `session-start.sh` | `agency.graph`: la ripresa viene dal checkpoint | M1 | fatto |
| `start-agency.sh` | dismesso: `agency` CLI | M2 | dismesso |
| `start-craft.sh` | `agency.workshop.craft`: fatto per VectorCraft, restano gli altri Craft | M2 | in corso |
| `ticket.py` | `agency.ledger`, `agency.contracts.ticket` | M0–M1 | fatto |
| `tools.py` | `agency.doctor` | M0 | fatto |
| `validate_agency.py` | `tests/test_registry.py` | M2 | in corso |
| `workdir.py` | `agency.workshop.files` | M1 | fatto |

## Script delle skill

Diventano strumenti con schema per gli agenti o controlli in `agency.qa`; la logica si riusa.

| Script | Skill | Traguardo | Stato |
|---|---|---|---|
| `world_ingest.py` | `client-world` | M2 | da portare |
| `color.py` | `color-system` | M2 | da portare |
| `tokens_check.py` | `design-tokens` | M2 | da portare |
| `direction_board.py` | `direction-sprint` | M2 | da portare |
| `photo_set.py` | `image-direction` | M2 | da portare |
| `logo_proof.py` | `logo-design` | M1 | fatto |
| `svg_audit.py` | `logo-design` | M1 | fatto |
| `mockup_compose.py` | `mockup` | M2 | da portare |
| `lottie_check.mjs` | `motion-identity` | M2 | da portare |
| `motion_probe.py` | `motion-identity` | M2 | da portare |
| `pdf_preflight.py` | `print-production` | M2 | da portare |
| `cycles_device.py` | `production-3d` | M2 | da portare |
| `pack_render.py` | `production-3d` | M2 | da portare |
| `font_inspect.py` | `type-system` | M2 | da portare |
| `font_library.py` | `type-system` | M2 | da portare |
| `type_scale.py` | `type-system` | M2 | da portare |
| `image_check.py` | `visual-qa` | M2 | da portare |
| `optical_check.py` | `visual-qa` | M1 | fatto |
| `pixel_diff.py` | `visual-qa` | M2 | da portare |
| `svg_parity.py` | `visual-qa` | M1 | fatto |
| `figcraft_audit.py` | `web-design` | M2 | da portare |
| `web_audit.mjs` | `web-qa` | M2 | da portare |

## Documenti e registri

| Documento | Destinazione | Traguardo | Stato |
|---|---|---|---|
| `CAPABILITIES.md` | `prompts/org/CAPABILITIES.md` | M2 | da portare |
| `CLIENT.md` | `prompts/org/CLIENT.md` | M2 | da portare |
| `CRAFT.md` | `prompts/org/CRAFT.md` | M2 | da portare |
| `HANDOFFS.md` | `prompts/org/HANDOFFS.md` | M2 | da portare |
| `ORG.md` | `prompts/org/ORG.md` | M2 | da portare |
| `PLAYBOOK.md` | `prompts/org/PLAYBOOK.md` | M2 | da portare |
| `QA.md` | `prompts/org/QA.md` | M2 | da portare |
| `README.md` | `prompts/org/README.md` | M2 | da portare |
| `ROUTING.md` | `prompts/org/ROUTING.md` | M2 | da portare |
| `SERVICES.md` | `prompts/org/SERVICES.md` | M2 | da portare |
| `SOURCES.md` | `prompts/org/SOURCES.md` | M2 | da portare |
| `TOOLS.md` | `prompts/org/TOOLS.md` | M2 | da portare |
| `checks.json` | `registry/checks.json` | M0 | fatto |
| `budgets.json` | dismesso: i vincoli sono modello e budget del cliente (ADR-0015) | M1.5 | dismesso |
| `tools/registry.json` | `agency.doctor` | M1 | fatto |
| `templates/*`, `references/*` | `prompts/org/` | M2 | da portare |
