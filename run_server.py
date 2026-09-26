"""
TEMPORARY DEV-ONLY LAUNCHER — SAFE TO DELETE
=============================================
This script exists solely to work around a known PyTorch 2.x / Python 3.12
incompatibility where `torch.utils._config_module` calls `inspect.getsource()`
on a module object that has no retrievable source, raising:

    OSError: could not get source code

And where `torch._jit_internal._check_overload_body` calls `parse_def()` which
calls `torch._sources.get_source_lines_and_file()` which also fails on
frozen/built-in functions.

The workaround: monkey-patch `inspect.getsource` and `inspect.findsource`
BEFORE any `torch` or `transformers` import occurs, so the calls degrade
gracefully instead of crashing.

NOTHING in app/ is modified. The original backend code is untouched.

To run the real backend without this workaround (e.g. in production or once
torch is upgraded), use:
    uvicorn app.api.main:app --port 8000

To run with this workaround during local admin-frontend development:
    python run_server.py
"""

import ast
import inspect
import textwrap
import warnings

# --- Monkey-patch: intercept the OSError from inspect.getsource/findsource ---

# A valid single-function definition stub that satisfies torch._sources.parse_def:
#   ast.parse → body[0] must be an ast.FunctionDef with a pass body.
_STUB_FUNCTION = "def _stub():\n    pass\n"

_original_getsource = inspect.getsource
_original_findsource = inspect.findsource
_original_getsourcelines = inspect.getsourcelines

def _patched_getsource(obj):
    try:
        return _original_getsource(obj)
    except OSError:
        # Return a valid function definition that torch.parse_def will accept
        if callable(obj) and not isinstance(obj, type):
            name = getattr(obj, '__name__', '_stub')
            return f"def {name}():\n    pass\n"
        return _STUB_FUNCTION

def _patched_findsource(obj):
    try:
        return _original_findsource(obj)
    except OSError:
        if callable(obj) and not isinstance(obj, type):
            name = getattr(obj, '__name__', '_stub')
            lines = [f"def {name}():\n", "    pass\n"]
        else:
            lines = ["def _stub():\n", "    pass\n"]
        return (lines, 0)

def _patched_getsourcelines(obj):
    try:
        return _original_getsourcelines(obj)
    except OSError:
        if callable(obj) and not isinstance(obj, type):
            name = getattr(obj, '__name__', '_stub')
            lines = [f"def {name}():\n", "    pass\n"]
        else:
            lines = ["def _stub():\n", "    pass\n"]
        return (lines, 1)

inspect.getsource = _patched_getsource
inspect.findsource = _patched_findsource
inspect.getsourcelines = _patched_getsourcelines

# --- End monkey-patch --------------------------------------------------------

import uvicorn  # noqa: E402 — must import after patch

if __name__ == "__main__":
    # Import the real, unmodified FastAPI app
    from app.api.main import app  # noqa: E402
    uvicorn.run(app, host="127.0.0.1", port=8000)
