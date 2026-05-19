"""Notion builtins. Public surface for workers."""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

from . import _imap, _notion_client as nc


# DB IDs read from env so workers can be ported between Notion workspaces
# without code changes. Set these in the user's environment or a worker
# config layer in v0.2.
def _db(name: str, default: str = "") -> str:
    return os.environ.get(f"NOTION_DB_{name.upper()}", default)


# Built-in defaults match York's setup. Override via env for other users.
_DEFAULTS = {
    "CONTACTS":       "04e1e30542f7427b9ebe21f39f038c58",
    "DEALS":          "62532555858f4dda840edfc28b58a31c",
    "TASKS":          "c4960c7e2e5a45448ba11c527001f26a",
    "EMAIL_OUTREACH": "32a8abe80cd74065b110676eaa391ca7",
    "REMINDERS":      "32faa37989ad817e83e7cf0ad6ebf0da",
    "CONTENT":        "32faa37989ad81ed9575c645b5b70431",
}


def _resolve(name: str) -> str:
    return _db(name) or _DEFAULTS[name]


# ─── morning-ops: due reminders ─────────────────────────────────────────

def due_reminders(*, inputs: dict, context: dict) -> dict:
    """Return open reminders sorted by priority/due date.

    Inputs:
      max_items: int (default 5)
    """
    max_items = int(inputs.get("max_items", 5))
    res = nc.query_db(
        _resolve("REMINDERS"),
        filt={"and": [
            {"property": "Status", "select": {"does_not_equal": "Done"}},
            {"property": "Status", "select": {"does_not_equal": "Cancelled"}},
        ]},
        sorts=[{"property": "Due Date", "direction": "ascending"}],
    )
    items = []
    prio_order = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3, "": 4}
    for p in res.get("results", []):
        items.append({
            "title":    nc.extract(p, "Reminder"),
            "due":      nc.extract(p, "Due Date"),
            "priority": nc.extract(p, "Priority"),
            "business": nc.extract(p, "Business"),
            "status":   nc.extract(p, "Status"),
        })
    items.sort(key=lambda x: (prio_order.get(x["priority"], 4), x["due"] or "9999"))
    return {"reminders": items[:max_items], "total_open": len(items)}


# ─── notion-sync: email → Notion ────────────────────────────────────────

def email_sync(*, inputs: dict, context: dict) -> dict:
    """Sync recent email activity into Notion: log sent, bump Deal Last Contact.

    Inputs:
      accounts: list of email account dicts (same shape as email.sweep_recent)
      dry_run is honored from context — no writes happen if True.
    """
    raw_accounts = inputs.get("accounts") or []
    if isinstance(raw_accounts, str):
        import yaml
        path = os.path.expanduser(raw_accounts)
        with open(path) as f:
            data = yaml.safe_load(f)
        accounts = data.get("accounts", []) if isinstance(data, dict) else data
    else:
        accounts = raw_accounts
    dry = bool(context.get("dry_run"))

    pipeline = _pipeline_cache()
    stats = {
        "sent_logged": 0,
        "inbox_seen": 0,
        "deals_updated": 0,
        "errors": [],
    }
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    for a in accounts:
        ae = a["user"]
        biz = _business_for(ae)
        try:
            m = _imap.open_inbox(a)
        except Exception as e:
            stats["errors"].append(f"login {ae}: {e}")
            continue

        # SENT — log new and bump deals
        try:
            for msg in _imap.fetch_recent(m, a.get("sent_folder", "Sent"),
                                          since_days=2):
                to_addr = _imap.addr_of(msg.get("To"))
                subj = _imap.decode_h(msg.get("Subject"))[:200] or "(no subject)"
                date_iso = _imap.msg_date_iso(msg.get("Date"))
                if _seen_email(_resolve("EMAIL_OUTREACH"), subj, seven_days_ago):
                    continue
                if not dry:
                    try:
                        nc.create_page(_resolve("EMAIL_OUTREACH"), {
                            "Subject":   nc.title(subj),
                            "To":        nc.email(to_addr),
                            "Sent Date": nc.date_prop(date_iso[:10]),
                            "Business":  nc.select(biz) if biz else None,
                            "Sent From": nc.select(ae) if biz else nc.select("support@caipherai.com"),
                            "Status":    nc.select("Sent"),
                            "Notes":     nc.rich_text(f"Auto-logged from {ae}"),
                        })
                    except Exception as e:
                        stats["errors"].append(f"log_email: {e}")
                stats["sent_logged"] += 1
                if not dry and _bump_deal(pipeline, to_addr, date_iso):
                    stats["deals_updated"] += 1
        except Exception as e:
            stats["errors"].append(f"sent {ae}: {e}")

        # INBOX — count + bump deals
        try:
            for msg in _imap.fetch_recent(m, "INBOX", since_days=2):
                stats["inbox_seen"] += 1
                if not dry and _bump_deal(pipeline,
                                          _imap.addr_of(msg.get("From")),
                                          _imap.msg_date_iso(msg.get("Date"))):
                    stats["deals_updated"] += 1
        except Exception as e:
            stats["errors"].append(f"inbox {ae}: {e}")

        try:
            m.logout()
        except Exception:
            pass

    return stats


# ─── notion-sync: git → Notion Content Calendar ─────────────────────────

