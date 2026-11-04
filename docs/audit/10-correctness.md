Correctness (COR) at 86f51a1: the ledger core is sound. The hash chain, ticket ids and every write stay serialized under parallel explorers, and timestamps are uniform aware UTC.
The real defects sit at the edges: an evidence guard that ignores which render version was viewed, a budget check that parallel calls race past, and resume steps that commit an effect and its record separately.
Cost accounting ignores billed attempts the API reports outside top-level `usage`, and several crash and boundary paths (brief encoding, torn UTF-8, project names, concurrent runs) leave state stuck or views down.
Critical 0 · High 1 · Medium 7 · Low 8 · Nit 0

Every reproduction below ran from the worktree root with `mise exec -- uv run python /tmp/audit-cor/<script>.py`. Each one
uses temporary directories, a scripted transport and no API key. The scripts are throwaway, so each finding also says
what the script does.

### COR-001 · High · Confirmed
- Where: src/agency/tools/surface.py:412-421 (`_seen_proof`, line 417), src/agency/tools/surface.py:333 (`view_image` key)
- Problem: `observe` and `judge` accept a render that this instance viewed for an *older* version of the file. The system then records PASS evidence for a version nobody looked at, which breaks the rule "un render della versione attuale che questa istanza ha davvero aperto" (ADR-0017).
- Evidence: `view_image` records the key `"<path>:<sha of the image viewed>"`, but `_seen_proof` throws the hash away (`key.rsplit(":", 1)[0]`) and only checks the proof *path*. Render proof paths are fixed per source (`proofs/render/<stem>.png`, render.py:121) and get overwritten on every render. So after render v1 → view → edit → render v2, `renders_of(project, file, sha_v2)` returns that same path, which counts as "viewed". `present_concepts` (surface.py:731) does compare the hash; `_seen_proof` does not.
- Reproduce: `stale_render_seen.py`: a critic context with a red `a.png` runs render, then view_image on the proof. The file becomes black, gets rendered again, and the new render is never viewed. `observe` is then **ACCEPTED**, and the evidence row says "Quadrato rosso…" for the black version.
- Fix: keep the viewed proof hash in the comparison: accept a proof only if `f"{proof}:{sha256(proof)}"` is in `_viewed(ctx)`. Better still, store the proof's sha in `renders` and require that one. Fix risk: Low.

### COR-002 · Medium · Confirmed
- Where: src/agency/gateway/client.py:132-142, src/agency/runtime.py:53, src/agency/graph/workflow.py:84-88
- Problem: parallel calls all pass `authorize` before any of them records usage, so up to `max_parallel` calls go out against the same remaining budget. The declared cap (ADR-0015, ADR-0043) is exceeded every time a budget runs out while explorers or proposals run in parallel.
- Evidence: `authorize` compares `ledger.spent(project) + estimate` with the limit. `spent` only counts rows written by `_record` after a call has finished streaming, and nothing reserves the estimates of calls still in flight. Explorers run as LangGraph `Send` tasks with `max_concurrency = settings.max_parallel` (5) and share one gateway and one ledger.
- Reproduce: `budget_race.py`: budget 0.20 $, and every call costs exactly its estimate (0.085 $). Sequentially, 2 calls go out, 3 are refused, and the spend is 0.170 $. With 5 threads at a barrier, all 5 go out, none is refused, and the spend is **0.425 $** (2.1× the cap).
- Fix: reserve under a lock. Keep an in-memory map of in-flight estimates per project, and authorize against `spent + reserved + estimate`. Release the reservation in `_record` or on error. Fix risk: Med.

