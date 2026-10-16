"""Print the OpenAPI schema as JSON without starting the server or reading settings.

Usage: fenix-openapi > webapp/openapi.json
"""

import json
import sys
from typing import Any

from fenix.main import build_app


def build_schema() -> dict[str, Any]:
    return build_app().openapi()


def main() -> None:
    json.dump(build_schema(), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
