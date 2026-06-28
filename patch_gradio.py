"""
Patches gradio 4.44.1 for Python 3.14 compatibility on Render.
Run via: pip install -r requirements.txt && python patch_gradio.py
"""
import os, re, sys

def get_pkg_file(import_name, subpath=None):
    """Get path to an installed package file."""
    import importlib, importlib.util
    try:
        spec = importlib.util.find_spec(import_name)
        if spec and spec.origin:
            base = os.path.dirname(spec.origin)
            if subpath:
                p = os.path.join(base, subpath)
                return p if os.path.exists(p) else None
            return spec.origin
    except Exception:
        pass
    return None

def read(p): 
    with open(p) as f: return f.read()

def write(p, s):
    with open(p, 'w') as f: f.write(s)

def patch(p, old, new, tag):
    if not p or not os.path.exists(p): print(f"  SKIP {tag}: not found"); return False
    s = read(p)
    if old in s:
        write(p, s.replace(old, new, 1))
        print(f"  OK   {tag}"); return True
    print(f"  MISS {tag}"); return False

# ── Find paths ─────────────────────────────────────────────────────────────────
gradio_dir  = os.path.dirname(get_pkg_file('gradio') or '')
gcu_path    = get_pkg_file('gradio_client', 'utils.py') or \
              get_pkg_file('gradio_client.utils')
blocks_path = os.path.join(gradio_dir, 'blocks.py') if gradio_dir else None
routes_path = os.path.join(gradio_dir, 'routes.py') if gradio_dir else None
utils_path  = os.path.join(gradio_dir, 'utils.py')  if gradio_dir else None

# Try harder to find gradio_client
if not gcu_path:
    try:
        import gradio_client.utils as _gcu; gcu_path = _gcu.__file__
    except Exception: pass

print(f"blocks.py : {blocks_path}")
print(f"routes.py : {routes_path}")
print(f"utils.py  : {utils_path}")
print(f"gcu/utils : {gcu_path}")

# ── PATCH 1: blocks.py — bypass localhost check (ValueError) ──────────────────
print("\n[PATCH 1] blocks.py localhost check")
if not patch(blocks_path,
        "            and not networking.url_ok(self.local_url)\n",
        "            # and not networking.url_ok(self.local_url)  # patched\n",
        "url_ok line commented out"):
    # Fallback: remove entire if block that raises ValueError
    if blocks_path and os.path.exists(blocks_path):
        s = read(blocks_path)
        s2 = re.sub(
            r"        if \(\n            _frontend\n.*?raise ValueError\(\n.*?localhost.*?\n.*?\)\n",
            "        pass  # localhost check removed\n",
            s, flags=re.DOTALL
        )
        if s2 != s:
            write(blocks_path, s2); print("  OK   url_ok block removed via regex")
        else:
            print("  MISS both patterns failed")

# ── PATCH 2: gradio_client/utils.py — bool schema handling ───────────────────
print("\n[PATCH 2] gradio_client/utils.py")
if gcu_path and os.path.exists(gcu_path):
    s = read(gcu_path)
    changed = False
    # 2a: dict guard in get_type
    if 'if not isinstance(schema, dict)' not in s:
        s = s.replace(
            '    if "const" in schema:',
            '    if not isinstance(schema, dict): return "Any"\n    if "const" in schema:'
        )
        changed = True; print("  OK   2a: dict guard in get_type")
    # 2b: suppress all raise APIInfoParseError
    # Replace each raise on its own line with a return on a new line
    def _replace_raise(m):
        indent = m.group(1)
        return f"{indent}return \"Any\"  # patched: was APIInfoParseError\n"
    s2 = re.sub(r'^(\s*)raise APIInfoParseError\([^)]+\)\n', _replace_raise, s, flags=re.MULTILINE)
    if s2 != s:
        s = s2; changed = True
        count = len(re.findall(r'raise APIInfoParseError', read(gcu_path))) - len(re.findall(r'raise APIInfoParseError', s))
        print(f"  OK   2b: APIInfoParseError raises replaced")
    if changed:
        write(gcu_path, s)
else:
    print("  SKIP: gcu/utils.py not found")

# ── PATCH 3: routes.py — TemplateResponse keyword args ───────────────────────
print("\n[PATCH 3] routes.py TemplateResponse")
if routes_path and os.path.exists(routes_path):
    s = read(routes_path)
    if 'name=template' in s or 'name = template' in s:
        print("  SKIP: already uses keyword args")
    else:
        s2 = re.sub(
            r'return templates\.TemplateResponse\(\s*\n(\s*)template,(\s*)\n(\s*)\{',
            r'return templates.TemplateResponse(\n\1name=template,\2\n\3context={',
            s
        )
        if s2 != s:
            write(routes_path, s2); print("  OK   TemplateResponse uses keyword args")
        else:
            print("  MISS: pattern not found (may be OK on this Starlette version)")
else:
    print("  SKIP: routes.py not found")

# ── PATCH 4: gradio/utils.py — asyncio event_loop ────────────────────────────
print("\n[PATCH 4] gradio/utils.py event_loop")
OLD_LOOP = '    event_loop = asyncio.get_event_loop()\n'
NEW_LOOP = (
    '    try:\n'
    '        event_loop = asyncio.get_event_loop()\n'
    '    except RuntimeError:\n'
    '        event_loop = asyncio.new_event_loop()\n'
    '        asyncio.set_event_loop(event_loop)\n'
)
if not patch(utils_path, OLD_LOOP, NEW_LOOP, "asyncio event_loop RuntimeError fix"):
    if utils_path and os.path.exists(utils_path):
        s = read(utils_path)
        if 'new_event_loop' in s:
            print("  SKIP: already patched")

print("\n=== patch_gradio.py complete ===")