### COR-003 · Medium · Confirmed
- Where: src/agency/tools/surface.py:587-624 (`plan_exploration`: 589-592, 618, 619-623), src/agency/tools/surface.py:912-916 and 944-945 (`Toolbox.call`), src/agency/graph/workflow.py:83-88
- Problem: an effect and the record that makes its resume safe are committed in separate transactions. An interruption between them leaves half-written state that resume does not repair. In `plan_exploration` the explorer ticket is opened, but its `concepts` row never gets written, so that direction silently never runs and its ticket stays `open` for good. For the closing tools (`deliver`, `block`, `submit_concept`), the ledger transition commits before `record_operation`. Re-running the tool on resume then hits `IllegalTransition`, and the instance can end `BLOCKED` even though the ticket is delivered. For the root director, the graph then ends with "bloccato".
- Evidence: `ledger.open(..., operation=(f"{operation_id}:{letter}", …))` commits the ticket and its per-letter operation together, and `add_concept` runs after it in a separate transaction. On resume the same `tool_use` is re-run (loop.py:122-127). `stored` is found for that letter, so the code does `continue` and skips `add_concept`. `send_explorers` only reads `ledger.concepts(...)`, so the ticket without a concept row is never sent. In `Toolbox.call` the handler's ledger writes come first and `record_operation(operation_id, …)` second (line 945). The `_restore` replay therefore only works when both have landed.
- Reproduce: `plan_interrupted.py`: `ledger.add_concept` is patched to raise `KeyboardInterrupt` on the 2nd letter, then `plan_exploration` is called again with the same tool_use id. Output: tickets `T-0002, T-0003, T-0004`, concept rows `T-0002, T-0004`, and **`T-0003` is never run**. The window is short (between two commits), but Ctrl-C is the normal way to stop a run.
- Fix: write the concept row inside the same transaction as `open`, for example through an `open(..., concept=…)` variant. For the closing tools, record the operation in the same `_writing()` transaction as the transition, or make the handler idempotent: treat "already DELIVERED by this actor" as done. Fix risk: Med.

### COR-004 · Medium · Confirmed
- Where: src/agency/runtime.py:78-92 (`set_project` line 79 before `brief.read_text` line 82), src/agency/cli.py:136-137, src/agency/runtime.py:107-109
- Problem: `Session.start` saves the project row before it reads the brief and before the graph writes its first checkpoint. A brief that is not UTF-8 (a cp1252 Italian file, for example) therefore crashes after the project exists. From then on, `agency run <name>` refuses ("esiste già") and `agency resume <name>` dies with an uncaught `EmptyInputError` traceback. The project name is unusable from then on.
- Evidence: the order in `start` is copy brief, `set_project` (commit), `brief.read_text(encoding="utf-8")`, then `ledger.open`, `_record` and `graph.invoke`. `_run` refuses whenever `ledger.project(name)` exists. `resume` calls `graph.invoke(None, …)` on a thread with no checkpoint, and `_guarded` only catches `BudgetExceeded` and `anthropic.APIError`. Resume also writes a spurious `runs` row first.
- Reproduce: `brief_encoding.py`: `Session.start` on a cp1252 brief raises `UnicodeDecodeError`. Afterwards the project row exists (budget 5.0), there are no tickets and the checkpoint state is `{}`. `session.resume` then raises `langgraph.errors.EmptyInputError: Received no input for __start__`, and `runs` contains `[(1, 'resume')]`.
- Fix: read and validate the brief (and anything else that can fail) before `set_project`, or write the project row and the root ticket in one transaction after validation. Have `resume` say "nessun lavoro salvato" when the thread has no checkpoint. Fix risk: Low.

### COR-005 · Medium · Confirmed
- Where: src/agency/runtime.py:107-114 and 121-133, src/agency/cli.py:155-162, src/agency/agents/loop.py:63-66 and 112-116
- Problem: nothing stops two engine processes from working on the same project at once, for example two `agency resume` in two terminals. Both run the same instances: each one appends to the same transcript and pays for its own copy of every call. The transcripts this produces are interleaved, and both resume and Replay read them (03-DATA-MODEL: "Perdita grave").
- Evidence: there is no lock per project or per thread id. `Ledger` serializes writes but not work, and the `SqliteSaver` connection takes no exclusive claim. `AgentRunner.run` decides what to do from the transcript alone (`outcome()`, `messages()`), so two processes that start together both see an empty or unfinished transcript.
- Reproduce: `same_project_twice.py`: two threads, each with its own `Ledger` and gateway as two processes would have, run the same ticket. The transcript reads `user, user, assistant, user, assistant, user, assistant, assistant, user, outcome, …, outcome`, and **6 model calls are paid where one worker pays 2**.
- Fix: take an exclusive per-project lock (`fcntl.flock` on `.data/runs/<project>.lock`, or a `BEGIN IMMEDIATE`-guarded claim row) in `open_session` for `run`, `resume` and `decide`, and refuse with a clear message while it is held. Fix risk: Low.

