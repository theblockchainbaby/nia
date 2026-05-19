"""Thin Notion HTTP client used by builtins. Internal — workers should not
import this directly; they call the public builtins in notion.py.

stdlib-only: urllib + json. No `notion-client` package dep.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime
from typing import Any


BASE = "https://api.notion.com/v1"


def _headers() -> dict[str, str]:
    key = os.environ.get("NOTION_API_KEY", "")
    if not key:
        raise RuntimeError(
            "NOTION_API_KEY not set. Workers that touch Notion need this in the environment."
        )
    return {
        "Authorization": f"Bearer {key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def request(method: str, path: str, body: dict | None = None, timeout: int = 20) -> dict:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Notion {method} {path} → {e.code}: {e.read()[:200].decode()}")


def query_db(db_id: str, filt: dict | None = None, sorts: list | None = None,
             page_size: int = 100) -> dict:
    payload: dict[str, Any] = {"page_size": page_size}
    if filt: payload["filter"] = filt
    if sorts: payload["sorts"] = sorts
    return request("POST", f"/databases/{db_id}/query", payload)


def update_page(page_id: str, properties: dict) -> dict:
    return request("PATCH", f"/pages/{page_id}", {"properties": properties})


def create_page(database_id: str, properties: dict) -> dict:
    return request("POST", "/pages", {
        "parent": {"database_id": database_id},
        "properties": properties,
    })


# ─── property builders (one per Notion type we touch) ───────────────────

def title(v: str) -> dict:
    return {"title": [{"text": {"content": v[:2000]}}]}

def rich_text(v: str) -> dict:
    return {"rich_text": [{"text": {"content": v[:2000]}}]}

def select(v: str) -> dict:
    return {"select": {"name": v}}

def date_prop(v: str | None) -> dict:
    if not v:
        return {"date": None}
    return {"date": {"start": v}}

def email(v: str) -> dict:
    return {"email": v or None}

def number(v) -> dict:
    return {"number": float(v) if v is not None else None}


# ─── property extractor (reverse direction) ─────────────────────────────

def extract(page: dict, prop: str) -> Any:
    pr = page.get("properties", {}).get(prop, {})
    t = pr.get("type")
    if t == "title":
        return "".join(b.get("plain_text", "") for b in pr.get("title", []))
    if t == "rich_text":
        return "".join(b.get("plain_text", "") for b in pr.get("rich_text", []))
    if t == "select":
        return (pr.get("select") or {}).get("name", "")
    if t == "status":
        return (pr.get("status") or {}).get("name", "")
    if t == "date":
        return ((pr.get("date") or {}).get("start") or "")
    if t == "email":
        return pr.get("email", "") or ""
    if t == "number":
        return pr.get("number")
    if t == "checkbox":
        return pr.get("checkbox", False)
    return ""


def today_iso() -> str:
    return date.today().isoformat()
