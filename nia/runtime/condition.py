"""Tiny expression evaluator for `when` / `condition` / `{{ }}` templating.

Deliberately limited:
  - dotted attribute access on the run context: `actions.foo.results.bar`
  - comparison ops: == != > < >= <=
  - boolean ops:    and or not
  - membership:     `x in y`
  - filter syntax:  `x | length`
  - literals:       numbers, strings, true, false, none

NO function calls, NO arbitrary Python, NO side effects. The runtime relies
on this being safe — we eval condition expressions against untrusted-ish
manifest input, so we can't reach for `eval()`.
"""
from __future__ import annotations

from typing import Any


def evaluate(expr: str, ctx: dict) -> bool:
    """Evaluate a boolean expression. Returns False on parse error."""
    if not expr or expr.strip().lower() == "true":
        return True
    if expr.strip().lower() == "false":
        return False
    try:
        return bool(_eval(_tokenize(expr), ctx))
    except Exception:
        return False


def access(expr: str, ctx: dict) -> Any:
    """Resolve a dotted-path expression like `config.accounts`. Returns None
    if any segment is missing. Used for `{{ }}` input templating."""
    try:
        return _eval(_tokenize(expr), ctx)
    except Exception:
        return None


# ─── tokenizer ──────────────────────────────────────────────────────────

def _tokenize(expr: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(expr):
        c = expr[i]
        if c.isspace():
            i += 1
            continue
        if c in "()|":
            out.append(c)
            i += 1
            continue
        if c in "<>=!":
            j = i + 1
            if j < len(expr) and expr[j] == "=":
                out.append(expr[i:j + 1]); i = j + 1; continue
            out.append(c); i += 1; continue
        if c in '"\'':
            j = i + 1
            while j < len(expr) and expr[j] != c:
                j += 1
            out.append(expr[i:j + 1]); i = j + 1; continue
        j = i
        while j < len(expr) and not expr[j].isspace() and expr[j] not in "()|<>=!":
            j += 1
        out.append(expr[i:j]); i = j
    return out


# ─── evaluator ───────────────────────────────────────────────────────────
#
# Single-pass recursive descent. Operator precedence (low → high):
#   or  >  and  >  not  >  comparisons (==, !=, <, >, <=, >=, in)  >  pipe (|length)  >  primary

def _eval(tokens: list[str], ctx: dict) -> Any:
    pos = [0]

    def peek() -> str | None:
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def consume() -> str:
        t = tokens[pos[0]]; pos[0] += 1; return t

    def parse_or() -> Any:
        left = parse_and()
        while peek() == "or":
            consume()
            right = parse_and()
            left = bool(left) or bool(right)
        return left

    def parse_and() -> Any:
        left = parse_not()
        while peek() == "and":
            consume()
            right = parse_not()
            left = bool(left) and bool(right)
        return left

    def parse_not() -> Any:
        if peek() == "not":
            consume()
            return not bool(parse_not())
        return parse_cmp()

    def parse_cmp() -> Any:
        left = parse_pipe()
        ops = {"==", "!=", ">", "<", ">=", "<=", "in"}
        while peek() in ops:
            op = consume()
            right = parse_pipe()
            if op == "==": left = left == right
            elif op == "!=": left = left != right
            elif op == ">":  left = left > right
            elif op == "<":  left = left < right
            elif op == ">=": left = left >= right
            elif op == "<=": left = left <= right
            elif op == "in": left = left in right
        return left

    def parse_pipe() -> Any:
        left = parse_primary()
        while peek() == "|":
            consume()
            filt = consume()
            if filt == "length":
                left = len(left) if left is not None else 0
            else:
                raise ValueError(f"unknown filter: {filt}")
        return left

    def parse_primary() -> Any:
        t = consume()
        if t == "(":
            v = parse_or()
            if peek() != ")":
                raise ValueError("expected )")
            consume()
            return v
        # Literals
        if t.lower() == "true": return True
        if t.lower() == "false": return False
        if t.lower() in ("none", "null"): return None
        if t.startswith(('"', "'")) and t.endswith((t[0],)):
            return t[1:-1]
        # Numbers
        try:
            if "." in t: return float(t)
            return int(t)
        except ValueError:
            pass
        # Dotted path against context
        return _resolve_path(t, ctx)

    return parse_or()


def _resolve_path(path: str, ctx: dict) -> Any:
    cur: Any = ctx
    for seg in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(seg)
        else:
            cur = getattr(cur, seg, None)
    return cur