### COR-006 · Medium · Confirmed
- Where: src/agency/insights/adapters/transcripts.py:88-90 (`_entries`), src/agency/agents/transcript.py:44-47 (`ensure_ascii=False`)
- Problem: a transcript whose last line was cut inside a multibyte character (the engine was killed, or is still writing a large line while the dashboard reads) makes `JsonlTranscripts.read()` and `.transcript()` raise `UnicodeDecodeError`. That breaks `agency report`, `agency insights` and every dashboard route, since each rebuild reads all transcripts, until the engine reopens and repairs that instance. The module promises "Una riga tagliata … si conta e si salta".
- Evidence: the engine writes Italian text unescaped (`json.dumps(..., ensure_ascii=False)`, which also covers the `×` in `view_image` notes). `_entries` decodes the whole file with `path.read_text(encoding="utf-8")` *before* its per-line `try`, so the decoding error escapes. `api._projection()` calls `application.current`, which rebuilds on any stamp change, and only `RegistryNotReadable` is mapped to 503. The engine's own `Transcript._repair` handles the same file because it works on bytes.
- Reproduce: `torn_utf8_transcript.py`: a file with one whole line and a second line cut after the first byte of `è`. Both `read()` and `transcript()` raise `UnicodeDecodeError … unexpected end of data`, while `Transcript(path).messages()` returns 1 message.
- Fix: read bytes and decode each line separately (`line.decode("utf-8")` inside the `try`), counting a failure as unreadable, or open with `errors="replace"` only for the last line. Fix risk: Low.

### COR-007 · Medium · Confirmed
- Where: src/agency/tools/render.py:105-106 and 121, src/agency/tools/surface.py:417-420, src/agency/graph/workflow.py:217-222
- Problem: proof names drop the extension, so sources with the same stem share one proof file. A view of one source's render then backs evidence for another. Every proposal ticket declares `proposta-x.vectorcraft`, `proposta-x.svg` and `proposta-x.png` in one folder, and all three render to `proofs/render/proposta-x.png`. A `visual_review` of the PNG export can therefore be signed after looking only at the master's render, which hides exactly the export defects (crop, scale) the check exists for.
- Evidence: `_stem(relative)` is `relative.replace("/", "_").rsplit(".", 1)[0]`. `add_render` registers that shared path for each source's own sha, and `_seen_proof` accepts any registered proof whose path was viewed. Fixing COR-001 alone does not close this, because the viewed bytes *are* the current content of the shared file.
- Reproduce: `proof_name_collision.py`: render a red `x.png`, then a blue `x.jpg`. Both return `['proofs/render/x.png']`, and the proof registered for `x.png` is now blue. After viewing it, `observe x.png` is **ACCEPTED**.
- Fix: keep the extension in the proof name (for example `proposta-x.png.png`, or `<stem>_<ext>.png`), and store the proof's sha256 in `renders` so a proof can be matched to the render that produced it. Fix risk: Low.

### COR-008 · Medium · Likely
- Where: src/agency/gateway/client.py:172-175 and 186-192, src/agency/gateway/pricing.py:132-145, src/agency/gateway/transport.py:44
- Problem: with `fallbacks: "default"` turned on, a request declined mid-stream and then served by the fallback model is billed for both attempts. The gateway only prices and records the top-level `usage`, which (per the claude-api skill, refusal section) "covers only the attempt that produced the returned message". `usage.iterations` holds every attempt. The ledger therefore under-records spend, and the budget allows more than the cap.
- Evidence: `_record` reads `data["usage"]` and `data["model"]` only, and nothing in `src/` or `tests/` reads `iterations` (`rg iterations` finds only the vendored `svg_parity`). The SDK knows about fallbacks (`_beta_messages.py:517-520` relabels the model on a `fallback` block). The response shape comes from the docs: no recorded cassette has a fallback.
- Reproduce: `fallback_usage.py`: a scripted response shaped per the docs (a declined `message` attempt of 50k in / 6k out on opus-5-5, plus a `fallback_message` of 50k in / 3k out on opus-5). Billed by both attempts: 0.645 $. Recorded in `usage`: **0.325 $**. Confirmation against a real fallback needs a live call, which this audit does not make.
- Fix: when `usage.iterations` is present, price each iteration at its own model's rates and store the sum, or one `usage` row per attempt. Add a cassette with a fallback to the tests. Fix risk: Med.