def git_sync(*, inputs: dict, context: dict) -> dict:
    """Detect new blog posts in tracked repos, log them to Content Calendar.

    Inputs:
      repos: list of {name, path, business, blog_glob}
    """
    import subprocess
    repos = inputs.get("repos") or []
    dry = bool(context.get("dry_run"))
    stats = {"commits_scanned": 0, "blog_posts_logged": 0, "errors": []}

    for repo in repos:
        path = repo.get("path")
        if not path or not os.path.isdir(path):
            continue
        try:
            out = subprocess.run(
                ["git", "-C", path, "log", "-30",
                 "--pretty=format:%H%x09%s%x09%cI", "--no-merges"],
                capture_output=True, text=True, timeout=15,
            )
            if out.returncode != 0:
                stats["errors"].append(f"git log {path}: {out.stderr[:100]}")
                continue
        except Exception as e:
            stats["errors"].append(f"git {path}: {e}")
            continue

        seen_slugs: set[str] = set()
        for line in out.stdout.strip().splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            sha, _subject, iso = parts
            stats["commits_scanned"] += 1
            try:
                files = subprocess.run(
                    ["git", "-C", path, "show", "--name-only",
                     "--pretty=format:", sha],
                    capture_output=True, text=True, timeout=10,
                ).stdout.strip().splitlines()
            except Exception:
                continue
            for f in files:
                if not (f.startswith("app/blog/") and f.endswith("/page.tsx")):
                    continue
                slug_parts = f.split("/")
                if len(slug_parts) < 3:
                    continue
                slug = slug_parts[2]
                if slug in {"layout.tsx", "page.tsx", "[slug]"} or slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                if dry:
                    continue
                try:
                    nc.create_page(_resolve("CONTENT"), {
                        "Title":          nc.title(f"Blog: {slug}"),
                        "Platform":       nc.select("Blog"),
                        "Business":       nc.select(repo.get("business", "Book")),
                        "Status":         nc.select("Posted"),
                        "Scheduled Date": nc.date_prop(iso[:10]),
                    })
                    stats["blog_posts_logged"] += 1
                except Exception as e:
                    stats["errors"].append(f"add_content {slug}: {e}")
    return stats


# ─── notion-sync: stripe → Notion ───────────────────────────────────────

def stripe_sync(*, inputs: dict, context: dict) -> dict:
    """Poll recent Stripe subscription events and add to Notion."""
    import json
    import urllib.parse
    import urllib.request

    stats = {"events_processed": 0, "contacts_added": 0, "deals_added": 0,
             "skipped": False, "errors": []}
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        stats["skipped"] = True
        return stats
    dry = bool(context.get("dry_run"))

    try:
        url = ("https://api.stripe.com/v1/events?" + urllib.parse.urlencode(
            [("limit", 25),
             ("types[]", "customer.subscription.created")], doseq=True))
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            events = json.loads(r.read()).get("data", [])
    except Exception as e:
        stats["errors"].append(f"stripe: {e}")
        return stats

    for ev in events:
        stats["events_processed"] += 1
        obj = ev.get("data", {}).get("object", {})
        cust_id = obj.get("customer")
        items = obj.get("items", {}).get("data", [])
        price_id = items[0].get("price", {}).get("id") if items else ""
        if not cust_id:
            continue
        if dry:
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(
                f"https://api.stripe.com/v1/customers/{cust_id}",
                headers={"Authorization": f"Bearer {key}"}), timeout=10) as r:
                customer = json.loads(r.read())
        except Exception as e:
            stats["errors"].append(f"stripe customer: {e}")
            continue
        name = customer.get("name") or customer.get("email", "Unknown")
        em = customer.get("email", "")
        try:
            nc.create_page(_resolve("CONTACTS"), {
                "Name":     nc.title(name),
                "Email":    nc.email(em),
                "Business": nc.select("Book"),
                "Role":     nc.rich_text("Subscriber"),
                "Source":   nc.select("Inbound"),
                "Notes":    nc.rich_text(f"Stripe customer {cust_id}, plan {price_id}"),
            })
            stats["contacts_added"] += 1
        except Exception as e:
            stats["errors"].append(f"add_contact: {e}")
    return stats


# ─── helpers ────────────────────────────────────────────────────────────

_PIPELINE: list[dict] | None = None

def _pipeline_cache() -> list[dict]:
    """Cache active deals once per run. Avoid 50× Notion queries per sync."""
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = []
        res = nc.query_db(_resolve("DEALS"), filt={"and": [
            {"property": "Stage", "select": {"does_not_equal": "Closed Won"}},
            {"property": "Stage", "select": {"does_not_equal": "Closed Lost"}},
        ]})
        for p in res.get("results", []):
            _PIPELINE.append({
                "page_id": p["id"],
                "deal_name": nc.extract(p, "Deal Name"),
                "contact_email": (nc.extract(p, "Contact Email") or "").lower(),
            })
    return _PIPELINE


def _bump_deal(pipeline: list[dict], addr: str, date_iso: str) -> bool:
    if not addr:
        return False
    addr = addr.lower()
    for d in pipeline:
        if d["contact_email"] == addr:
            try:
                nc.update_page(d["page_id"], {
                    "Last Contact": nc.date_prop(date_iso[:10]),
                })
                return True
            except Exception:
                return False
    return False


def _seen_email(db_id: str, subject: str, since_iso: str) -> bool:
    try:
        res = nc.query_db(db_id, filt={"and": [
            {"property": "Subject", "title": {"equals": subject[:100]}},
            {"property": "Sent Date", "date": {"on_or_after": since_iso[:10]}},
        ]}, page_size=2)
        return bool(res.get("results"))
    except Exception:
        return False


def _business_for(account_email: str) -> str | None:
    a = account_email.lower()
    if "vitros" in a: return "VitrOS"
    if "caipher" in a: return "Caipher AI"
    return None  # personal Gmail → don't tag
