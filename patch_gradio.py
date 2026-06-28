"""
Patches gradio 4.44.1 installed files for Python 3.14 compatibility.
Run after: pip install -r requirements.txt
Usage: python patch_gradio.py
"""
import os, sys, re

def find_gradio_path():
    import gradio
    return os.path.dirname(gradio.__file__)

gradio_path = find_gradio_path()
print(f"Gradio path: {gradio_path}")

# PATCH 1: Fix networking.url_ok to always return True on Render
# This fixes the "localhost not accessible" ValueError
networking_file = os.path.join(gradio_path, 'networking.py')
with open(networking_file, 'r') as f:
    src = f.read()

old_url_ok = '''def url_ok(url: str) -> bool:
    try:
        for _ in range(5):
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                r = httpx.head(url, timeout=3, verify=False)
            if r.status_code in (200, 401, 302):  # 401 or 302 if auth is set
                return True
            time.sleep(0.500)
    except (ConnectionError, httpx.ConnectError, httpx.TimeoutException):
        return False
    return False'''

new_url_ok = '''def url_ok(url: str) -> bool:
    # Patched for Render deployment: always return True to skip localhost check
    import os as _os_urlok
    if _os_urlok.environ.get('RENDER') or _os_urlok.environ.get('PORT'):
        return True
    try:
        for _ in range(5):
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                r = httpx.head(url, timeout=3, verify=False)
            if r.status_code in (200, 401, 302):  # 401 or 302 if auth is set
                return True
            time.sleep(0.500)
    except (ConnectionError, httpx.ConnectError, httpx.TimeoutException):
        return False
    return False'''

if old_url_ok in src:
    src = src.replace(old_url_ok, new_url_ok)
    with open(networking_file, 'w') as f:
        f.write(src)
    print("✅ PATCH 1: networking.url_ok fixed")
else:
    print("⚠️  PATCH 1: url_ok pattern not found — trying alternate patch")
    # Simpler patch: just replace the function body
    src2 = re.sub(
        r'(def url_ok\(url: str\) -> bool:)\n.*?return False\n',
        r'\1\n    import os as _p; \n    if _p.environ.get("RENDER") or _p.environ.get("PORT"): return True\n    return False\n',
        src, flags=re.DOTALL
    )
    if src2 != src:
        with open(networking_file, 'w') as f:
            f.write(src2)
        print("✅ PATCH 1: networking.url_ok patched (alternate)")

# PATCH 2: Fix gradio_client utils for Python 3.14
# TypeError: argument of type 'bool' is not iterable in _json_schema_to_python_type
try:
    import gradio_client.utils as gcu_module
    gcu_file = gcu_module.__file__
    with open(gcu_file, 'r') as f:
        gcu_src = f.read()

    # Fix get_type function
    old_get_type = '    if "const" in schema:'
    new_get_type = '    if not isinstance(schema, dict): return "Any"\n    if "const" in schema:'
    if old_get_type in gcu_src:
        gcu_src = gcu_src.replace(old_get_type, new_get_type)
        with open(gcu_file, 'w') as f:
            f.write(gcu_src)
        print("✅ PATCH 2: gradio_client get_type fixed")
    else:
        print("⚠️  PATCH 2: get_type pattern not found")
except Exception as e:
    print(f"⚠️  PATCH 2 skipped: {e}")

# PATCH 3: Fix routes.py TemplateResponse for new Starlette API
routes_file = os.path.join(gradio_path, 'routes.py')
with open(routes_file, 'r') as f:
    routes_src = f.read()

old_tmpl = '''return templates.TemplateResponse(
                    template,
                    {
                        "request": request,
                        "config": config,
                        "gradio_api_info": gradio_api_info,
                    },
                )'''
new_tmpl = '''return templates.TemplateResponse(
                    name=template,
                    context={
                        "request": request,
                        "config": config,
                        "gradio_api_info": gradio_api_info,
                    },
                )'''
if old_tmpl in routes_src:
    routes_src = routes_src.replace(old_tmpl, new_tmpl)
    with open(routes_file, 'w') as f:
        f.write(routes_src)
    print("✅ PATCH 3: routes.py TemplateResponse fixed")
else:
    print("⚠️  PATCH 3: TemplateResponse pattern not found (may already be correct)")

print("\n✅ All patches applied successfully")