### COR-009 · Low · Suspected
- Where: src/agency/agents/loop.py:152-156 and 171-177
- Problem: after a mid-output fallback, the response `content` can hold the declined attempt's `thinking` and `tool_use` blocks before the `fallback` block. The docs say to omit those blocks when echoing and say they are not continuation context. The loop instead executes every `tool_use` in `content`, including actions the serving model never chose (any tool, even `deliver`), and echoes them back unchanged in the history.
- Evidence: `_run_tools` iterates all blocks with `type == "tool_use"`, and the assistant turn is appended as `response.content`. Nothing in `loop.py` or the gateway looks for a `fallback` block. Suspected because it depends on API behaviour that cannot be reproduced without a live refusal: whether a declined partial carries complete `tool_use` blocks, and whether echoing them is rejected.
- Reproduce: not reproducible offline. A scripted response with `[tool_use A, fallback, tool_use B]` would show both A and B executed, but the shape itself is the open question.
- Fix: in the loop (or the gateway), drop `thinking`, `redacted_thinking` and `tool_use` blocks that appear before the last `fallback` block, both before executing tools and before appending the turn. Fix risk: Med.

### COR-010 · Low · Likely
- Where: src/agency/gateway/client.py:141-142 and 160-167
- Problem: when the SDK raises `ValueError` on malformed streamed tool JSON, `_stream` sends the whole request again, up to 2 more times. The failed attempts were already billed (the full input, and the output up to the failure), but they leave no `usage` row, and the retries are never re-authorized against the budget.
- Evidence: `authorize` runs once in `call`, and `_record` runs once after `_stream` returns. The SDK raises this `ValueError` during accumulation of `input_json_delta` (`anthropic/lib/streaming/_beta_messages.py:541-544`), that is, after generation has started.
- Reproduce: `malformed_retry.py`: a transport that raises that `ValueError` twice and then succeeds. Result: `requests streamed: 3, usage rows: 1, budget checks: 1`. The billing of the failed attempts is API behaviour and was not measured.
- Fix: authorize before each attempt, and record the failed attempts with whatever usage the stream snapshot has (at least the input estimate), marked with a distinct `stop_reason`. Fix risk: Med.

### COR-011 · Low · Likely
- Where: src/agency/agents/loop.py:144-169
- Problem: `stop_reason` values other than `refusal`, `max_tokens`, `tool_use` and `pause_turn` (notably `model_context_window_exceeded`, documented for current models) are handled as a finished answer. The cut-off content is appended and followed by a text reminder. If the truncated content holds a `tool_use` block, the next request carries a `tool_use` with no `tool_result` and gets a 400. Because history is append-only, every later resume repeats that 400.
- Evidence: the final branch (lines 164-169) appends a user string with no `tool_result` for any `tool_use` in `response.content`. CLAUDE.md requires every `stop_reason` to be checked before `content` is read. This one reaches `content` unchecked. With single-use agents and a 1M window it is unlikely to fire.
- Reproduce: not run. The path is clear from the branch structure.
- Fix: give `model_context_window_exceeded` its own branch, handled like `max_tokens` (do not append; block the ticket with the reason), and refuse to append any content that has an unanswered `tool_use` unless tools are run. Fix risk: Low.

### COR-012 · Low · Confirmed
- Where: src/agency/tools/render.py:150
- Problem: two zooms with the same top-left corner but different sizes are written to the same file, so the first zoom is silently replaced. The agent then receives a list that names one path twice and looks at the wrong crop.
- Evidence: `zoom_path = f"{PROOFS}/{_stem(relative)}_zoom_{x:.2f}_{y:.2f}.png"` leaves out `w` and `h`.
- Reproduce: `zoom_collision.py`: zooms `(0.1,0.1,0.1,0.1)` and `(0.1,0.1,0.8,0.8)` on a 400 px image return `['proofs/render/a.png', 'proofs/render/a_zoom_0.10_0.10.png', 'proofs/render/a_zoom_0.10_0.10.png']`. The "first" zoom is 320×320 (the second crop) instead of 40×40.
- Fix: include width and height (or the index) in the zoom name. Fix risk: Low.

### COR-013 · Low · Confirmed
- Where: src/agency/cli.py:305, src/agency/config.py:53-54, src/agency/contracts/layout.py:45-46, src/agency/insights/adapters/transcripts.py:76
- Problem: project names are never validated, yet they become folder names. `../x` makes the engine write outside `projects/` (into the repository, for `../docs`). `acme/v2` nests folders, and its transcripts fall outside `runs/*/*.jsonl`, so the Quality view silently shows no tool calls. `""` puts the work folder at `projects/work`.
- Evidence: `project_dir(slug)` is `(projects_dir / slug).resolve()` and `transcript(project, …)` is `transcripts / project / …`, both without a check. Insights globs exactly one folder level.
- Reproduce: `project_names.py`: `'../fuori'` gives `fuori` (outside `projects/`), `'acme/v2'` gives `projects/acme/v2`, and `''` gives `projects`. With transcripts written for `merlo` and `acme/v2`, the projection's tool calls come only from `['merlo']`.
- Fix: validate the name once at the CLI and in `Session.start` (for example `^[a-z0-9][a-z0-9-]{0,62}$`), and reject anything else before any write. Fix risk: Low.

