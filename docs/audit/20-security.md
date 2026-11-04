The bwrap profile is sound (clean environment, no network, one writable bind), and the dashboard read side, the SQL and the git history are clean.
The weak point is the harness itself: it trusts paths and files that sandboxed code wrote. A symlinked `.ops` turns `compute` into code execution outside bwrap, and Pillow runs Ghostscript on sandbox-written files on the host.
The other findings are a reviewer-rule bypass, missing resource limits, and smaller perimeter and terminal gaps. No real secret is in the code or the history.
Critical 1 · High 1 · Medium 3 · Low 4 · Nit 0
After review (SUMMARY.md): Critical 1 · High 0 · Medium 4 · Low 4 · Nit 0

# 20 — Security (SEC)

Audited at `86f51a1` on `audit/deep-review`. Threat model as in the brief: model output, client briefs and client files are
untrusted; the dashboard is loopback-only and read-only; the API key must never leave the gateway. Every probe below ran
through the project's own code (`mise exec -- uv run python <script>`, with `PYTHONDONTWRITEBYTECODE=1`), with work dirs
and targets under `/tmp/audit-sec/`. `git status --porcelain` stayed empty after each run.

### SEC-001 · Critical · Confirmed
- Where: src/agency/tools/surface.py:388-393; src/agency/tools/craft.py:106-113; src/agency/ledger/store.py:67; src/agency/ledger/schema.py:57-58
- Problem: `compute` writes the model's code to `work/.ops/compute_<id>.py` without resolving `.ops`, but `.ops` is inside
  the sandbox's writable `/job`. Sandboxed code can replace `.ops` with a symlink to any existing host directory. The next
  `compute` call then makes the harness, outside bwrap, write the model's code there. Dropped into
  `src/agency/ledger/migrations/versions/`, that file is executed by Alembic on the next `Ledger()` open. It runs as the
  operator, with network access and `.env` readable.
- Evidence: `ops = ctx.work / ".ops"; ops.mkdir(exist_ok=True); (ops / name).write_text(a.code)` has no `inside()` and no
  `O_NOFOLLOW`, and `mkdir(exist_ok=True)` accepts a symlink to a directory. `craft_run` does the same with
  `.ops/<op>.steps.json` (craft.py:106-113). Every `Ledger()` calls `schema.ensure_current` → `head()` →
  `ScriptDirectory.from_config(...).get_current_head()`. That call imports every `*.py` in `versions/`, and Alembic runs
  each module before it checks for `revision`. Finding the target is easy. A relative link works without any discovery
  (`../../../src/agency/ledger/migrations/versions` from `projects/<slug>/work/.ops`). Inside the sandbox,
  `/proc/self/mountinfo` also shows the host path behind `/opt/agency-qa`, which is `<repo>/src/agency/qa/scripts`.
  Explorers, proposers, finishers and every author ticket have `compute` (surface.py:829, 836, 851).
- Reproduce: `/tmp/audit-sec/ops_symlink_probe.py` uses the real `Sandbox(work, ~/.local/share/design-agency)` and the real
  `compute` handler (`ctx = SimpleNamespace(work=…, sandbox=…)`), with a scratch copy of `schema.MIGRATIONS` as the target.
  Its steps and output:

  ```text
  step 1 (sandboxed code): read /proc/self/mountinfo; os.rename('/job/.ops', '/job/.ops-old');
                           os.symlink('<copy>/versions', '/job/.ops')
    -> mount /opt/agency-qa <- host root /home/andreaaazo/Dev/design-agency-harness/.worktrees/audit/deep-review/src/agency/qa/scripts
  step 2: compute(code=payload)
    -> exit 2 "can't open file '/job/.ops/compute_inst_toolu_step2.py'"   (the sandbox cannot see it...)
    -> files planted in the host migrations/versions copy: ['compute_inst_toolu_step2.py']   (...the host has it)
  step 3: schema.MIGRATIONS = <copy>; schema.head()   (what Ledger() does on open)
    -> MARKER payload executed by the harness process, outside bwrap
  ```
