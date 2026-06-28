"""
Patches gradio 4.44.1 for Python 3.14 on Render.
Fixes: localhost ValueError, bool schema TypeError, TemplateResponse, event_loop.
Run: pip install -r requirements.txt && python patch_gradio.py
"""
import os, re, sys

def rw(p):
    with open(p) as f: return f.read()

def ww(p, s):
    with open(p, 'w') as f: f.write(s)

def find(pkg, fname=None):
    try:
        import importlib.util
        spec = importlib.util.find_spec(pkg)
        if spec and spec.origin:
            d = os.path.dirname(spec.origin)
            return os.path.join(d, fname) if fname else spec.origin
    except Exception:
        pass
    return None

# Locate files
gradio_dir = os.path.dirname(find('gradio') or '')
blocks_p  = os.path.join(gradio_dir, 'blocks.py')  if gradio_dir else None
routes_p  = os.path.join(gradio_dir, 'routes.py')  if gradio_dir else None
utils_p   = os.path.join(gradio_dir, 'utils.py')   if gradio_dir else None
gcu_p     = find('gradio_client', 'utils.py')
if not gcu_p:
    try:
        import gradio_client.utils as _g; gcu_p = _g.__file__
    except Exception: pass

print("blocks.py :", blocks_p)
print("routes.py :", routes_p)
print("utils.py  :", utils_p)
print("gcu/utils :", gcu_p)

# ── PATCH 1: blocks.py — remove localhost ValueError ──────────────────────────
print("\n[PATCH 1] blocks.py — remove localhost ValueError")
if blocks_p and os.path.exists(blocks_p):
    s = rw(blocks_p)
    patched = False

    # Method A: replace the raise line with pass (works on any indentation)
    s2 = re.sub(
        r'(\s+)raise ValueError\(\s*\n\s*"When localhost is not accessible[^"]*"\s*\n\s*\)',
        r'\1pass  # ValueError removed by patch_gradio.py',
        s
    )
    if s2 != s:
        ww(blocks_p, s2); print("  OK   raise ValueError -> pass"); patched = True

    if not patched:
        # Method B: comment out url_ok condition line
        for old in [
            "            and not networking.url_ok(self.local_url)\n",
            "        and not networking.url_ok(self.local_url)\n",
        ]:
            if old in s:
                ww(blocks_p, s.replace(old, old.replace("and not", "# and not"), 1))
                print("  OK   url_ok condition commented out"); patched = True; break

    if not patched:
        if 'When localhost' not in s:
            print("  SKIP already patched")
        else:
            print("  MISS could not patch blocks.py")
else:
    print("  SKIP blocks.py not found")

# ── PATCH 2: gradio_client/utils.py — bool schema TypeError ──────────────────
print("\n[PATCH 2] gradio_client/utils.py — bool schema")
if gcu_p and os.path.exists(gcu_p):
    s = rw(gcu_p)
    changed = False

    # 2a: dict guard in get_type
    if 'if not isinstance(schema, dict)' not in s:
        s = s.replace(
            '    if "const" in schema:',
            '    if not isinstance(schema, dict): return "Any"\n    if "const" in schema:'
        )
        if 'if not isinstance(schema, dict)' in s:
            print("  OK   2a: dict guard in get_type"); changed = True
        else:
            print("  MISS 2a: 'const' pattern not found")

    # 2b: replace ALL raise APIInfoParseError lines with return "Any"
    def _repl_raise(m):
        return m.group(1) + 'return "Any"  # patched\n'
    s2 = re.sub(r'^(\s*)raise APIInfoParseError\([^\n]+\)\n', _repl_raise, s, flags=re.MULTILINE)
    n = s.count('raise APIInfoParseError')
    if s2 != s:
        s = s2; print(f"  OK   2b: {n} raise APIInfoParseError -> return Any"); changed = True
    elif n == 0:
        print("  SKIP 2b: no raise APIInfoParseError found")

    if changed:
        ww(gcu_p, s)
        # Verify syntax
        try:
            import ast; ast.parse(s); print("  OK   gcu/utils.py syntax valid")
        except SyntaxError as e:
            print(f"  !! syntax error after patch: {e}")
else:
    print("  SKIP gcu/utils.py not found")

# ── PATCH 3: routes.py — TemplateResponse positional -> keyword args ──────────
print("\n[PATCH 3] routes.py — TemplateResponse keyword args")
if routes_p and os.path.exists(routes_p):
    s = rw(routes_p)
    if 'name=template' in s:
        print("  SKIP already uses keyword args")
    else:
        # Line-by-line: find TemplateResponse( line followed by bare 'template,' line
        lines = s.splitlines(keepends=True)
        out = []; i = 0; changed = False
        while i < len(lines):
            line = lines[i]
            if 'templates.TemplateResponse(' in line and i+1 < len(lines):
                nxt = lines[i+1]
                if nxt.strip() in ('template,', 'template'):
                    ind = len(nxt) - len(nxt.lstrip())
                    out.append(line)
                    out.append(' ' * ind + 'name=template,\n')
                    i += 2
                    # convert bare { to context={
                    if i < len(lines) and lines[i].strip() == '{':
                        ind2 = len(lines[i]) - len(lines[i].lstrip())
                        out.append(' ' * ind2 + 'context={\n')
                        i += 1
                    changed = True
                    continue
            out.append(line); i += 1

        if changed:
            ww(routes_p, ''.join(out))
            print("  OK   TemplateResponse converted to keyword args")
        else:
            # Regex fallback
            s2 = re.sub(
                r'([ \t]*)return templates\.TemplateResponse\(\s*\n\s*template,',
                r'\1return templates.TemplateResponse(\n\1    name=template,',
                s
            )
            if s2 != s:
                ww(routes_p, s2); print("  OK   TemplateResponse fixed via regex")
            else:
                print("  MISS could not fix TemplateResponse")
else:
    print("  SKIP routes.py not found")

# ── PATCH 4: gradio/utils.py — asyncio event_loop RuntimeError ───────────────
print("\n[PATCH 4] gradio/utils.py — asyncio event_loop")
if utils_p and os.path.exists(utils_p):
    s = rw(utils_p)
    OLD = '    event_loop = asyncio.get_event_loop()\n'
    NEW = ('    try:\n'
           '        event_loop = asyncio.get_event_loop()\n'
           '    except RuntimeError:\n'
           '        event_loop = asyncio.new_event_loop()\n'
           '        asyncio.set_event_loop(event_loop)\n')
    if OLD in s and 'new_event_loop' not in s:
        ww(utils_p, s.replace(OLD, NEW, 1)); print("  OK   event_loop RuntimeError fix")
    elif 'new_event_loop' in s:
        print("  SKIP already patched")
    else:
        print("  MISS event_loop pattern not found")
else:
    print("  SKIP gradio/utils.py not found")

print("\n=== patch_gradio.py complete ===")