### COR-014 · Low · Likely
- Where: src/agency/ledger/store.py:139-140, 177 and 203, src/agency/insights/adapters/registry.py:35, src/agency/insights/adapters/projection.py:90
- Problem: ticket ids are `T-{n:04d}` across the whole ledger, and they are sorted as text. From the 10,000th ticket onwards, `T-10000` sorts before `T-9999`, so `children()`, `tickets()` and the insights views list tickets out of creation order. That order feeds the `team` node's run order, the "TICKET FIGLI" packet and `existing[0]` choices.
- Evidence: `ORDER BY tickets.id` / `order_by(TicketRow.id)` on a VARCHAR primary key. Ids are global: `count(*)` over all projects. This is latent; a single project uses far fewer tickets.
- Reproduce: not run. The ordering follows from text comparison of the ids.
- Fix: order by `created_at, rowid` (or a numeric seq), and widen the id format before the next migration. Fix risk: Low.

### COR-015 · Low · Suspected
- Where: src/agency/tools/surface.py:330 and 336-353
- Problem: `view_image` sends the original bytes with the media type guessed from the extension. A misnamed file, such as JPEG bytes saved as `.png` by `compute`, would be sent as `image/png`. If the API rejects the mismatch, that tool result is now part of the append-only history, so every later request and every resume of that instance fails the same way.
- Evidence: `media = IMAGE_MEDIA.get(target.suffix.lower())`, while PIL has already opened the file and knows `image.format`. Suspected because the API's rejection of a mismatched `media_type` was not verified here, which would take a live call.
- Reproduce: not run, since it needs the API.
- Fix: derive the media type from `image.format`, and re-encode to PNG when the format is not one of the four the API accepts. Fix risk: Low.

### COR-016 · Low · Suspected
- Where: src/agency/qa/scripts/svg_audit.py:144-146 (vendored)
- Problem: a stroke set on a `<g>` or `<svg>` and inherited by its paths is never flagged, so a logo built from un-expanded strokes passes `svg_audit`. A `<style>` sheet is not read either.
- Evidence: `stroke` is read only from the element's own attribute or inline style, and the warning is skipped when `tag in ("svg", "g")`. Inheritance is never walked.
- Reproduce: `/tmp/audit-cor/stroked_group.svg` (`<g stroke="#000000" stroke-width="8" fill="none"><path …/></g>`) → `mise exec -- uv run python src/agency/qa/scripts/svg_audit.py /tmp/audit-cor/stroked_group.svg` prints no warning and exits 0. It was reproduced, but it stays Suspected because the script is a byte-identical copy of legacy, and changing it needs the owner's decision.
- Fix: carry the inherited `stroke` down the tree while iterating (and treat a `<style>` element as a warning). Fix risk: Low.

## Checked and found sound

There is no C/C++ in this repository. The following leads were traced and hold:
- **Hash chain and write serialization.** Every chain write runs under the per-instance `RLock` plus `BEGIN IMMEDIATE`, and ticket ids are allocated inside that transaction (store.py:84-105, 138-140). The suite covers both threads and separate `Ledger` instances (`tests/test_hardening.py:305`, `:343`).
- **Sibling explorers when one hits the budget.** LangGraph waits for the other `Send` tasks before raising (checked with a probe graph), so their work is saved before the CLI prints "BUDGET FINITO".
- **Migrations.** They run in one transaction with a backup, and commit only after the chain check.
- **Artifact store.** Content goes to a temporary file in `.incoming/`, is fsynced, and only then renamed to its hash.
- **Idempotent `craft_run`.** It replays its stored result from `.ops/<operation>` on resume.
- **Append-only history.** It is enforced by the transcript. The only rewrite is `_repair` of a torn last line, which was never sent.
- **`stop_reason` before `content`.** It is checked for `refusal` and `max_tokens` before anything is appended, apart from COR-009 and COR-011.
- **Timestamps.** Every ledger timestamp comes from `now()` (aware UTC, seconds), so the string comparisons in insights are safe. `quality.py:134` never compares naive with aware datetimes, and the web formats in UTC.
- **Budget input.** `--budget` and `agency budget` reject zero, negative, `nan`, `inf` and text.
- **Web helpers.** `timescale`, `chart`, `format` and `loopback` handle their empty and zero cases.
