#!/usr/bin/env python3
"""Autotest dello studio: ricrea casi di prova in una cartella temporanea e verifica che ogni
script dia l'esito atteso, sia sui casi buoni sia su quelli sbagliati apposta.

  .claude/scripts/py .claude/scripts/selftest.py [--keep] [--only colore,web,…]

Da eseguire dopo ogni aggiornamento della toolchain o degli script. Esce con 1 se un test fallisce.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[1]
ROOT = CLAUDE.parent
PY = str(CLAUDE / "scripts/py")
NODE = str(CLAUDE / "scripts/node")
SK = CLAUDE / "skills"
results = []
TEST_ENV = None  # impostato in main: ogni script scrive nel progetto di prova, mai nel template


def run(cmd, env=None, cwd=None, inp=None, timeout=300):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, env=env or TEST_ENV,
                       cwd=cwd, input=inp, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def check(group, name, cond, detail=""):
    results.append((group, name, bool(cond), detail))
    print(f"{'ok  ' if cond else 'FAIL'} [{group}] {name}" + (f" — {detail}" if detail and not cond else ""))


def t_colore(tmp, env):
    for fg, bg, want in (("#888888", "#FFFFFF", "63.1"), ("#FFFFFF", "#888888", "-68.5"),
                         ("#B184FF", "#FEFCFF", "51.6"), ("#B184FF", "#030306", "-48.8")):
        _, out = run([PY, SK / "color-system/scripts/color.py", "--json", "contrast", fg, bg])
        lc = json.loads(out)[0]["apca_lc"]
        check("colore", f"APCA {fg} su {bg} = {want}", f"{lc:.1f}" == want, f"ottenuto {lc}")
    (tmp / "cvd.json").write_text(json.dumps({"blu": "#2E90FA", "viola": "#B184FF"}))
    _, out = run([PY, SK / "color-system/scripts/color.py", "cvd", tmp / "cvd.json"])
    check("colore", "cvd segnala blu/viola confondibili", "CONFONDIBILE" in out)


def t_tipo(tmp, env):
    code, out = run([PY, SK / "type-system/scripts/type_scale.py", "--base", "16", "--ratio", "major-third",
                     "--steps", "0:2", "--dtcg"])
    (tmp / "ts.json").write_text(out)
    code2, _ = run([PY, SK / "design-tokens/scripts/tokens_check.py", tmp / "ts.json"])
    check("tipo", "scala → token DTCG validi", code == 0 and code2 == 0)
    font = next((l.split(":")[0] for l in run(["fc-list", ":", "file"])[1].splitlines() if l.strip().endswith((".ttf:", ".otf:"))), None)
    if font:
        code, out = run([PY, SK / "type-system/scripts/font_inspect.py", font, "--langs", "it,en", "--sample", "Città"])
        check("tipo", "font_inspect legge metriche e copertura", code == 0 and "coverage" in out)


def t_token(tmp, env):
    (tmp / "bad.json").write_text(json.dumps({"c": {"$type": "color", "a": {"$value": "{c.nope}"}}}))
    code, _ = run([PY, SK / "design-tokens/scripts/tokens_check.py", tmp / "bad.json"])
    check("token", "alias rotto → errore", code == 1)


def t_svg(tmp, env):
    good = tmp / "good.svg"
    good.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                    '<path fill="#000" d="M10 90 A40 40 0 0 1 90 90 H60 L50 60 L40 90 Z"/></svg>')
    bad = tmp / "bad.svg"
    bad.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                   '<path d="M10 10 L90 10 L90.1 50 Z" stroke="red"/></svg>')
    check("svg", "svg_audit pulito → PASS", run([PY, SK / "logo-design/scripts/svg_audit.py", good])[0] == 0)
    code, out = run([PY, SK / "logo-design/scripts/svg_audit.py", bad])
    check("svg", "svg_audit trova quasi-allineamento e tratto", code == 1 and "quasi" in out and "tratto" in out)
    code, _ = run([PY, SK / "logo-design/scripts/logo_proof.py", "proof", good, "--out", tmp / "proofs"])
    check("svg", "logo_proof produce il foglio", code == 0 and (tmp / "proofs/good_proof.png").exists())
    check("svg", "svg_parity pulito → PASS", run([PY, SK / "visual-qa/scripts/svg_parity.py", good])[0] == 0)
    filt = tmp / "filter.svg"
    filt.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><filter id="b">'
                    '<feGaussianBlur stdDeviation="4"/></filter></defs><circle cx="50" cy="50" r="30" filter="url(#b)"/></svg>')
    check("svg", "svg_parity con filtro → FAIL", run([PY, SK / "visual-qa/scripts/svg_parity.py", filt])[0] == 1)


def t_immagini(tmp, env):
    code, _ = run([PY, "-c", f"""
from PIL import Image, ImageDraw
s=Image.new('RGB',(1200,800),(90,70,60)); ImageDraw.Draw(s).polygon([(330,170),(930,230),(880,690),(260,610)],fill=(236,232,224)); s.save(r'{tmp}/scene.png')
Image.new('RGBA',(800,800),(20,20,26,255)).save(r'{tmp}/sq.png'); Image.new('RGBA',(1104,800),(20,20,26,255)).save(r'{tmp}/fit.png')
"""])
    quad = "330,170 930,230 880,690 260,610"
    m = SK / "mockup/scripts/mockup_compose.py"
    check("immagini", "mockup rifiuta artwork deformato",
          run([PY, m, "--scene", tmp / "scene.png", "--art", tmp / "sq.png", "--quad", quad, "--out", tmp / "m.png"])[0] == 1)
    check("immagini", "mockup accetta proporzioni corrette",
          run([PY, m, "--scene", tmp / "scene.png", "--art", tmp / "fit.png", "--quad", quad, "--out", tmp / "m.png"])[0] == 0)
    check("immagini", "image_check segnala dimensioni errate",
          run([PY, SK / "visual-qa/scripts/image_check.py", tmp / "m.png", "--expect", "100x100"])[0] == 1)
    check("immagini", "pixel_diff trova regressione fuori regione",
          run([PY, SK / "visual-qa/scripts/pixel_diff.py", tmp / "scene.png", tmp / "m.png", "--expect-region", "0,0,10,10"])[0] == 1)


def t_pdf(tmp, env):
    run([PY, "-c", f"""
