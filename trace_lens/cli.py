"""Command line: import traces, serve the API."""
from __future__ import annotations

import argparse
import sys

from .db import connect
from .importer import import_file
from .schema import TraceValidationError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trace_lens")
    sub = parser.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import", help="import trace JSON files")
    imp.add_argument("files", nargs="+")
    imp.add_argument("--db", default=None)
    srv = sub.add_parser("serve", help="run the API")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    if args.cmd == "import":
        conn = connect(args.db)
        status = 0
        for f in args.files:
            try:
                added = import_file(conn, f)
                print(f"{f}: {'imported' if added else 'already imported, skipped'}")
            except TraceValidationError as exc:
                print(f"{f}: REJECTED - {exc}", file=sys.stderr)
                status = 1
        return status

    import uvicorn

    uvicorn.run("trace_lens.api:app_factory", factory=True, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
