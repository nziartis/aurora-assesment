"""
Dataset analysis script for the November 7 member messages API.
Run with: python analyze.py
No dependencies beyond the standard library.
"""

import re
import time
import json
import urllib.request
from collections import defaultdict, Counter
from datetime import datetime, timezone


API_URL = "https://november7-730026606190.europe-west1.run.app/messages/"
PAGE_SIZE = 100
MAX_RETRIES = 5
RETRY_SLEEP = 2.0


def fetch_all() -> list[dict]:
    all_messages = []
    skip = 0
    total = None

    while True:
        fetched = False
        for attempt in range(MAX_RETRIES):
            try:
                url = f"{API_URL}?skip={skip}&limit={PAGE_SIZE}"
                with urllib.request.urlopen(url, timeout=15) as r:
                    data = json.loads(r.read())
                if total is None:
                    total = data["total"]
                all_messages.extend(data["items"])
                skip += len(data["items"])
                fetched = True
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_SLEEP)
        if not fetched:
            print(f"  [!] Stopped at skip={skip} after {MAX_RETRIES} failed attempts")
            break
        if skip >= total:
            break

    return all_messages, total


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def analyze():
    print("Fetching messages...")
    messages, api_total = fetch_all()

    section("FETCH SUMMARY")
    print(f"  API total field : {api_total}")
    print(f"  Messages fetched: {len(messages)}")
    if api_total != len(messages):
        print(f"  [!] Discrepancy : {api_total - len(messages)} messages missing")
    else:
        print(f"  No discrepancy.")

    # --- User distribution ---
    section("USER DISTRIBUTION")
    by_user: dict[str, list[dict]] = defaultdict(list)
    for m in messages:
        by_user[m["user_name"]].append(m)
    for name, msgs in sorted(by_user.items(), key=lambda x: -len(x[1])):
        print(f"  {name}: {len(msgs)} messages")
    print(f"\n  Total members: {len(by_user)}")

    # --- user_id <-> user_name consistency ---
    section("USER ID / NAME CONSISTENCY")
    id_to_names: dict[str, set] = defaultdict(set)
    name_to_ids: dict[str, set] = defaultdict(set)
    for m in messages:
        id_to_names[m["user_id"]].add(m["user_name"])
        name_to_ids[m["user_name"]].add(m["user_id"])
    issues = False
    for uid, names in id_to_names.items():
        if len(names) > 1:
            print(f"  [!] user_id {uid} maps to multiple names: {names}")
            issues = True
    for name, ids in name_to_ids.items():
        if len(ids) > 1:
            print(f"  [!] {name} has multiple user_ids: {ids}")
            issues = True
    if not issues:
        print("  All user_id <-> user_name mappings are 1:1. No issues.")

    # --- Duplicate IDs ---
    section("DUPLICATE MESSAGE IDs")
    id_counts = Counter(m["id"] for m in messages)
    dupes = {k: v for k, v in id_counts.items() if v > 1}
    if dupes:
        print(f"  [!] {len(dupes)} duplicate IDs:")
        for mid, count in list(dupes.items())[:5]:
            print(f"    id={mid} appears {count}x")
    else:
        print("  No duplicate message IDs.")

    # --- Duplicate content ---
    section("DUPLICATE MESSAGE CONTENT")
    content_counts = Counter((m["user_name"], m["message"].strip()) for m in messages)
    content_dupes = {k: v for k, v in content_counts.items() if v > 1}
    if content_dupes:
        print(f"  [!] {len(content_dupes)} (user, content) pairs duplicated:")
        for (name, msg), count in sorted(content_dupes.items(), key=lambda x: -x[1])[:5]:
            print(f"    [{count}x] {name}: \"{msg[:80]}\"")
    else:
        print("  No duplicate message content.")

    # --- Timestamp analysis ---
    section("TIMESTAMP ANALYSIS")
    timestamps = []
    bad_ts = []
    for m in messages:
        try:
            ts = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
            timestamps.append((ts, m))
        except Exception:
            bad_ts.append(m)

    timestamps.sort(key=lambda x: x[0])
    now = datetime(2026, 3, 4, tzinfo=timezone.utc)
    future = [(ts, m) for ts, m in timestamps if ts > now]

    print(f"  Earliest message : {timestamps[0][0].date()}")
    print(f"  Latest message   : {timestamps[-1][0].date()}")
    span = (timestamps[-1][0] - timestamps[0][0]).days
    print(f"  Span             : {span} days")
    print(f"  Unparseable      : {len(bad_ts)}")
    if future:
        print(f"  [!] Future-dated : {len(future)}")
        for ts, m in future[:3]:
            print(f"    [{m['user_name']}] {ts.date()}: \"{m['message'][:60]}\"")
    else:
        print(f"  No future-dated messages.")

    # --- Message content quality ---
    section("MESSAGE CONTENT QUALITY")
    empty = [m for m in messages if not m["message"].strip()]
    short = [m for m in messages if 0 < len(m["message"].strip()) < 10]
    lengths = [len(m["message"]) for m in messages]

    print(f"  Empty messages    : {len(empty)}")
    print(f"  Truncated (<10ch) : {len(short)}")
    for m in short:
        print(f"    [{m['user_name']}] \"{m['message']}\"")
    print(f"  Avg length        : {sum(lengths) // len(lengths)} chars")
    print(f"  Min / Max length  : {min(lengths)} / {max(lengths)} chars")

    # --- PII detection ---
    section("PII DETECTION")
    cc_re = re.compile(r"\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b")
    phone_re = re.compile(r"\b(\+\d{1,3}[\s-])?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}\b")
    email_re = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

    for label, pattern in [("Credit card numbers", cc_re), ("Phone numbers", phone_re), ("Email addresses", email_re)]:
        hits = [m for m in messages if pattern.search(m["message"])]
        print(f"\n  {label}: {len(hits)} messages")
        for m in hits[:5]:
            print(f"    [{m['user_name']}] \"{m['message'][:100]}\"")

    # --- Activity patterns ---
    section("ACTIVITY PATTERNS PER MEMBER")
    for name, msgs in sorted(by_user.items()):
        ts_list = sorted(
            datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
            for m in msgs
        )
        gaps = [(ts_list[i + 1] - ts_list[i]).days for i in range(len(ts_list) - 1)]
        same_day = sum(1 for g in gaps if g == 0)
        print(
            f"  {name}: {len(msgs)} msgs | "
            f"max gap {max(gaps)}d | "
            f"{same_day} same-day pairs ({100*same_day//len(gaps)}%)"
        )

    print(f"\n{'=' * 60}")
    print("  Analysis complete.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    analyze()