import pymupdf as fitz
from PIL import Image
Image.new('RGB',(100,100),(200,40,40)).save(r'{tmp}/low.png')
d=fitz.open(); mm=72/25.4; p=d.new_page(width=216*mm,height=303*mm)
p.set_trimbox(fitz.Rect(3*mm,3*mm,213*mm,300*mm)); p.insert_text((40*mm,60*mm),'Prova',fontsize=30,fontname='helv')
p.insert_image(fitz.Rect(30*mm,100*mm,180*mm,250*mm),filename=r'{tmp}/low.png'); d.save(r'{tmp}/t.pdf')
"""])
    code, out = run([PY, SK / "print-production/scripts/pdf_preflight.py", tmp / "t.pdf", "--print"])
    check("pdf", "preflight trova font non incorporato e bassa risoluzione",
          code == 1 and "non incorporato" in out and "ppi" in out)


def t_motion(tmp, env):
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "color=c=black:s=160x90:d=2:r=30,geq=lum='if(lt(mod(N,6),3),235,16)':cb=128:cr=128", "-pix_fmt", "yuv420p", tmp / "f.mp4"])
    check("motion", "motion_probe segnala flash", run([PY, SK / "motion-identity/scripts/motion_probe.py", tmp / "f.mp4"])[0] == 1)
    code, _ = run(["effectcraft-cli", "run", "file.exportLottie", json.dumps({"path": str(tmp / "demo.json")}), "--demo"], timeout=180)
    if (tmp / "demo.json").exists():
        code, out = run([NODE, SK / "motion-identity/scripts/lottie_check.mjs", tmp / "demo.json", "--out", tmp / "lottie", "--frames", "0,1"])
        check("motion", "Lottie esportato da EffectCraft si rende con lottie-web", code == 0)
    else:
        check("motion", "export Lottie demo da EffectCraft", False, "effectcraft-cli non ha prodotto il file")


def t_web(tmp, env):
    (tmp / "p.html").write_text('<!doctype html><html lang="it"><head><meta charset="utf-8"></head><body>'
                                '<div style="width:1400px;font-family:Brand Sans">x</div><img src="x.png"></body></html>')
    code, out = run([NODE, SK / "web-qa/scripts/web_audit.mjs", tmp / "p.html", "--out", tmp / "web", "--widths", "360"], timeout=240)
    check("web", "web_audit trova overflow, alt, font mancante", code == 1 and "overflow" in out and "Brand Sans" in out)


def t_governance(tmp, env):
    s = CLAUDE / "scripts"
    code, _ = run([sys.executable, CLAUDE / "hooks/craft-guard.py"], env=env, inp=json.dumps({"tool_name": "mcp__vectorcraft__x"}))
    check("governance", "craft-guard blocca senza lock", code == 2)
    run([sys.executable, s / "craft_lock.py", "acquire", "vectorcraft", "identity-designer", "doc"], env=env)
    code, _ = run([sys.executable, CLAUDE / "hooks/craft-guard.py"], env=env,
                  inp=json.dumps({"tool_name": "mcp__vectorcraft__x", "agent_type": "motion-designer"}))
    check("governance", "craft-guard blocca un altro agente", code == 2)
    code, _ = run([sys.executable, CLAUDE / "hooks/craft-guard.py"], env=env,
                  inp=json.dumps({"tool_name": "mcp__vectorcraft__x", "agent_type": "identity-designer"}))
    check("governance", "craft-guard ammette il titolare", code == 0)
    run([sys.executable, s / "craft_lock.py", "release", "vectorcraft", "identity-designer"], env=env)
    (tmp / "work").mkdir(exist_ok=True)
    f = tmp / "work/direction.md"
    f.write_text("A")
    from PIL import Image
    Image.new("RGB", (10, 10)).save(tmp / "work/esempio.png")
    common = ["--from", "router", "--to", "design-director", "--type", "produzione", "--title", "t",
              "--request", "r", "--inputs", "work/esempio.png", "--outputs", "work/out.md", "--accept", "facts_check",
              "--medium", "nessuno", "--medium-why", "solo un testo di prova", "--after-gate", "direction"]
    check("governance", "ticket oltre un gate non approvato → rifiutato",
          run([sys.executable, s / "ticket.py", "new", *common], env=env)[0] == 1)
    run([sys.executable, s / "client.py", "approve", "--gate", "direction", "--files", "work/direction.md", "--text", "ok la A"], env=env)
    check("governance", "ticket dopo approvazione → accettato",
          run([sys.executable, s / "ticket.py", "new", *common], env=env)[0] == 0)
    f.write_text("B")
    check("governance", "approvazione scade se il file cambia",
          run([sys.executable, s / "client.py", "gate", "direction"], env=env)[0] == 1)
    run([sys.executable, s / "evidence.py", "record", "--file", "work/direction.md", "--check", "facts_check", "--result", "PASS", "--by", "qa-inspector"], env=env)
    check("governance", "prova fresca → gate superato",
          run([sys.executable, s / "evidence.py", "gate", "work/direction.md", "--require", "facts_check"], env=env)[0] == 0)
    f.write_text("C")
    check("governance", "prova STALE dopo modifica → gate bloccato",
          run([sys.executable, s / "evidence.py", "gate", "work/direction.md", "--require", "facts_check"], env=env)[0] == 1)
    code, out = run([sys.executable, s / "client.py", "ask", "--from", "router", "--question", "q?", "--why", "w", "--blocking"], env=env)
    _, status = run(["bash", CLAUDE / "hooks/session-start.sh"], env=env)
    check("governance", "hook di avvio mostra le domande aperte al cliente", "BLOCCANTE" in status)


def t_contratto(tmp, env):
    s = CLAUDE / "scripts"
    (tmp / "work").mkdir(exist_ok=True)
    (tmp / "work/brief.md").write_text("brief v1")
    T = lambda *a: run([sys.executable, s / "ticket.py", *a], env=env)
    base = ("--from", "router", "--to", "ui-designer", "--type", "produzione", "--title", "t", "--request", "r",
            "--medium", "nessuno", "--medium-why", "prova senza master")
    check("contratto", "ticket di produzione senza --outputs → rifiutato", T("new", *base, "--accept", "facts_check")[0] == 1)
    check("contratto", "--accept none su produzione → rifiutato", T("new", *base, "--outputs", "work/o.png", "--accept", "none")[0] == 1)
    code, out = T("new", *base, "--inputs", "work/brief.md", "--outputs", "work/o.png", "work/o.md",
                  "--accept", "*.png=visual_review", "o.md=facts_check")
    tid = out.strip().splitlines()[-1]
    D = lambda *a: T("deliver", tid, "--by", "ui-designer", *a)
    check("contratto", "consegna con output mancanti → rifiutata", D()[0] == 1)
    from PIL import Image
    Image.new("RGB", (40, 40), (10, 10, 10)).save(tmp / "work/o.png")
    (tmp / "work/o.md").write_text("x [F-0001]")
    check("contratto", "consegna senza prove di accettazione → rifiutata", D()[0] == 1)
    E = lambda *a: run([sys.executable, s / "evidence.py", *a], env=env)
    check("contratto", "visual_review senza render della versione attuale → rifiutato",
          E("record", "--file", "work/o.png", "--check", "visual_review", "--result", "PASS", "--by", "ui-designer", "--proof", "work/o.png")[0] == 1)
    run([PY, s / "render.py", "work/o.png", "--out", "work/proofs"], env=env, cwd=tmp)
    check("contratto", "visual_review con render della versione attuale → accettato",
          E("record", "--file", "work/o.png", "--check", "visual_review", "--result", "PASS", "--by", "ui-designer",
            "--proof", "work/proofs/o_preview.png")[0] == 0)
    E("record", "--file", "work/o.md", "--check", "facts_check", "--result", "PASS", "--by", "ui-designer")
    Image.new("RGB", (60, 40), (200, 10, 10)).save(tmp / "work/n.png")
    check("contratto", "observe rifiuta una descrizione vuota",
          E("observe", "work/n.png", "--by", "qa-inspector", "--seen", "ok")[0] == 1)
    code1, _ = E("observe", "work/n.png", "--by", "qa-inspector", "--seen", "Rettangolo rosso pieno 60×40, bordi netti, nessun testo né difetto visibile.")
    code2, _ = E("observe", "work/n.png", "--by", "qa-inspector", "--seen", "Rettangolo rosso pieno 60×40, bordi netti, nessun testo né difetto visibile.")
    check("contratto", "observe: prima rende e chiede di guardare, poi registra", code1 == 1 and code2 == 0)
    (tmp / "work/brief.md").write_text("brief v2")
    check("contratto", "input cambiato durante il lavoro → consegna rifiutata", D()[0] == 1)
    check("contratto", "input cambiato dichiarato → consegna accettata", D("--input-change", "il brief v2 cambia solo la scadenza")[0] == 0)
    _, out = T("lineage", "work/o.png")
    check("contratto", "lineage indica il ticket che ha prodotto la versione attuale", tid in out and "versione attuale" in out)


def t_stati(tmp, env):
    s = CLAUDE / "scripts"
    T = lambda *a: run([sys.executable, s / "ticket.py", *a], env=env)
    E = lambda *a: run([sys.executable, s / "evidence.py", *a], env=env)
    (tmp / "work/s").mkdir(parents=True, exist_ok=True)
    base = ("--from", "design-director", "--to", "identity-designer", "--type", "produzione", "--title", "t", "--request", "r",
            "--medium", "nessuno", "--medium-why", "prova senza master")
    # Copertura degli output: il difetto trovato nella prova reale.
    check("stati", "cartella come output → rifiutata", T("new", *base, "--outputs", "work/s", "--accept", "*.png=visual_review")[0] == 1)
    check("stati", "pattern che non colpisce nessun output → rifiutato",
          T("new", *base, "--outputs", "work/s/a.md", "--accept", "*.png=visual_review", "a.md=facts_check")[0] == 1)
    check("stati", "output senza controlli → rifiutato",
          T("new", *base, "--outputs", "work/s/a.md", "work/s/b.md", "--accept", "a.md=facts_check")[0] == 1)
    check("stati", "controllo sconosciuto → rifiutato", T("new", *base, "--outputs", "work/s/a.md", "--accept", "r1_no_text")[0] == 1)
    check("stati", "produzione senza mezzo → rifiutata",
          T("new", "--from", "design-director", "--to", "identity-designer", "--type", "produzione", "--title", "t",
            "--request", "r", "--outputs", "work/s/a.md", "--accept", "facts_check")[0] == 1)
    check("stati", "esenzione senza motivo → rifiutata",
          T("new", *base, "--outputs", "work/s/a.md", "work/s/b.md", "--accept", "a.md=facts_check", "--exempt", "work/s/b.md=x")[0] == 1)
    code, out = T("new", *base, "--outputs", "work/s/*.md", "--accept", "*.md=facts_check+req:peso_massimo")
    tid = out.strip().splitlines()[-1]
    check("stati", "glob e requisito di progetto req: → accettati", code == 0)
    check("stati", "glob senza file → consegna rifiutata", T("deliver", tid, "--by", "identity-designer")[0] == 1)
    (tmp / "work/s/a.md").write_text("A")
    (tmp / "work/s/b.md").write_text("B")
    E("record", "--file", "work/s/a.md", "--check", "facts_check", "--result", "PASS", "--by", "identity-designer")
    E("record", "--file", "work/s/a.md", "--check", "req:peso_massimo", "--result", "PASS", "--by", "identity-designer")
    code, out = T("deliver", tid, "--by", "identity-designer")
    check("stati", "glob espanso: il file senza prove blocca la consegna", code == 1 and "b.md" in out)
    for f in ("a", "b"):
        for c in ("facts_check", "req:peso_massimo"):
            E("record", "--file", f"work/s/{f}.md", "--check", c, "--result", "PASS", "--by", "identity-designer")
    check("stati", "la consegna spetta al destinatario", T("deliver", tid, "--by", "motion-designer")[0] == 1)
    check("stati", "consegna regolare → delivered", T("deliver", tid, "--by", "identity-designer")[0] == 0)
    check("stati", "accettare spetta al mittente", T("accept", tid, "--by", "identity-designer")[0] == 1)
    check("stati", "rework con motivo", T("rework", tid, "--by", "design-director", "--reason", "T-9 ha trovato un difetto")[0] == 0)
    check("stati", "dopo il rework si riconsegna", T("deliver", tid, "--by", "identity-designer")[0] == 0)
    check("stati", "accept → accepted", T("accept", tid, "--by", "design-director")[0] == 0)
    data = json.loads((tmp / f".agency/tickets/{tid}.json").read_text())
    check("stati", "la storia registra attore ed evento", [h["event"] for h in data["history"]] ==
          ["open", "delivered", "rework", "delivered", "accepted"] and data["history"][-1]["by"] == "design-director")
    check("stati", "il vecchio comando close non esiste più", T("close", tid, "--result", "DONE")[0] != 0)
    _, listed = T("list", "--open")
    check("stati", "un ticket accepted non è tra gli aperti", tid not in listed)
    # Autore e revisore.
    (tmp / "work/s/m.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    code, out = T("new", *base, "--outputs", "work/s/m.svg", "--accept", "critique+svg_audit")
    prod = out.strip().splitlines()[-1]
    run([PY, s / "render.py", "work/s/m.svg", "--out", "work/proofs"], env=env, cwd=tmp)
    (tmp / "work/s/ref.png").write_bytes((tmp / "work/proofs/m.png").read_bytes())
    why = "Il confronto con il riferimento mostra spessori più coerenti e un'apertura più netta del segno precedente."
    J = lambda by, res="PASS", *a: E("judge", "work/s/m.svg", "--compare", "work/s/ref.png", "--why", why, "--by", by, "--check", "critique", "--result", res, *a)
    check("stati", "l'autore non firma un controllo indipendente", J("identity-designer")[0] == 1)
    check("stati", "un ruolo non ammesso non firma la critica", J("copywriter")[0] == 1)
    check("stati", "giudizio con record invece di judge → rifiutato",
          E("record", "--file", "work/s/m.svg", "--check", "critique", "--result", "PASS", "--by", "critic")[0] == 1)
    check("stati", "--by inventato → rifiutato", E("record", "--file", "work/s/m.svg", "--check", "svg_audit", "--result", "PASS", "--by", "qa")[0] == 1)
    E("record", "--file", "work/s/m.svg", "--check", "svg_audit", "--result", "PASS", "--by", "identity-designer")
    check("stati", "i controlli indipendenti non bloccano la consegna dell'autore", T("deliver", prod, "--by", "identity-designer")[0] == 0)
    code, out = T("accept", prod, "--by", "design-director")
    check("stati", "accettazione senza il controllo indipendente → rifiutata", code == 1 and "critique" in out)
    J("critic", "FAIL")
    J("art-director", "PASS")
    code, out = E("gate", "work/s/m.svg", "--require", "critique")
    check("stati", "il PASS di un altro non copre un FAIL sulla stessa versione", code == 1)
    J("critic", "PASS")
    check("stati", "il firmatario può cambiare il proprio FAIL", T("accept", prod, "--by", "design-director")[0] == 0)
    # Revisione: verdetto separato dallo stato.
    code, out = T("new", "--from", "design-director", "--to", "qa-inspector", "--type", "qa", "--title", "qa", "--request", "r",
                  "--inputs", "work/s/m.svg", "--outputs", "work/s/m.svg", "work/s/qa.md", "--accept", "*.svg=svg_audit")
    qa = out.strip().splitlines()[-1]
    (tmp / "work/s/qa.md").write_text("referto")
    check("stati", "ticket qa senza verdetto → rifiutato", T("deliver", qa, "--by", "qa-inspector")[0] == 1)
    code, out = T("deliver", qa, "--by", "qa-inspector", "--verdict", "READY")
    check("stati", "le prove dell'autore non soddisfano il QA", code == 1 and "qa-inspector" in out)
    E("record", "--file", "work/s/m.svg", "--check", "svg_audit", "--result", "FAIL", "--by", "qa-inspector")
    check("stati", "verdetto READY con un FAIL → rifiutato", T("deliver", qa, "--by", "qa-inspector", "--verdict", "READY")[0] == 1)
    code, out = T("deliver", qa, "--by", "qa-inspector", "--verdict", "REVISE", "--note", "svg_audit fallito")
    check("stati", "verdetto REVISE: il lavoro di revisione è consegnato", code == 0 and "delivered" in out and "REVISE" in out)
    check("stati", "--verdict su una produzione → rifiutato", T("deliver", prod, "--by", "identity-designer", "--verdict", "READY")[0] == 1)


def hook(name, env, event):
    return run([sys.executable, CLAUDE / "hooks" / name], env=env, inp=json.dumps(event))


def t_identita(tmp, env):
    G = lambda cmd, agent=None: hook("identity-guard.py", env, {"tool_name": "Bash", "tool_input": {"command": cmd},
                                                                 **({"agent_type": agent} if agent else {})})[0]
    ev = "python3 .claude/scripts/evidence.py record --file a --check svg_audit --result PASS"
    check("identità", "firma propria → ammessa", G(f"{ev} --by qa-inspector", "qa-inspector") == 0)
    check("identità", "firma altrui → bloccata", G(f"{ev} --by qa-inspector", "identity-designer") == 2)
    check("identità", "il router non firma per un agente", G(f"{ev} --by critic") == 2)
    check("identità", "firma in variabile → bloccata", G(f'{ev} --by "$AUTORE"', "critic") == 2)
    check("identità", "--by=valore letto", G(f"{ev} --by=critic", "qa-inspector") == 2)
    check("identità", "--record-by altrui → bloccato",
          G(".claude/scripts/py .claude/scripts/facts.py check a.md --record-by critic", "copywriter") == 2)
    check("identità", "--from altrui su ticket.py new → bloccato",
          G("python3 .claude/scripts/ticket.py new --from router --to x", "design-director") == 2)
    check("identità", "un subagente non scrive al cliente",
          G('python3 .claude/scripts/client.py ask --from x --question "q"', "design-director") == 2)
    check("identità", "il router scrive al cliente", G('python3 .claude/scripts/client.py ask --from router --question "q"') == 0)
    check("identità", "redirezione sul registro → bloccata", G('echo x >> .agency/evidence.jsonl', "critic") == 2)
    check("identità", "sed sul ticket → bloccato", G("sed -i s/a/b/ .agency/tickets/T-0001.json", "critic") == 2)
    check("identità", "lettura del registro → ammessa", G("tail -3 .agency/evidence.jsonl", "critic") == 0)
    check("identità", "Write sul registro → bloccata",
          hook("identity-guard.py", env, {"tool_name": "Write", "tool_input": {"file_path": "/p/.agency/tickets/T-1.json"}})[0] == 2)
    check("identità", "lock a nome altrui → bloccato",
          G("python3 .claude/scripts/craft_lock.py acquire vectorcraft router doc", "identity-designer") == 2)
    check("identità", "comandi estranei non toccati", G("ls -la --by x", "critic") == 0)


def t_budget(tmp, env):
    from PIL import Image
    (tmp / ".claude/design-agency").mkdir(parents=True, exist_ok=True)
    shutil.copy(CLAUDE / "design-agency/budgets.json", tmp / ".claude/design-agency/budgets.json")
    (tmp / "work/b").mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (3000, 400)).save(tmp / "work/b/grande.png")
    Image.new("RGB", (3000, 400)).save(tmp / "work/b/grande.jpg")
    Image.new("RGB", (800, 400)).save(tmp / "work/b/ok.png")
    B = lambda ev, agent="legal-reviewer", aid="a1": hook("budget-guard.py", env, {"agent_type": agent, "agent_id": aid, **ev})
    R = lambda name: {"tool_name": "Read", "tool_input": {"file_path": str(tmp / "work/b" / name)}}
    check("budget", "PNG oltre 1600 px → bloccato", B(R("grande.png"))[0] == 2)
    check("budget", "JPEG oltre 1600 px → bloccato", B(R("grande.jpg"))[0] == 2)
    check("budget", "immagine di misura giusta → ammessa", B(R("ok.png"))[0] == 0)
    check("budget", "seconda lettura → ammessa", B(R("ok.png"))[0] == 0)
    check("budget", "terza lettura dello stesso file immutato → bloccata", B(R("ok.png"))[0] == 2)
    Image.new("RGB", (800, 401)).save(tmp / "work/b/ok.png")
    check("budget", "il file è cambiato → si rilegge", B(R("ok.png"))[0] == 0)
    codes = [B({"tool_name": "WebSearch", "tool_input": {"query": "q"}}, aid="w1")[0] for _ in range(13)]
    check("budget", "legal-reviewer si ferma a 12 ricerche", codes[:12] == [0] * 12 and codes[12] == 2)
    run([sys.executable, CLAUDE / "scripts/budget.py", "extend", "legal-reviewer", "web", "2", "--by", "router", "--why", "serve la verifica UIBM"], env=env)
    check("budget", "il router estende", B({"tool_name": "WebSearch", "tool_input": {"query": "q"}}, aid="w1")[0] == 0)
    check("budget", "solo il router estende",
          run([sys.executable, CLAUDE / "scripts/budget.py", "extend", "critic", "web", "2", "--by", "critic", "--why", "serve la verifica"], env=env)[0] == 1)
    codes = [B({"tool_name": "Bash", "tool_input": {"command": "ls"}}, agent="critic", aid="c1")[0] for _ in range(41)]
    check("budget", "alla soglia avvisa una volta, poi si prosegue", codes.count(2) == 1 and codes[39] == 2 and codes[40] == 0)
    M = lambda: hook("budget-guard.py", env, {"session_id": "s9", "tool_name": "SendMessage", "tool_input": {"to": "critic", "message": "m"}})[0]
    check("budget", "terzo risveglio dello stesso agente → bloccato", [M(), M(), M()] == [0, 0, 2])
    _, out = run([sys.executable, CLAUDE / "scripts/budget.py", "status"], env=env)
    check("budget", "budget.py status riassume per agente", "legal-reviewer" in out)
    _, out = run([PY, CLAUDE / "scripts/render.py", "work/b/ok.png", "work/b/grande.png", "--out", "work/proofs/b", "--sheet"], env=env, cwd=tmp)
    check("budget", "render.py produce il foglio di contatto", (tmp / "work/proofs/b/contact_sheet.png").exists())
    check("budget", "render.py resta entro 1200 px", max(Image.open(tmp / "work/proofs/b/grande_preview.png").size) == 1200)


def t_master(tmp, env):
    s = CLAUDE / "scripts"
    if not shutil.which("vectorcraft-cli"):
        return check("master", "vectorcraft-cli presente", False)
    T = lambda *a: run([sys.executable, s / "ticket.py", *a], env=env)
    M = lambda *a: run([PY, s / "master.py", *a], env=env, cwd=tmp)
    (tmp / "work/m").mkdir(parents=True, exist_ok=True)
    svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><path d='M10 90 L50 10 L90 90 Z'/><circle cx='50' cy='60' r='12' fill='#fff'/></svg>"
    (tmp / "work/m/calcolo.svg").write_text(svg)
    base = ("--from", "design-director", "--to", "identity-designer", "--type", "produzione", "--title", "t", "--request", "r")
    code, out = T("new", *base, "--medium", "vettoriale", "--outputs", "work/m/logo.vectorcraft", "work/m/logo.svg",
                  "--accept", "*.vectorcraft=master_open", "*.svg=svg_audit")
    tid = out.strip().splitlines()[-1]
    D = lambda: T("deliver", tid, "--by", "identity-designer")
    shutil.copy(tmp / "work/m/calcolo.svg", tmp / "work/m/logo.svg")
    E = lambda *a: run([sys.executable, s / "evidence.py", *a], env=env)
    E("record", "--file", "work/m/logo.svg", "--check", "svg_audit", "--result", "PASS", "--by", "identity-designer")
    code, out = D()
    check("master", "mezzo vettoriale senza master → consegna rifiutata", code == 1 and "manca" in out)
    (tmp / "work/m/logo.vectorcraft").write_text("{}")
    check("master", "master illeggibile → rifiutato", M("check", "work/m/logo.vectorcraft")[0] == 1)
    (tmp / "work/m/logo.vectorcraft").unlink()
    run(["vectorcraft-cli", "run", "--export", str(tmp / "work/m/vuoto.vectorcraft")], env=env)
    check("master", "master vuoto → rifiutato", M("check", "work/m/vuoto.vectorcraft")[0] == 1)
    run(["vectorcraft-cli", "convert", str(tmp / "work/m/calcolo.svg"), str(tmp / "work/m/logo.vectorcraft")], env=env)
    code, out = M("check", "work/m/logo.vectorcraft", "--record-by", "identity-designer")
    check("master", "la geometria calcolata diventa un master valido", code == 0)
    code, out = D()
    check("master", "SVG non esportato dal master → rifiutato", code == 1 and "non risulta esportato" in out)
    code, out = M("export", "work/m/logo.vectorcraft", "work/m/logo.svg")
    check("master", "export dal master registrato", code == 0)
    E("record", "--file", "work/m/logo.svg", "--check", "svg_audit", "--result", "PASS", "--by", "identity-designer")
    M("check", "work/m/logo.vectorcraft", "--record-by", "identity-designer")
    code, out = D()
    check("master", "master aperto e SVG derivato → consegnato", code == 0, out[-300:])
    run(["vectorcraft-cli", "run", "--in", str(tmp / "work/m/logo.vectorcraft"), "--cmd", "shape.ellipse", "--params",
         '{"x":5,"y":5,"width":9,"height":9}', "--export", str(tmp / "work/m/logo.vectorcraft")], env=env)
    _, status = M("status", "work/m/logo.svg")
    check("master", "master modificato → export scaduto", "SCADUTO" in status)
    code, out = T("new", *base, "--medium", "nessuno", "--outputs", "work/m/x.md", "--accept", "facts_check")
    check("master", "mezzo nessuno senza motivo → rifiutato", code == 1)
    for name, cmd in (("PhotoCraft", ["photocraft-cli", "run", "--new", '{"width":40,"height":40}', "--out", str(tmp / "work/m/f.pcraft")]),
                      ("EffectCraft", ["effectcraft-cli", "run", "file.saveAs", json.dumps({"path": str(tmp / "work/m/e.ecproj")})])):
        run(cmd, env=env)
        target = "work/m/f.pcraft" if name == "PhotoCraft" else "work/m/e.ecproj"
        check("master", f"master {name} aperto con la CLI", M("check", target)[0] == 0)
    (tmp / "work/m/f.figcraft").write_text("x")
    check("master", "master FigCraft non valido → rifiutato", M("check", "work/m/f.figcraft")[0] == 1)
    code, _ = run([sys.executable, CLAUDE / "scripts/workdir.py", "--help"], env=env)
    check("master", "workdir --help non crea cartelle", code == 0 and not (tmp / "--help").exists())
    check("master", "workdir rifiuta le opzioni", run([sys.executable, CLAUDE / "scripts/workdir.py", "--zzz"], env=env)[0] == 1)


def t_dossier(tmp, env):
    s = CLAUDE / "scripts"
    F = lambda *a: run([sys.executable, s / "facts.py", *a], env=env)
    check("dossier", "fatto 'client' senza risposta reale del cliente → rifiutato",
          F("add", "--topic", "audience", "--kind", "client", "--text", "x", "--ref", "A-9999")[0] == 1)
    check("dossier", "ipotesi senza --why/--test → rifiutata",
          F("add", "--topic", "audience", "--kind", "hypothesis", "--text", "x")[0] == 1)
    _, qid = run([sys.executable, s / "client.py", "ask", "--from", "router", "--question", "pubblico?", "--why", "w"], env=env)
    run([sys.executable, s / "client.py", "answer", qid.strip(), "--text", "professionisti 30-50"], env=env)
    _, recs = run(["cat", tmp / ".agency/client.jsonl"])
    aid = [json.loads(l)["id"] for l in recs.splitlines() if '"answer"' in l][-1]
    code, fid = F("add", "--topic", "audience", "--kind", "client", "--text", "professionisti 30-50", "--ref", aid)
    check("dossier", "fatto 'client' con risposta registrata → accettato", code == 0)
    _, hid = F("add", "--topic", "users", "--kind", "hypothesis", "--text", "arrivano in auto", "--why", "periferia", "--test", "chiedere")
    check("dossier", "copertura incompleta → exit 1", F("coverage")[0] == 1)
    F("reject", hid.strip(), "--ref", aid)
    doc = tmp / "work/strategy.md"
    doc.parent.mkdir(exist_ok=True)
    doc.write_text(f"Pubblico {fid.strip()} e mobilità {hid.strip()}".replace("F-", "[F-").replace(" e", "] e").rstrip() + "]")
    code, out = F("check", "work/strategy.md", "--record-by", "brand-strategist")
    check("dossier", "check segnala un fatto smentito ancora citato", code == 1 and "smentito" in out)
    F("export")
    check("dossier", "export scrive il dossier con le provenienze", "**CLIENTE**" in (tmp / "work/context/dossier.md").read_text())


def t_mondo(tmp, env):
    c = tmp / "work/client"
    (c / "foto").mkdir(parents=True, exist_ok=True)
    from PIL import Image
    Image.new("RGB", (400, 300), (40, 90, 140)).save(c / "foto/ingresso.jpg")
    (c / "testi.md").write_text("Fisioterapia sportiva a Lugano. Riabilitazione dopo infortunio. Fisioterapia per atleti.")
    run([PY, "-c", f"import pymupdf; d=pymupdf.open(); p=d.new_page(); p.insert_text((72,72),'Modulo di accettazione paziente'); d.save(r'{c}/modulo.pdf')"])
    code, out = run([PY, SK / "client-world/scripts/world_ingest.py", "work/client"], env=env, cwd=tmp)
    inv = tmp / "work/context/world/inventory.md"
    check("mondo", "inventario del mondo del cliente", code == 0 and inv.exists() and "modulo.pdf" in inv.read_text())
    pal = json.loads((tmp / "work/context/world/palette.json").read_text())
    def near(h, target=(40, 90, 140)):
        rgb = [int(h[i:i + 2], 16) for i in (1, 3, 5)]
        return sum((x - y) ** 2 for x, y in zip(rgb, target)) < 25
    check("mondo", "palette misurata dalle foto del cliente (un solo colore, senza duplicati)",
          any(len(p) == 1 and near(p[0]["hex"]) for p in pal.values()))
    lex = json.loads((tmp / "work/context/world/lexicon.json").read_text())
    check("mondo", "lessico del cliente estratto", lex["words"][0][0] == "fisioterapia")


def t_sprint(tmp, env):
    g = CLAUDE / "hooks/isolation-guard.py"
    G = lambda agent, tool, inp: run([sys.executable, g], inp=json.dumps({"agent_type": agent, "tool_name": tool, "tool_input": inp}))[0]
    check("sprint", "direction-a non legge la direzione B", G("direction-a", "Read", {"file_path": "/p/work/directions/b/direction.md"}) == 2)
    check("sprint", "direction-a non elenca la cartella delle direzioni", G("direction-a", "Glob", {"pattern": "work/directions/*"}) == 2)
    check("sprint", "direction-a non vede le tavole", G("direction-a", "Read", {"file_path": "/p/work/directions/boards/A1.png"}) == 2)
    check("sprint", "direction-a non scrive fuori dalla sua cartella", G("direction-a", "Write", {"file_path": "/p/work/brief.md"}) == 2)
    check("sprint", "direction-a legge il brief pack", G("direction-a", "Read", {"file_path": "/p/work/directions/brief-pack.md"}) == 0)
    check("sprint", "direction-a scrive nella sua cartella", G("direction-a", "Write", {"file_path": "/p/work/directions/a/apps/A1.png"}) == 0)
    check("sprint", "altri agenti non sono limitati", G("critic", "Read", {"file_path": "/p/work/directions/b/direction.md"}) == 0)
    d = tmp / "work/directions"
    (d).mkdir(parents=True, exist_ok=True)
    (d / "brief-pack.md").write_text("# Brief pack\n## Territori esclusi\n- goniometro\n")
    (tmp / "work/creative-contract.md").write_text("# Contratto\n")
    (d / "apps.json").write_text(json.dumps({"apps": [{"id": "A1", "name": "Lockup", "size": [320, 200]},
                                                      {"id": "A2", "name": "Poster", "size": [200, 280]}]}))
    from PIL import Image, ImageDraw
    looks = {"a": ((250, 245, 235), (20, 20, 20), "circle"), "b": ((15, 30, 60), (240, 200, 60), "bar"), "c": ((250, 245, 235), (20, 20, 20), "circle")}
    for k, (bg, fg, shape) in looks.items():
        (d / k / "apps").mkdir(parents=True, exist_ok=True)
        (d / k / "direction.md").write_text("\n".join(f"## {s}\nx [F-0001]" for s in
            ["Concept", "Composizione", "Tipografia", "Colore", "Linguaggio delle immagini", "Movimento", "Voce", "Fatti su cui si basa", "Rischi"]))
        for app in ("A1", "A2"):
            size = (320, 200) if app == "A1" else (200, 280)
            im = Image.new("RGB", size, bg)
            dr = ImageDraw.Draw(im)
            if shape == "circle":
                dr.ellipse((size[0] * 0.3, size[1] * 0.25, size[0] * 0.7, size[1] * 0.75), fill=fg)
            else:
                dr.rectangle((0, size[1] * 0.6, size[0], size[1] * 0.8), fill=fg)
            im.save(d / k / "apps" / f"{app}.png")
    B = lambda *a: run([PY, SK / "direction-sprint/scripts/direction_board.py", *a], env=env)
    check("sprint", "board check completo", B("check")[0] == 0)
    code, out = B("diversity", "--record-by", "creative-director")
    check("sprint", "diversity segnala due direzioni quasi identiche", code == 1 and "a–c" in out and "TROPPO SIMILI" in out)
    Image.new("RGB", (100, 100)).save(d / "a/apps/A1.png")
    check("sprint", "board check segnala dimensioni errate", B("check")[0] == 1)
    B("boards", "--seed", "1")
    check("sprint", "tavole anonime prodotte", (d / "boards/A2.png").exists() and (tmp / ".agency/blind-map.json").exists())
    card = lambda concept, lever, font, colors, img: ("## Scheda\n" + "\n".join([
        f"- Concept: {concept}", f"- Leva di partenza: {lever}", "- Principio compositivo: " + concept,
        f"- Carattere primario: {font}", f"- Colori primari: {colors}", f"- Linguaggio delle immagini: {img}",
        "- Idee ovvie scartate: onda; croce; omino"]) + "\n")
    (d / "a/direction.md").write_text(card("goniometro sull'orizzonte del lago, gradi di movimento", "gesto",
                                          "Inter (OFL)", "#16324F, #F26B1D", "tipografico"))
    (d / "b/direction.md").write_text(card("pietra del lungolago levigata dal movimento continuo", "materia",
                                          "Fraunces (OFL)", "#8A7F6E, #2B2B26", "fotografia materica"))
    (d / "c/direction.md").write_text(card("goniometro sull'orizzonte del lago, gradi e recupero", "gesto",
                                          "Inter (OFL) + JetBrains Mono (OFL)", "#16324F, #F26B1D", "tipografico"))
    code, out = B("lint")
    check("sprint", "lint segnala Inter senza giustificazione", code == 1 and "inter" in out.lower())
    code, out = B("concepts", "--record-by", "creative-director")
    check("sprint", "concepts segnala a–c convergenti e a–b diverse",
          code == 1 and "a–c" in out and "NON SOSTANZIALMENTE" in out.split("a–c")[1].splitlines()[0]
          and "NON SOSTANZIALMENTE" not in out.split("a–b")[1].splitlines()[0])


def t_ottica(tmp, env):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (400, 400), (255, 255, 255))
    ImageDraw.Draw(im).polygon([(200, 100), (320, 320), (80, 320)], fill=(0, 0, 0))
    im.save(tmp / "tri.png")
    code, out = run([PY, SK / "visual-qa/scripts/optical_check.py", tmp / "tri.png", "--out", tmp / "tri_annot.png"])
    # Un triangolo centrato nella bbox ha il baricentro sotto il centro della bbox (1/3 dell'altezza dalla base).
    check("ottica", "baricentro del triangolo sotto il centro della bbox", code == 0 and re_search(r"centro bbox:\s+[+-]\d+\.\d+% x, \+", out))
    for i, r in enumerate((60, 60, 90)):
        c = Image.new("RGB", (200, 200), (255, 255, 255))
        ImageDraw.Draw(c).ellipse((100 - r, 100 - r, 100 + r, 100 + r), fill=(0, 0, 0))
        c.save(tmp / f"ic{i}.png")
    code, out = run([PY, SK / "visual-qa/scripts/optical_check.py", "--set", tmp / "ic0.png", tmp / "ic1.png", tmp / "ic2.png"])
    check("ottica", "set: icona otticamente più pesante segnalata", code == 1 and "ic2.png" in out.split("PESO OTTICO")[0].splitlines()[-1])


def re_search(pattern, text):
    import re
    return re.search(pattern, text) is not None


def t_render(tmp, env):
    from PIL import Image
    (tmp / "r").mkdir(exist_ok=True)
    Image.new("RGB", (300, 200), (200, 30, 60)).save(tmp / "r/a.png")
    (tmp / "r/p.html").write_text('<!doctype html><html lang="it"><head><meta charset="utf-8"><title>t</title></head><body>Prova</body></html>')
    run([PY, "-c", f"import pymupdf; d=pymupdf.open(); d.new_page(); d.new_page(); d.save(r'{tmp}/r/d.pdf')"])
    code, out = run([PY, CLAUDE / "scripts/render.py", "r/a.png", "r/p.html", "r/d.pdf", "--out", "r/out"], env=env, cwd=tmp)
    check("render", "render di immagine, HTML e PDF", code == 0 and (tmp / "r/out/p_w1440.png").exists() and (tmp / "r/out/d_p002.png").exists())
    code, _ = run([PY, CLAUDE / "scripts/render.py", "r/a.png", "--out", "r/out2", "--zoom", "0,0,0.5,0.5"], env=env, cwd=tmp)
    check("render", "ingrandimento di dettaglio prodotto e registrato", code == 0 and (tmp / "r/out2/a_preview_zoom_0.00_0.00.png").exists())
    man = (tmp / ".agency/renders.jsonl").read_text()
    check("render", "manifest dei render con hash della sorgente", '"source": "r/d.pdf"' in man and "source_sha" in man)
    hook = CLAUDE / "hooks/observe-reminder.py"
    _, out = run([sys.executable, hook], inp=json.dumps({"tool_name": "Write", "tool_input": {"file_path": "/p/work/logo.svg"}}))
    check("render", "hook ricorda di renderizzare e guardare un SVG scritto", "render.py" in out)


def t_design(tmp, env):
    d = tmp / "work/design"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "sito.figcraft"
    s1 = d / "s1.json"
    s1.write_text(json.dumps([
        {"command": "node.create", "params": {"type": "frame", "name": "Home 1440", "width": 1440, "height": 900, "props": {"fill": "#F2F0E7"}}},
        {"command": "node.create", "params": {"type": "frame", "name": "Home 390", "x": 1540, "width": 390, "height": 844, "props": {"fill": "#13141A"}}}]))
    run(["figcraft-cli", "run", s1, "--out", f])
    s2 = d / "s2.json"
    s2.write_text(json.dumps([
        {"command": "node.create", "params": {"type": "text", "parent": 2, "x": 96, "y": 120, "text": "Titolo", "props": {"fontSize": 96, "fill": "#13141A"}}},
        {"command": "node.create", "params": {"type": "text", "parent": 2, "x": 96, "y": 400, "text": "Note minuscole", "props": {"fontSize": 10, "fill": "#B5B2A8"}}},
        {"command": "node.create", "params": {"type": "rectangle", "parent": 3, "x": 20, "y": 40, "width": 20, "height": 20, "props": {"fill": "#F26B1D"}}}]))
    run(["figcraft-cli", "run", s2, "--in", f, "--out", f])
    s3 = d / "s3.json"
    s3.write_text(json.dumps([{"command": "proto.interaction.add", "params": {"id": 6, "dest": 2}}]))
    run(["figcraft-cli", "run", s3, "--in", f, "--out", f])
    code, out = run([PY, SK / "web-design/scripts/figcraft_audit.py", f, "--record-by", "ui-designer"])
    check("design", "audit FigCraft: testo < 12 px, contrasto e target < 24 trovati",
          code == 1 and "10 px" in out and "contrasto" in out and "20×20" in out)
    code, out = run([PY, CLAUDE / "scripts/render.py", "work/design/sito.figcraft", "--out", "work/proofs"], cwd=tmp)
    check("design", "render di un file FigCraft: un PNG per frame",
          code == 0 and (tmp / "work/proofs/sito_frames/Home 390.png").exists())


def t_scoperta(tmp, env):
    # Progetto separato: lo stato lasciato dagli altri gruppi (domande aperte) non deve interferire.
    s = CLAUDE / "scripts"
    tmp = tmp / "scoperta"
    tmp.mkdir(exist_ok=True)
    env2 = dict(env, CLAUDE_PROJECT_DIR=str(tmp))
    C = lambda *a: run([sys.executable, s / "client.py", *a], env=env2)
    F = lambda *a: run([sys.executable, s / "facts.py", *a], env=env2)
    check("scoperta", "ready: non pronto all'inizio", C("ready")[0] == 1)
    _, q = C("ask", "--from", "router", "--question", "pubblico?", "--why", "tono", "--blocking")
    code, out = C("ready")
    check("scoperta", "ready: domanda bloccante aperta → non pronto", code == 1 and "bloccanti" in out)
    C("answer", q.strip(), "--text", "professionisti")
    aid = [json.loads(l)["id"] for l in (tmp / ".agency/client.jsonl").read_text().splitlines() if '"answer"' in l][-1]
    for topic in ("objective", "audience", "context", "competitors", "content", "constraints", "success"):
        F("add", "--topic", topic, "--kind", "client", "--text", f"fatto {topic}", "--ref", aid)
    code, out = C("ready")
    check("scoperta", "ready: senza comprensione confermata → non pronto", code == 1 and "comprensione" in out)
    (tmp / "work/context").mkdir(parents=True, exist_ok=True)
    (tmp / "work/context/understanding.md").write_text("# Comprensione\nil cliente è … [F-0001]")
    C("approve", "--gate", "understanding", "--files", "work/context/understanding.md", "--text", "Sì, avete capito bene")
    check("scoperta", "ready: comprensione confermata e dossier coperto → pronto", C("ready")[0] == 0)


def t_prove(tmp, env):
    sys.path.insert(0, str(CLAUDE / "scripts"))
    (tmp / "work").mkdir(exist_ok=True)
    a, b = tmp / "work/a.txt", tmp / "work/b.txt"
    a.write_text("a")
    b.write_text("b")
    E = lambda *x: run([sys.executable, CLAUDE / "scripts/evidence.py", *x])
    run([sys.executable, "-c", f"import sys; sys.path.insert(0, r'{CLAUDE / 'scripts'}'); import evidence; "
         f"evidence.record_auto('work/a.txt', 'diversity', 'MEASURED', 'qa-inspector', inputs=['work/b.txt']); "
         f"evidence.record_auto('work/a.txt', 'svg_audit', 'MEASURED', 'qa-inspector')"], cwd=tmp)
    check("prove", "MEASURED accettato per una misura", E("gate", "work/a.txt", "--require", "diversity")[0] == 0)
    check("prove", "MEASURED non vale come PASS per un requisito", E("gate", "work/a.txt", "--require", "svg_audit")[0] == 1)
    b.write_text("b2")
    code, out = E("gate", "work/a.txt", "--require", "diversity")
    check("prove", "la prova scade se cambia un input confrontato", code == 1 and "STALE" in out)


def t_produzione(tmp, env):
    from PIL import Image
    ph = tmp / "photo"
    ph.mkdir(exist_ok=True)
    for i, c in enumerate([(120, 110, 100), (125, 112, 98), (118, 108, 102), (30, 40, 90)]):
        Image.new("RGB", (200, 150), c).save(ph / f"p{i}.jpg")
    code, out = run([PY, SK / "image-direction/scripts/photo_set.py", "measure", ph])
    check("produzione", "photo_set segnala la foto fuori set", code == 1 and "p3.jpg" in [l.split()[2] for l in out.splitlines() if "FUORI SET" in l])
    art = tmp / "fronte.png"
    Image.new("RGB", (400, 600), (30, 60, 90)).save(art)
    code, out = run(["blender", "-b", "-P", SK / "production-3d/scripts/pack_render.py", "--", "--size", "40x20x60",
                     "--front", art, "--out", tmp / "pack.png", "--res", "320x240", "--samples", "8", "--finish", "matte",
                     "--light", "0.5"], timeout=600)
    check("produzione", "render Blender con autoverifica di colore e alte luci",
          (tmp / "pack.png").exists() and "VERIFICA fronte" in out and "VERIFICA alte luci" in out)
    check("produzione", "render Blender dichiara il dispositivo usato", "DISPOSITIVO " in out, out[-300:])
    code, out = run(["blender", "-b", "-P", SK / "production-3d/scripts/pack_render.py", "--", "--size", "40x20x60",
                     "--front", art, "--out", tmp / "pack_cpu.png", "--res", "160x120", "--samples", "2"],
                    env={**TEST_ENV, "CUDA_VISIBLE_DEVICES": "-1"}, timeout=600)
    check("produzione", "render Blender senza GPU ripiega sulla CPU e lo dichiara",
          (tmp / "pack_cpu.png").exists() and "DISPOSITIVO CPU" in out, out[-300:])
    bad = tmp / "storto.png"
    Image.new("RGB", (600, 600), (30, 60, 90)).save(bad)
    code, out = run(["blender", "-b", "-P", SK / "production-3d/scripts/pack_render.py", "--", "--size", "40x20x60",
                     "--front", bad, "--out", tmp / "pack2.png", "--res", "160x120", "--samples", "2"], timeout=600)
    check("produzione", "render Blender rifiuta una grafica con proporzioni diverse dalla faccia", "proporzioni" in out)


def t_contratto_creativo(tmp, env):
    s = CLAUDE / "scripts"
    w = tmp / "cc/work"
    w.mkdir(parents=True, exist_ok=True)
    env2 = dict(env, CLAUDE_PROJECT_DIR=str(tmp / "cc"))
    shutil.copy(CLAUDE / "design-agency/templates/creative-contract.md", w / "creative-contract.md")
    code, out = run([sys.executable, s / "contract_lint.py"], env=env2)
    check("contratto creativo", "modello non compilato → rifiutato", code == 1 and "non compilata" in out)
    body = {"Percezione da produrre": "Chi apre il sito percepisce un caffè lavorato a mano, attraverso fotografie ravvicinate dei chicchi e titoli grandi.",
            "Cosa del cliente deve emergere": "Le schede di tostatura scritte a mano [F-0004] diventano materiale tipografico delle pagine prodotto.",
            "Decisione visiva caratterizzante": "La curva di tostatura di ogni lotto, come linea sottile su carta kraft, accompagna ogni prodotto.",
            "Dove sperimentare": "Nella pagina dei lotti: sequenza di immagini e curve che si costruiscono allo scorrimento, provata su touch.",
            "Cosa deve restare familiare e immediato": "Carrello, spedizioni e prezzi: componenti convenzionali, testo a 16 px, nessun effetto.",
            "Come giudicheremo il risultato": "Home desktop e touch, scheda prodotto e pagina lotti, confrontate con i riferimenti di livello."}
    (w / "creative-contract.md").write_text("# Contratto\n" + "".join(f"## {k}\n{v}\n" for k, v in body.items()))
    check("contratto creativo", "contratto concreto → accettato", run([sys.executable, s / "contract_lint.py"], env=env2)[0] == 0)
    with open(w / "creative-contract.md", "a") as fh:
        fh.write("Vogliamo un look premium e moderno.\n")
    code, out = run([sys.executable, s / "contract_lint.py"], env=env2)
    check("contratto creativo", "aggettivo senza forma osservabile → segnalato", code == 1 and "premium" in out)


def t_giudizio(tmp, env):
    from PIL import Image
    s = CLAUDE / "scripts"
    root = tmp / "gd"
    (root / "work").mkdir(parents=True, exist_ok=True)
    env2 = dict(env, CLAUDE_PROJECT_DIR=str(root))
    Image.new("RGB", (80, 60), (20, 40, 90)).save(root / "work/poster.png")
    Image.new("RGB", (80, 60), (200, 200, 200)).save(root / "work/riferimento.png")
    E = lambda *a: run([sys.executable, s / "evidence.py", *a], env=env2, cwd=root)
    why = "Rispetto al riferimento eccellente la gerarchia regge, ma il titolo è meno incisivo per scala e il margine inferiore pesa troppo."
    check("giudizio", "giudizio senza render della versione attuale → rifiutato",
          E("judge", "work/poster.png", "--compare", "work/riferimento.png", "--why", why, "--by", "critic", "--result", "PASS")[0] == 1)
    run([PY, s / "render.py", "work/poster.png", "--out", "work/proofs"], env=env2, cwd=root)
    check("giudizio", "motivazione generica → rifiutata",
          E("judge", "work/poster.png", "--compare", "work/riferimento.png", "--why", "bello", "--by", "critic", "--result", "PASS")[0] == 1)
    check("giudizio", "giudizio con confronto e motivazione → registrato",
          E("judge", "work/poster.png", "--compare", "work/riferimento.png", "--why", why, "--by", "critic", "--result", "PASS")[0] == 0)
    check("giudizio", "gate quality_judgement superato", E("gate", "work/poster.png", "--require", "quality_judgement")[0] == 0)
    Image.new("RGB", (80, 60), (180, 30, 30)).save(root / "work/riferimento.png")
    check("giudizio", "il giudizio scade se cambia il termine di confronto",
          E("gate", "work/poster.png", "--require", "quality_judgement")[0] == 1)
    # Riferimenti visivi obbligatori nei ticket di produzione dopo la direzione.
    (root / "work/direction.md").write_text("A")
    run([sys.executable, s / "client.py", "approve", "--gate", "direction", "--files", "work/direction.md", "--text", "ok A"], env=env2)
    T = lambda *a: run([sys.executable, s / "ticket.py", *a], env=env2, cwd=root)
    base = ["new", "--from", "design-director", "--to", "identity-designer", "--type", "produzione", "--title", "t",
            "--request", "r", "--outputs", "work/out.svg", "--accept", "svg_audit", "--after-gate", "direction",
            "--medium", "vettoriale"]
    check("giudizio", "produzione dopo la direzione senza riferimenti visivi → rifiutata",
          T(*base, "--inputs", "work/direction.md")[0] == 1)
    check("giudizio", "produzione con un esempio approvato tra gli input → accettata",
          T(*base, "--inputs", "work/direction.md", "work/poster.png")[0] == 0)


def t_setup(tmp, env):
    check("setup", "nessuno stato di progetto scritto nel template durante i test", not (ROOT / ".agency").exists())
    check("setup", "validate_agency --template", run([sys.executable, CLAUDE / "scripts/validate_agency.py", "--template"], cwd=ROOT)[0] == 0)
    check("setup", "toolchain: nessun tool core mancante", run([PY, CLAUDE / "scripts/tools.py", "check"])[0] == 0)


GROUPS = {"colore": t_colore, "tipo": t_tipo, "token": t_token, "svg": t_svg, "immagini": t_immagini,
          "pdf": t_pdf, "motion": t_motion, "web": t_web, "governance": t_governance, "contratto": t_contratto,
          "dossier": t_dossier, "mondo": t_mondo, "sprint": t_sprint, "ottica": t_ottica, "render": t_render,
          "design": t_design, "scoperta": t_scoperta, "prove": t_prove, "produzione": t_produzione,
          "contratto creativo": t_contratto_creativo, "giudizio": t_giudizio,
          "stati": t_stati, "identità": t_identita, "budget": t_budget, "master": t_master,
          "setup": t_setup}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--keep", action="store_true", help="conserva la cartella temporanea")
    p.add_argument("--only")
    a = p.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="studio-selftest-"))
    global TEST_ENV
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp))
    TEST_ENV = env
    shutil.copytree(CLAUDE, tmp / ".claude", ignore=shutil.ignore_patterns("runtime", "__pycache__"))
    wanted = a.only.split(",") if a.only else list(GROUPS)
    for g in wanted:
        try:
            GROUPS[g](tmp, env)
        except Exception as exc:  # un gruppo che si rompe è un fallimento, non un crash della suite
            check(g, "esecuzione del gruppo", False, repr(exc))
    failed = [r for r in results if not r[2]]
    print(f"\n{len(results) - len(failed)}/{len(results)} test superati" + (f" — cartella: {tmp}" if a.keep else ""))
    if not a.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
