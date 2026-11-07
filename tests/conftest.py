"""Load the repo root as the `ichor` package, whatever the checkout directory is called."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if "ichor" not in sys.modules:
    spec = importlib.util.spec_from_file_location("ichor", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ichor"] = module
    spec.loader.exec_module(module)
