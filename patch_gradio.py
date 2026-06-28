"""
Patches gradio 4.44.1 for Python 3.14 compatibility on Render.
Run via: pip install -r requirements.txt && python patch_gradio.py
"""
import os, sys, re

def find_file(pkg_name, filename):
    try:
        import importlib
        mod = importlib.import_module(pkg_name)
        base = os.path.dirname(mod.__file__)
        path = os.path.join(base, filename)
        if os.path.exists(path):
            return path
    except Exception:
        pass
    return None

def patch_file(path, old, new, label):
    if not path or not os.path.exists(path):
        print(f"  SKIP {label}: file not found")
        return False
    with open(path) as f:
        src = f.read()
    if old in src:
        with open(path, 'w') as f:
            f.write(src.replace(old, new, 1))
        print(f"  OK   {label}")
        return True
    print(f"  MISS {label}: pattern not found")
    return False

# ── PATCH 1: blocks.py — remove localhost check ───────────────────────────────
blocks_path = find_file('gradio', 'blocks.py')
print(f"\nblocks.py: {blocks_path}")

p1a = patch_file(blocks_path,
    "and not networking.url_ok(self.local_url)\n            and not self.share\n        ):\n            raise ValueError(\n                \"When localhost is not accessible",
    "and True  # patched\n            and not self.share\n        ):\n            pass  # raise removed by patch_gradio.py\n        if False:  # pragma: no cover\n            raise ValueError(\n                \"When localhost is not accessible",
    "PATCH 1a: url_ok check bypassed")

if not p1a:
    # simpler: just remove the url_ok line entirely
    patch_file(blocks_path,
        "            and not networking.url_ok(self.local_url)\n",
        "            # and not networking.url_ok(self.local_url)  # patched\n",
        "PATCH 1b: url_ok commented out")

# ── PATCH 2: gradio_client/utils.py — handle bool schema ─────────────────────
try:
    import gradio_client.utils as _gcu
    gcu_path = _gcu.__file__
except Exception:
    gcu_path = None
print(f"\ngradio_client/utils.py: {gcu_path}")

patch_file(gcu_path,
    '    if "const" in schema:',
    '    if not isinstance(schema, dict): return "Any"\n    if "const" in schema:',
    "PATCH 2a: get_type dict guard")

if gcu_path and os.path.exists(gcu_path):
    with open(gcu_path) as f:
        src = f.read()
    if 'raise APIInfoParseError' in src:
        src = src.replace(
            'raise APIInfoParseError(f"Cannot parse schema {schema}")',
            'return "Any"  # patched: was APIInfoParseError'
        )
        with open(gcu_path, 'w') as f:
            f.write(src)
        print("  OK   PATCH 2b: APIInfoParseError suppressed")

# ── PATCH 3: routes.py — TemplateResponse keyword args ───────────────────────
routes_path = find_file('gradio', 'routes.py')
print(f"\nroutes.py: {routes_path}")

if routes_path and os.path.exists(routes_path):
    with open(routes_path) as f:
        src = f.read()
    # Fix TemplateResponse to use keyword args (new Starlette API)
    patched = re.sub(
        r'return templates\.TemplateResponse\(\s*\n(\s*)template,\s*\n\s*\{',
        r'return templates.TemplateResponse(\n\1name=template,\n\1context={',
        src
    )
    if patched != src:
        with open(routes_path, 'w') as f:
            f.write(patched)
        print("  OK   PATCH 3: routes.py TemplateResponse keyword args")
    else:
        # Check if already using keyword args
        if 'name=template' in src:
            print("  SKIP PATCH 3: already uses keyword args")
        else:
            print("  MISS PATCH 3: TemplateResponse pattern not found")

# ── PATCH 4: gradio/utils.py — asyncio event loop ────────────────────────────
utils_path = find_file('gradio', 'utils.py')
print(f"\ngradio/utils.py: {utils_path}")

if utils_path and os.path.exists(utils_path):
    with open(utils_path) as f:
        src = f.read()
    old_loop = '    event_loop = asyncio.get_event_loop()'
    new_loop = (
        '    try:\n'
        '        event_loop = asyncio.get_event_loop()\n'
        '    except RuntimeError:\n'
        '        event_loop = asyncio.new_event_loop()\n'
        '        asyncio.set_event_loop(event_loop)'
    )
    if old_loop in src:
        src = src.replace(old_loop, new_loop)
        with open(utils_path, 'w') as f:
            f.write(src)
        print("  OK   PATCH 4: utils.py event_loop RuntimeError fix")
    else:
        print("  SKIP PATCH 4: pattern not found")

print("\n=== patch_gradio.py done ===")
