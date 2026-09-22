#!/usr/bin/env python3
"""Decide what a comments endpoint actually answered, following redirects safely.

This exists because the first Stage 1 apply failed on a check that was wrong in
two separate ways, and both are the kind of wrong that a shell one-liner hides.

**It probed the wrong port.** The check asked `http://127.0.0.1:9121`, which is
the Animedia site runtime. The comments API lives in an nginx `location` block;
requests that never pass through nginx never reach it. So the probe hit the
site, the site normalised `/api/comments` to `/api/comments/` with a 308, and
the script read that as "the visitor was not refused". It could not have read
anything else: there was no gateway on that path to answer.

**It treated any non-503 as failure.** A 308 from a trailing-slash rule is
routine and says nothing about who may read comments. What matters is where the
chain *ends*, and whether every hop stayed on the same host.

So this module follows the chain itself, with rules a shell pipeline cannot
express:

* bounded hops, and a repeat of any URL is a loop rather than a slow success;
* every hop must stay on the same host — a redirect to another host is an
  escape, whatever status code carries it;
* a downgrade from https to http is refused even on the same host;
* the verdict is drawn from the *final* response, and the chain is reported
  whole so an operator can see how it got there.

Exit status is the verdict, so a shell script can branch on it without parsing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

MAX_HOPS = 5

# What an ordinary visitor may receive from a comments endpoint during an
# owner-only pilot. 503 is the designed refusal; 404 is the honest answer when
# the route does not exist at all, which is the correct state after a rollback.
CLOSED_CODES = frozenset({401, 403, 404, 405, 501, 503})

# What an ordinary visitor must never receive: a served read or an accepted
# write. 200 on a comments endpoint means the gate is open.
OPEN_CODES = frozenset({200, 201, 202, 206})

REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


@dataclass
class Hop:
    url: str
    code: int
    location: str = ""
    served_by_gateway: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "code": self.code,
            "location": self.location,
            "served_by_gateway": self.served_by_gateway,
        }


@dataclass
class ChainResult:
    hops: list[Hop] = field(default_factory=list)
    verdict: str = "UNKNOWN"
    reason: str = ""

    @property
    def final(self) -> Hop | None:
        return self.hops[-1] if self.hops else None

    @property
    def codes(self) -> str:
        return " -> ".join(str(h.code) for h in self.hops)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "codes": self.codes,
            "hops": [h.as_dict() for h in self.hops],
            "final_code": self.final.code if self.final else None,
            "final_is_gateway": bool(self.final and self.final.served_by_gateway),
        }


def _curl(url: str, method: str, resolve: str, cookie: str) -> tuple[int, str, str]:
    """One request, no redirect following. Returns (code, location, headers)."""
    cmd = [
        "curl", "-sS", "-m", "12", "-o", "/dev/null", "-D", "-",
        "-X", method, "-w", "\n__CODE__%{http_code}\n__LOC__%{redirect_url}\n",
    ]
    if resolve:
        cmd += ["--resolve", resolve]
    if cookie:
        cmd += ["-H", f"Cookie: {cookie}"]
    if method == "POST":
        cmd += ["-H", "Content-Type: application/json", "-d", "{}"]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    code = 0
    location = ""
    for line in out.splitlines():
        if line.startswith("__CODE__"):
            code = int(line[8:] or 0)
        elif line.startswith("__LOC__"):
            location = line[7:]
    return code, location, out


def _is_gateway(headers: str) -> bool:
    """Did the comments gateway answer this, rather than the site runtime?

    Judged on a header the gateway sets and the site does not. Guessing from
    the body would be guessing; the absence of this header on a 404 is exactly
    how a rollback is confirmed.
    """
    lowered = headers.lower()
    return "x-comments-module-version:" in lowered or "comments-gateway" in lowered


def follow(url: str, *, method: str = "GET", resolve: str = "", cookie: str = "") -> ChainResult:
    result = ChainResult()
    seen: set[str] = set()
    current = url

    for _ in range(MAX_HOPS):
        if current in seen:
            result.verdict = "REDIRECT_LOOP"
            result.reason = f"{current} was visited twice"
            return result
        seen.add(current)

        code, location, headers = _curl(current, method, resolve, cookie)
        hop = Hop(url=current, code=code, location=location,
                  served_by_gateway=_is_gateway(headers))
        result.hops.append(hop)

        if code == 0:
            result.verdict = "UNREACHABLE"
            result.reason = "no response"
            return result

        if code not in REDIRECT_CODES or not location:
            return _classify(result)

        before, after = urlsplit(current), urlsplit(location)
        if after.hostname != before.hostname:
            result.verdict = "HOST_CHANGED"
            result.reason = f"{before.hostname} -> {after.hostname}"
            return result
        if before.scheme == "https" and after.scheme == "http":
            result.verdict = "SCHEME_DOWNGRADED"
            result.reason = f"{current} -> {location}"
            return result
        current = location

    result.verdict = "TOO_MANY_REDIRECTS"
    result.reason = f"more than {MAX_HOPS} hops"
    return result


def _classify(result: ChainResult) -> ChainResult:
    final = result.final
    assert final is not None

    if final.code in OPEN_CODES:
        result.verdict = "OPEN"
        result.reason = (
            f"final {final.code} from "
            + ("the comments gateway" if final.served_by_gateway else "the site")
        )
    elif final.code in CLOSED_CODES:
        result.verdict = "CLOSED"
        result.reason = f"final {final.code}"
    elif 500 <= final.code < 600:
        result.verdict = "SERVER_ERROR"
        result.reason = f"final {final.code}"
    else:
        result.verdict = "UNEXPECTED"
        result.reason = f"final {final.code}"
    return result


# --- verdict helpers the shell scripts branch on ---------------------------

def expect_closed_visitor(result: ChainResult) -> tuple[bool, str]:
    """An ordinary visitor during an owner-only pilot.

    A first same-host redirect is fine. What must hold is that the chain ends
    closed — and that the endpoint did not quietly serve a read.
    """
    if result.verdict != "CLOSED":
        return False, f"expected a closed final answer, got {result.verdict}: {result.reason}"
    return True, f"visitor refused, chain {result.codes}"


def expect_no_gateway(result: ChainResult) -> tuple[bool, str]:
    """After a rollback: nothing on this path may be the comments gateway."""
    if any(h.served_by_gateway for h in result.hops):
        return False, "a hop was answered by the comments gateway"
    if result.verdict not in ("CLOSED", "UNREACHABLE"):
        return False, f"expected no route, got {result.verdict}: {result.reason}"
    return True, f"no gateway on this path, chain {result.codes}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--resolve", default="", help="curl --resolve host:port:addr")
    parser.add_argument("--cookie", default="", help="cookie header value")
    parser.add_argument(
        "--expect", choices=("closed-visitor", "no-gateway", "report"), default="report"
    )
    args = parser.parse_args(argv)

    result = follow(args.url, method=args.method, resolve=args.resolve, cookie=args.cookie)
    payload = result.as_dict()

    if args.expect == "report":
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    check = expect_closed_visitor if args.expect == "closed-visitor" else expect_no_gateway
    ok, message = check(result)
    payload["check"] = args.expect
    payload["ok"] = ok
    payload["message"] = message
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