- Fix: keep the files the harness writes out of `/job`. Write `.ops` content in a harness-owned folder (for example
  `.data/ops/<instance>/`) and bind it read-only into the sandbox, or at least resolve `.ops` with `inside()`, refuse
  `is_symlink()`, and open with `O_NOFOLLOW`. Apply the same rule to every harness-side `work / …` join (see SEC-003).
  Fix risk: Med (craft_run's resume reads its results back from `.ops`).
- Review (SUMMARY.md): Confirmed, Critical. Reproduced end to end with the real Sandbox and `compute`: the payload landed in a host folder and ran when `schema.head()` loaded it; `rg` finds no symlink check in src/. Effort: M.
- Related: SEC-003 (same root cause: the harness follows symlinks planted under `/job`).

### SEC-002 · High · Confirmed
- Where: src/agency/tools/render.py:46,49; src/agency/tools/surface.py:336-341; src/agency/tools/board.py:108,129; src/agency/tools/presentation.py:60; src/agency/evaluation/board.py:121,135
- Problem: the harness opens sandbox-written images with a bare `Image.open`. Pillow chooses the decoder from the file's
  content, not from its suffix. A `schizzo-a.png` that really holds EPS therefore makes Pillow run Ghostscript on the host,
  outside bwrap, on PostScript the model wrote. Pillow's other C decoders (TIFF, PSD, MPO…) also parse untrusted bytes
  inside the harness process.
- Evidence: Pillow 13.0.0 `EpsImagePlugin` runs `gs … -dSAFER` on `load()` (`.venv/…/PIL/EpsImagePlugin.py:144-169`).
  All the call sites above are on the normal path:
  - `render` (the explorer's own tool);
  - `view_image` when it reduces an image;
  - `submit_concept` → `board.mark_problem`;
  - `make_board` → `board.build`;
  - `draft_presentation` and `present()` → `presentation._fit`;
  - `agency judge` → `_raster`.

  Ghostscript inherits the harness's stdout, so the PostScript's output reaches the operator's terminal unfiltered. With
  gs 10.06.0, `-dSAFER` is the only barrier left. In the probe, PostScript could read files under `/tmp` but not a file in
  the repo, and `getenv` was undefined. `view_image` also sends the raw bytes with a media type chosen from the suffix
  (surface.py:330, 353), never checked against `image.format`.
- Reproduce: `/tmp/audit-sec/eps_probe.py` writes EPS text to `/tmp/audit-sec/eps/schizzo-a.png` and calls
  `agency.tools.board.mark_problem`. `/tmp/audit-sec/eps_render_probe.py` calls `render.render_one` on the same file. The
  output is the same for both:

  ```text
  MARKER gs executed model-controlled PostScript on the host
  MARKER same-dir read = file-canary-audit-sec
  MARKER other-dir read = other-dir-canary-audit-sec
  MARKER repo file read denied
  render_one -> ['proofs/render/schizzo-a.png']
  ```
- Fix: add one helper that opens sandbox-written images with `Image.open(path, formats=["PNG", "JPEG", "WEBP"])` (plus GIF
  where it is needed), and use it at every call site. Take `view_image`'s media type from `image.format`. Checked: with that
  allowlist the same file raises `UnidentifiedImageError` and Ghostscript never runs. Fix risk: Low.
- Review (SUMMARY.md): Downgraded to Medium. Reproduced, but gs 10.06 `-dSAFER` limits the PostScript to `/tmp` read and write plus terminal output (repo, home and `/etc` denied). Fix it together with SEC-001. Effort: S.
- Duplicate: the media-type remark is tracked under COR-015; both use one image-opening helper.

### SEC-003 · Medium · Confirmed
- Where: src/agency/tools/presentation.py:221-224,59-60; src/agency/tools/surface.py:710; src/agency/graph/workflow.py:261-263; src/agency/qa/delivery.py:121
- Problem: the presentation collects `proposals/rN/<x>/applicazioni-<x>/*.png` with `Path.glob` and opens each file without
  `inside()`. Delivery expands the same pattern with `glob.glob`, which skips dot-files. A proposer can therefore leave
  `applicazioni-v/.zz.png -> <any host image>`, and delivery never sees it. The host image then appears in the director's
  sheet, in the pages the director views (sent to the API) and in the PDF the client receives. It could be another
  client's file under `projects/`.
- Evidence: `proposal_files` builds raw `work / f"proposals/r{turn}/{letter}"` paths. Pathlib's glob matches names that
  start with a dot, and `_fit` → `Image.open` follows symlinks. `delivery.expected` uses `glob.glob(..., recursive=True)`,
  which leaves those names out. `present()` accepts DELIVERED proposals by itself (workflow.py:256), and acceptance only
  rechecks the delivered files. The proposer's sandbox is exactly that folder, with `compute` (workflow.py:203, 231).
- Reproduce: `/tmp/audit-sec/hidden_glob_probe.py` makes the proposer folder with a real `insegna.png` plus
  `.zz.png -> /tmp/audit-sec/hidden/host-only/secret.png` (solid red):

  ```text
  delivery.expected sees: ['applicazioni-v/insegna.png'] empty: []
  presentation.proposal_files returns: ['proposals/r1/v/applicazioni-v/.zz.png', 'proposals/r1/v/applicazioni-v/insegna.png']
    _fit opened .zz.png real file: /tmp/audit-sec/hidden/host-only/secret.png pixel: (200, 0, 0)
  ```
- Fix: build each proposal's image list from what was delivered (the proposal ticket's `ledger.delivered`, or
  `delivery.expected`), pass every path through `inside()` of the proposal folder, and never glob that folder again.
  Fix risk: Low.
- Review (SUMMARY.md): Confirmed, Medium. Reproduced: the hidden symlinked image enters the presentation but not delivery. Effort: S.
- Related: SEC-001 (same root cause).

### SEC-004 · Medium · Confirmed
- Where: src/agency/tools/surface.py:300-304
- Problem: the rule "a reviewer writes only in reviews/" is checked on the raw string with `startswith("reviews/")`. So
  `reviews/../brief.md` passes, and `inside()` accepts it. A critic, QA inspector or legal reviewer can then rewrite any
  `.md`, `.txt` or `.json` in the work it judges: the client brief, `construction.md`, `explorations/rN/applicazioni.json`.
  The rule exists to prevent exactly that (06-SECURITY, "Autoapprovazione").
- Evidence: reviewers opened with `open_ticket` have no workspace (contracts/ticket.py:102), so their perimeter is the
  whole `work/` folder (agents/loop.py:67).
- Reproduce: `/tmp/audit-sec/reviewer_write_probe.py` calls `write_file` with `actor="critic"`:

  ```text
  brief.md -> refused: un revisore scrive solo in reviews/: non modifica il lavoro che giudica
  reviews/../brief.md -> {'ok': True, 'path': 'reviews/../brief.md'}
  brief.md now: rewritten by a reviewer
  ```
- Fix: compare resolved paths. Require `inside(ctx.work, a.path).is_relative_to(inside(ctx.work, "reviews"))`.
  Fix risk: Low.
- Review (SUMMARY.md): Confirmed, Medium. Reproduced: `reviews/../brief.md` was written by a critic. Effort: S.

### SEC-005 · Medium · Confirmed
- Where: src/agency/tools/sandbox.py:42-43,78-82; src/agency/tools/master.py:64
- Problem: the sandbox has no limit on memory, file size, processes or tmpfs size, and it runs in the operator's own cgroup
  scope. In its 60 s, model-written `compute` code can fill RAM through the heap and the RAM-backed `/tmp` and `/dev/shm`
  (30.5 GiB free each), or fill the project's disk. The host's OOM killer can then hit the harness or the operator's
  desktop.
- Evidence: `subprocess.run(self.argv(command), …, timeout=…)` sets no rlimits, and `--tmpfs` has no `--size`. The harness
  side makes it worse: `master.problem` reads a whole `.blend` file to look at 8 bytes (`path.read_bytes()[:8]`), and
  `view_image` reads files of any size (surface.py:336).
- Reproduce: `/tmp/audit-sec/limits_probe.py` reads the limits from inside the real Sandbox, with no stress test:

  ```text
  RLIMIT_AS soft unlimited hard unlimited      RLIMIT_FSIZE soft unlimited hard unlimited
  RLIMIT_DATA soft unlimited hard unlimited    RLIMIT_CPU soft unlimited hard unlimited
  /tmp free GiB 30.5   /dev/shm free GiB 30.5   /job free GiB 28.7
  cgroup: 0::/user.slice/user-1000.slice/user@1000.service/app.slice/kitty-14146-0.scope
  ```
- Fix: give each `--tmpfs` a `--size` (bwrap 0.11.1 has it), and set rlimits for the bwrap child (`RLIMIT_AS`,
  `RLIMIT_FSIZE`, `RLIMIT_NPROC`) or start it under `systemd-run --user --scope -p MemoryMax=…`. Read only 8 bytes in
  master.py. Fix risk: Med (measure Blender's and the Craft CLIs' memory first).
- Review (SUMMARY.md): Confirmed, Medium. No rlimits inside the real Sandbox, and the tmpfs mounts have no `--size`. Effort: M (measure Blender and the Craft CLIs first).

### SEC-006 · Low · Confirmed
- Where: src/agency/evaluation/board.py:50-73,103-116; src/agency/cli.py:230
- Problem: `agency judge` renders model-produced SVGs with `vectorcraft-cli convert` directly on the host, not in bwrap.
  The environment is cut down to `PATH` and `HOME`, but file access is not limited. An SVG `<image href>` that points to any
  file the operator can read is drawn into `tavola.png`. The blind board can then show content that the studio's sandboxed
  renders never showed, and an untrusted SVG parser runs outside the sandbox.
- Evidence: `render()` calls `subprocess.run([binary, "convert", str(source), …], env=environment)` with no `Sandbox`. The
  `mcp` mode of vectorcraft-cli has `--automation-read-root` to confine reads, but `convert` has no such option
  (`vectorcraft-cli convert --help`).
- Reproduce: `/tmp/audit-sec/svg_href_probe.py` renders three SVGs through `board.vectorcraft()`. Each one references
  `/tmp/audit-sec/hidden/host-only/secret.png` (solid red), as a `file://` URI, a relative path and a plain path:
  `abs/rel/plain rendered, centre pixel: (200, 0, 0, 255)`. Remote `http(s)` hrefs were not tested, because no listener was
  started.
- Fix: run the renderer through `Sandbox`, with the anonymous scratch folder bound as `/job`. Fix risk: Low.

### SEC-007 · Low · Confirmed
- Where: src/agency/qa/delivery.py:98-104; src/agency/contracts/ticket.py:88,96; src/agency/tools/surface.py:506-507
- Problem: `TicketSpec` accepts absolute paths and `..` in `outputs` and `inputs`, and `validate_review` globs
  `work / output` with `recursive=True`. The glob therefore runs outside the perimeter. The refusal depends on whether the
  path exists, so a director can probe for host files, and a pattern like `/**` makes the harness walk the whole
  filesystem.
- Evidence: `pathlib` turns `work / "/abs/path"` into `/abs/path`. `absent` lists only the outputs whose glob found
  nothing, and the refusal names them.
- Reproduce: `/tmp/audit-sec/glob_oracle_probe.py` runs `delivery.validate` and `validate_review` on a critic's review spec
  with an outside output:

  ```text
  /tmp/audit-sec/hidden/host-only/secret.png -> accepted (file exists outside the perimeter)
  ../../hidden/host-only/secret.png -> accepted (file exists outside the perimeter)
  /tmp/audit-sec/hidden/host-only/nope.png -> refused: un revisore non può produrre ['/tmp/audit-sec/hidden/host-only/nope.png']…
  ```
- Fix: add one `TicketSpec` validator that rejects absolute paths and any `..` segment in `outputs`, `inputs` and the
  `checks` patterns. Fix risk: Low.

### SEC-008 · Low · Likely
- Where: src/agency/tools/sandbox.py:33-56
- Problem: bwrap runs without `--new-session`, so sandboxed code keeps the operator's controlling terminal. Where the kernel
  still allows `TIOCSTI` (older kernels, or `dev.tty.legacy_tiocsti=1`), that code can push keystrokes into the operator's
  shell, and they run after the job ends. This is CVE-2017-5226, and bwrap's own manual recommends `--new-session` against
  it.
- Evidence: `/tmp/audit-sec/sandbox_probe.py` shows that `/dev` contains `tty` and that the sandbox has not started a
  session of its own (`os.getsid(0) != os.getpid()`). This machine has `dev.tty.legacy_tiocsti = 0`, which blocks the
  injection here, so the severity is Low.
- Reproduce: not reproducible on this host (the sysctl above blocks `TIOCSTI`, and the tool runner has no tty).
- Fix: add `--new-session` (and consider `--disable-userns`) to `Sandbox.argv` and to `spikes/sandbox_craft.sh`.
  Fix risk: Low (the Craft CLIs and Blender already run with captured pipes).

### SEC-009 · Low · Likely
- Where: src/agency/cli.py:96,117; src/agency/graph/workflow.py:77,299,371
- Problem: model text reaches the operator's terminal unfiltered: the presentation `reasons`, and block notes inside
  `bloccato: …`. A prompt-injected model can embed ESC and OSC sequences that hide or forge lines of the CLI output. In
  terminals that honour OSC 52, it can also write the clipboard.
- Evidence: the data flow. `PresentConcepts.reasons: str` has no character restriction, goes into `ConceptGate.reasons`
  (workflow.py:299), and is printed by `print(gate.reasons)`. `block(reason)` → `outcome.note` → `f"bloccato: {…}"` →
  `print(f"Esito: {outcome}")`. JSON tool input can carry `\u001b`. SEC-002's Ghostscript stdout reaches the same terminal.
- Reproduce: not run end to end: that needs a recorded session reaching a gate with a crafted `reasons`.
- Fix: add one helper that drops C0 and C1 control characters except `\n` and `\t`, and use it on every model-sourced
  string the CLI prints. Fix risk: Low.

## Checked, no finding

- **Sandbox profile**: `--clearenv` keeps a fake `ANTHROPIC_API_KEY` out (only `PATH HOME LANG PWD CLAUDE_PROJECT_DIR` are
  set). Networking fails (`errno 101`). `/usr`, `/opt/agency-qa` and the toolchain are read-only. Only the sandbox's own
  tmpfs mounts and `/job` are writable, and only two PIDs are visible.
- **The `inside()` paths**: `read_file`, `write_file`, `view_image`, `render`, `judge`, `observe`, delivery and keep all
  resolve symlinks and refuse targets outside the work folder. `list_files` and `read_skill` are confined. No two
  sandboxes share a work dir concurrently (`team` runs children one by one).
- **SQL**: every statement in `ledger/` and `insights/adapters/` is a constant or uses parameters. `artifacts_with` uses
  `startswith(..., autoescape=True)` after a hex check.
- **Dashboard**: Django answers only `GET`, checks `ALLOWED_HOSTS` first on every request, reads with
  `mode=ro`/`query_only`, removes the key from its own environment and refuses non-loopback binds. The Replay checks
  instance names against `phase.INSTANCE` and keeps resolved paths under `runs/`, and images are served with
  `nosniff` and `CSP: sandbox`. In Next.js, `proxy.ts` rejects foreign `Host` headers with no `matcher`, every fetch uses
  `no-store`, the web sources use no `dangerouslySetInnerHTML`, and every script removes the key.
- **Docker**: the build contexts are allowlists. The containers run read-only with `cap_drop: ALL` and
  `no-new-privileges`, and only `127.0.0.1:3000` is published.
- **Secrets**: `git log --all -p` (24 commits, `legacy/` included) holds only fake canaries: `sk-ant-prova`,
  `sk-ant-segreto`, `sk-ant-test`, `sk-ant-dal-dotenv` and `sk-ant-non-deve-entrare` (11–23 characters), plus
  `chiave-finta`. No private keys, cloud tokens or Langfuse keys appear, and no `.env` was ever committed (only
  `.env.example`, whose key is empty).
- **Dependencies**: `mise exec -- pnpm --dir web audit` reports one moderate advisory, minimatch <11.0.1
  (GHSA-g3hv-75wg-m249). It is reachable only through the dev tool `openapi-typescript`, on the project's own schema, so
  it cannot be exploited here. Next.js 16.4.2 is past the October 2026 advisories (fixed in 16.4.1), and the Pillow CVEs
  published in 2026 that I found are fixed in 13.0.0. No Python scanner was run, as the brief asks; the other Python pins
  were not checked one by one.
