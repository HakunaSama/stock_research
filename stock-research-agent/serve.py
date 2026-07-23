#!/usr/bin/env python3
"""Tiny read-only HTTP bridge exposing seeded ``context.json`` runs to the UI.

Stdlib only (``http.server``) — no FastAPI/Flask, matching this project's
dependency-light stance. It scans ``workdir`` for ``<run_id>/context.json``,
indexes them by ``query.target``, and serves:

    GET /api/runs                 -> [{target, run_id, status, score, ...}, ...]
    GET /api/research/<target>    -> the run's ``research`` slot (ResearchSlot)
    GET /api/kline/<target>       -> the run's K-line features + OHLCV bars
    GET /api/context/<target>     -> the full ResearchContext (for debugging)
    GET /healthz                  -> {"ok": true}

The frontend adapter maps ``/api/research/<target>`` onto its ``ResearchRun``
type. CORS is wide-open (dev tool, read-only, local only). If a target has
multiple runs, the most recently modified ``context.json`` wins.

Usage:
    python3 serve.py [--workdir ~/.hermes/stock] [--port 8787]
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse


def _scan_runs(workdir: str) -> Dict[str, Dict[str, Any]]:
    """Return {target: context_dict} keeping the newest context.json per target."""
    base = os.path.expanduser(workdir)
    latest: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    if not os.path.isdir(base):
        return {}
    for run_id in os.listdir(base):
        cpath = os.path.join(base, run_id, "context.json")
        if not os.path.isfile(cpath):
            continue
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                ctx = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        target = (ctx.get("query") or {}).get("target")
        if not target:
            continue
        mtime = os.path.getmtime(cpath)
        if target not in latest or mtime > latest[target][0]:
            latest[target] = (mtime, ctx)
    return {t: ctx for t, (_, ctx) in latest.items()}


def _run_summary(ctx: Dict[str, Any]) -> Dict[str, Any]:
    r = ctx.get("research") or {}
    k = ctx.get("kline") or {}
    return {
        "target": (ctx.get("query") or {}).get("target", ""),
        "run_id": ctx.get("run_id", ""),
        "engine": r.get("engine", ""),
        "status": r.get("status", ""),
        "score": r.get("score", 0),
        "attempts": r.get("attempts", 0),
        "threshold": r.get("threshold", 0),
        "kline_status": k.get("status", "placeholder"),
    }


def _load_kline(workdir: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble the K-line payload: the ``kline`` slot + persisted OHLCV bars.

    The slot lives in context.json; the raw OHLCV bars sit next to it in
    ``<run_id>/kline.json`` (written by ``fetch_kline``). Bars are optional —
    if the run was a placeholder or the file is missing, ``bars`` is [].
    """
    slot = dict(ctx.get("kline") or {})
    bars: List[Dict[str, Any]] = []
    run_id = ctx.get("run_id", "")
    if run_id:
        kpath = os.path.join(os.path.expanduser(workdir), run_id, "kline.json")
        if os.path.isfile(kpath):
            try:
                with open(kpath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    bars = loaded
            except (OSError, json.JSONDecodeError):
                bars = []
    return {
        "status": slot.get("status", "placeholder"),
        "symbol": slot.get("symbol", ""),
        "timeframe": slot.get("timeframe", ""),
        "range": slot.get("range", ""),
        "features": slot.get("features"),
        "bars": bars,
    }


class Handler(BaseHTTPRequestHandler):
    # ``workdir`` injected via server attribute (set in ``main``).
    workdir: str = "~/.hermes/stock"

    def _send(self, code: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 (http.server naming)
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/")
        runs = _scan_runs(self.workdir)

        if path in ("", "/healthz"):
            self._send(200, {"ok": True, "targets": sorted(runs.keys())})
            return

        if path == "/api/runs":
            self._send(200, [_run_summary(c) for c in runs.values()])
            return

        target, kind = self._match_target(path)
        if target is not None:
            ctx = runs.get(target)
            if ctx is None:
                self._send(404, {"error": f"no run for target {target!r}",
                                 "available": sorted(runs.keys())})
                return
            if kind == "research":
                slot = ctx.get("research") or {}
                self._send(200, {"target": target, "run_id": ctx.get("run_id", ""), **slot})
            elif kind == "kline":
                payload = _load_kline(self.workdir, ctx)
                self._send(200, {"target": target, "run_id": ctx.get("run_id", ""), **payload})
            else:  # full context
                self._send(200, ctx)
            return

        self._send(404, {"error": "not found", "path": path})

    @staticmethod
    def _match_target(path: str) -> Tuple[Optional[str], str]:
        for prefix, kind in (
            ("/api/research/", "research"),
            ("/api/kline/", "kline"),
            ("/api/context/", "context"),
        ):
            if path.startswith(prefix):
                return unquote(path[len(prefix):]), kind
        return None, ""

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter logs
        return


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve seeded stock-research runs.")
    ap.add_argument("--workdir", default="~/.hermes/stock",
                    help="dir containing <run_id>/context.json (default: ~/.hermes/stock)")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    Handler.workdir = args.workdir
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    targets = sorted(_scan_runs(args.workdir).keys())
    print(f"stock-research bridge on http://{args.host}:{args.port}")
    print(f"  workdir : {os.path.expanduser(args.workdir)}")
    print(f"  targets : {targets or '(none — run seed_runs.py first)'}")
    print(f"  routes  : /api/runs  /api/research/<target>  /api/kline/<target>  /api/context/<target>  /healthz")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
