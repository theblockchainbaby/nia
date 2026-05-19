"""Email builtins. Public surface for workers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import _imap


def sweep_recent(*, inputs: dict, context: dict) -> dict:
    """Pull recent inbox + sent activity across one or more accounts.

    Inputs:
      accounts: list of {label, user, pass, server, sent_folder}
      since_hours: int (default 48)

    Returns:
      {
        "accounts": [{label, inbox_count, sent_count}],
        "unanswered_inbox": [{from, subject, date_iso, account}],  # last 48h
        "recently_sent":    [{to, subject, date_iso, account}],
      }

    Determines "unanswered" by cross-referencing inbox senders against the
    sent folder of the SAME account within the lookback window. No LLM,
    no judgment — pure set logic.
    """
    raw_accounts = inputs.get("accounts") or []
    # If accounts is a string, treat it as a YAML file path that contains
    # a list under the `accounts` key. Keeps secrets out of the manifest.
    if isinstance(raw_accounts, str):
        import os
        import yaml
        path = os.path.expanduser(raw_accounts)
        with open(path) as f:
            data = yaml.safe_load(f)
        accounts = data.get("accounts", []) if isinstance(data, dict) else data
    else:
        accounts = raw_accounts
    since_hours = int(inputs.get("since_hours", 48))
    since_dt = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    summary: list[dict] = []
    inbox_msgs: list[dict] = []
    sent_msgs: list[dict] = []

    for a in accounts:
        try:
            m = _imap.open_inbox(a)
        except Exception as e:
            summary.append({"label": a.get("label", a.get("user")),
                            "error": str(e), "inbox_count": 0, "sent_count": 0})
            continue

        acct_inbox: list[dict] = []
        acct_sent: list[dict] = []

        # INBOX
        try:
            for msg in _imap.fetch_recent(m, "INBOX",
                                          since_days=max(2, (since_hours // 24) + 1)):
                acct_inbox.append({
                    "from": _imap.addr_of(msg.get("From")),
                    "from_name": _imap.decode_h(msg.get("From"))[:60],
                    "subject": _imap.decode_h(msg.get("Subject"))[:200],
                    "date_iso": _imap.msg_date_iso(msg.get("Date")),
                    "account": a.get("label", a.get("user")),
                })
        except Exception as e:
            summary.append({"label": a.get("label"), "inbox_error": str(e)})

        # SENT
        try:
            for msg in _imap.fetch_recent(m, a.get("sent_folder", "Sent"),
                                          since_days=max(2, (since_hours // 24) + 1)):
                acct_sent.append({
                    "to": _imap.addr_of(msg.get("To")),
                    "subject": _imap.decode_h(msg.get("Subject"))[:200],
                    "date_iso": _imap.msg_date_iso(msg.get("Date")),
                    "account": a.get("label", a.get("user")),
                })
        except Exception as e:
            summary.append({"label": a.get("label"), "sent_error": str(e)})

        try:
            m.logout()
        except Exception:
            pass

        inbox_msgs.extend(acct_inbox)
        sent_msgs.extend(acct_sent)
        summary.append({
            "label": a.get("label", a.get("user")),
            "inbox_count": len(acct_inbox),
            "sent_count": len(acct_sent),
        })

    # Cross-ref: an inbox message is "unanswered" if we have not sent
    # anything to that sender within the same window.
    sent_to = {(s["to"], s["account"]) for s in sent_msgs if s["to"]}
    unanswered: list[dict] = []
    for i in inbox_msgs:
        # ignore obvious noise
        if not i["from"] or any(d in i["from"] for d in
                                ("noreply", "no-reply", "donotreply",
                                 "mailer-daemon", "notifications@")):
            continue
        if (i["from"], i["account"]) not in sent_to:
            # also filter by time
            try:
                t = datetime.fromisoformat(i["date_iso"])
                if t < since_dt:
                    continue
            except Exception:
                pass
            unanswered.append(i)

    return {
        "accounts": summary,
        "unanswered_inbox": unanswered[:50],
        "unanswered_count": len(unanswered),
        "recently_sent": sent_msgs[-30:],
        "recently_sent_count": len(sent_msgs),
        "inbox_total": len(inbox_msgs),
    }
