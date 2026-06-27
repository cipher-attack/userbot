from telethon.tl.functions.channels import InviteToChannelRequest, GetParticipantsRequest
from telethon.tl.types import (
    ChannelParticipantsSearch, ChannelParticipantsRecent,
    UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth,
    UserStatusOnline, UserStatusOffline
)
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, UserNotMutualContactError,
    ChatAdminRequiredError, UserBannedInChannelError, PeerFloodError,
    UserKickedError, ChannelPrivateError, InputUserDeactivatedError
)

import asyncio
import logging
import json
import time
import random
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from core.utils import safe_register

logger = logging.getLogger(__name__)

# data models

@dataclass
class UserRecord:
    id: int
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    phone: Optional[str]
    is_premium: bool
    last_seen_bucket: str
    source: str
    collected_at: float = field(default_factory=time.time)
    result: Optional[str] = None

    def display_name(self):
        parts = [self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts)


@dataclass
class GrowthSession:
    users: list[UserRecord] = field(default_factory=list)
    rejected_ids: set = field(default_factory=set)
    filters: dict = field(default_factory=lambda: {
        "max_last_seen": "last_month",
        "require_username": False,
        "require_phone": False,
        "exclude_premium": False,
        "max_count": 5000,
    })
    op_running: bool = False
    op_cancelled: bool = False
    op_start_time: Optional[float] = None
    op_progress: dict = field(default_factory=dict)

    def clear_users(self):
        self.users.clear()

    def to_export(self) -> str:
        return json.dumps([asdict(u) for u in self.users], indent=2)

    def from_import(self, raw: str):
        data = json.loads(raw)
        self.users = [UserRecord(**d) for d in data]


# globals

SESSION = GrowthSession()
EXPORT_PATH = "/tmp/growth_export.json"
SEEN_ORDER = ["online", "recently", "last_week", "last_month", "unknown"]


# helpers

def classify_last_seen(status) -> str:
    if isinstance(status, UserStatusOnline):    return "online"
    if isinstance(status, UserStatusRecently):  return "recently"
    if isinstance(status, UserStatusLastWeek):  return "last_week"
    if isinstance(status, UserStatusLastMonth): return "last_month"
    return "unknown"


def passes_filter(rec: UserRecord, filters: dict) -> bool:
    max_seen = filters.get("max_last_seen", "last_month")
    if max_seen != "any":
        allowed = SEEN_ORDER[: SEEN_ORDER.index(max_seen) + 1]
        if rec.last_seen_bucket not in allowed:
            return False
    if filters.get("require_username") and not rec.username:
        return False
    if filters.get("require_phone") and not rec.phone:
        return False
    if filters.get("exclude_premium") and rec.is_premium:
        return False
    return True


def smart_sleep(base: float = 10.0) -> float:
    return base + random.uniform(-2.5, 4.0)


def format_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:  return f"{h}h {m}m {s}s"
    if m:  return f"{m}m {s}s"
    return f"{s}s"


def eta_string(done: int, total: int, elapsed: float) -> str:
    if done == 0: return "calculating..."
    return format_duration((total - done) / (done / elapsed))


# commands

@safe_register(pattern=r'\.scrape (.+)')
async def scrape_target(event):
    global SESSION

    if SESSION.op_running:
        return await event.edit(
            "· operation already in progress\n"
            "  use `.gstop` to cancel first"
        )

    targets   = [t.strip() for t in event.pattern_match.group(1).strip().split() if t.strip()]
    filters   = SESSION.filters
    max_count = filters.get("max_count", 5000)

    SESSION.op_running    = True
    SESSION.op_cancelled  = False
    SESSION.op_start_time = time.time()
    SESSION.clear_users()

    seen_ids    = set()
    total_found = 0
    errors      = []

    await event.edit(
        f"· sources  : {', '.join(targets)}\n"
        f"· limit    : {max_count}\n"
        f"· activity : ≤ {filters['max_last_seen']}\n"
        f"  working..."
    )

    for target in targets:
        if SESSION.op_cancelled or total_found >= max_count:
            break

        target_count   = 0
        skipped_filter = 0
        skipped_dup    = 0

        try:
            async for tl_user in event.client.iter_participants(
                target,
                filter=ChannelParticipantsRecent(),
                aggressive=True
            ):
                if SESSION.op_cancelled or total_found >= max_count:
                    break

                if tl_user.bot or tl_user.deleted:
                    continue
                if tl_user.id in seen_ids:
                    skipped_dup += 1
                    continue

                bucket = classify_last_seen(tl_user.status)
                record = UserRecord(
                    id=tl_user.id,
                    username=tl_user.username,
                    first_name=tl_user.first_name or "",
                    last_name=tl_user.last_name,
                    phone=tl_user.phone,
                    is_premium=getattr(tl_user, "premium", False),
                    last_seen_bucket=bucket,
                    source=target,
                )

                if not passes_filter(record, filters) or record.id in SESSION.rejected_ids:
                    skipped_filter += 1
                    continue

                SESSION.users.append(record)
                seen_ids.add(tl_user.id)
                total_found  += 1
                target_count += 1

                if total_found % 100 == 0:
                    elapsed = time.time() - SESSION.op_start_time
                    await event.edit(
                        f"· source   : {target}\n"
                        f"· found    : {total_found}\n"
                        f"· filtered : {skipped_filter}\n"
                        f"· dupes    : {skipped_dup}\n"
                        f"· elapsed  : {format_duration(elapsed)}"
                    )

        except ChannelPrivateError:
            errors.append(f"{target}: private / no access")
        except Exception as e:
            errors.append(f"{target}: {str(e)[:80]}")

    SESSION.op_running = False
    elapsed = time.time() - SESSION.op_start_time

    source_counts  = {}
    seen_breakdown = {}
    for u in SESSION.users:
        source_counts[u.source]            = source_counts.get(u.source, 0) + 1
        seen_breakdown[u.last_seen_bucket] = seen_breakdown.get(u.last_seen_bucket, 0) + 1

    source_lines = "\n".join(f"  {src}: {cnt}" for src, cnt in source_counts.items())
    seen_lines   = "\n".join(
        f"  {k}: {v}"
        for k, v in sorted(
            seen_breakdown.items(),
            key=lambda x: SEEN_ORDER.index(x[0]) if x[0] in SEEN_ORDER else 99
        )
    )

    error_section  = ("\n\nerrors:\n" + "\n".join(f"  {e}" for e in errors)) if errors else ""
    cancelled_note = "\n· stopped early" if SESSION.op_cancelled else ""

    await event.edit(
        f"· total    : {len(SESSION.users)}\n"
        f"· duration : {format_duration(elapsed)}\n\n"
        f"by source:\n{source_lines}\n\n"
        f"by activity:\n{seen_lines}"
        f"{error_section}"
        f"{cancelled_note}\n\n"
        f"next: `.addmembers @YourGroup`"
    )


@safe_register(pattern=r'\.addmembers (.+)')
async def start_adding(event):
    global SESSION

    if SESSION.op_running:
        return await event.edit(
            "· operation already in progress\n"
            "  use `.gstop` to cancel"
        )

    if not SESSION.users:
        return await event.edit(
            "· session is empty\n"
            "  run `.scrape @group` first"
        )

    dest = event.pattern_match.group(1).strip()

    SESSION.op_running    = True
    SESSION.op_cancelled  = False
    SESSION.op_start_time = time.time()

    await event.edit(f"· reading {dest}...")

    try:
        existing_ids = set()
        async for member in event.client.iter_participants(dest):
            existing_ids.add(member.id)
    except Exception as e:
        SESSION.op_running = False
        return await event.edit(f"· could not read {dest}\n  {e}")

    def activity_score(u: UserRecord) -> int:
        return SEEN_ORDER.index(u.last_seen_bucket) if u.last_seen_bucket in SEEN_ORDER else 99

    candidates    = sorted([u for u in SESSION.users if u.id not in existing_ids], key=activity_score)
    already_there = len(SESSION.users) - len(candidates)

    SESSION.op_progress = {
        "total": len(candidates),
        "success": 0,
        "privacy": 0,
        "flood_pauses": 0,
        "already": already_there,
        "banned": 0,
        "other_errors": 0,
        "current_index": 0,
        "dest": dest,
    }

    await event.edit(
        f"· destination : {dest}\n"
        f"· to process  : {len(candidates)}\n"
        f"· already in  : {already_there}\n"
        f"· order       : most active first\n\n"
        f"`.gstatus` to check · `.gstop` to cancel"
    )

    p                  = SESSION.op_progress
    consecutive_errors = 0
    sleep_base         = 10.0

    for i, user in enumerate(candidates):
        if SESSION.op_cancelled:
            break

        p["current_index"] = i

        try:
            await event.client(InviteToChannelRequest(channel=dest, users=[user.id]))
            user.result = "success"
            p["success"] += 1
            consecutive_errors = 0

            if p["success"] % 20 == 0 and sleep_base > 8:
                sleep_base = max(8.0, sleep_base - 0.5)

            await asyncio.sleep(smart_sleep(sleep_base))

        except FloodWaitError as e:
            user.result = "flood"
            p["flood_pauses"] += 1
            wait = e.seconds + random.randint(5, 15)
            await event.respond(f"· rate limit — pausing {wait}s, will resume")
            await asyncio.sleep(wait)
            sleep_base = min(sleep_base + 2.0, 20.0)

        except UserPrivacyRestrictedError:
            user.result = "privacy"
            p["privacy"] += 1
            SESSION.rejected_ids.add(user.id)
            await asyncio.sleep(smart_sleep(2))

        except (UserNotMutualContactError, UserKickedError,
                UserBannedInChannelError, InputUserDeactivatedError):
            user.result = "banned"
            p["banned"] += 1
            SESSION.rejected_ids.add(user.id)
            await asyncio.sleep(smart_sleep(2))

        except PeerFloodError:
            user.result = "flood"
            p["flood_pauses"] += 1
            await event.respond("· heavy rate limit — pausing 5 min to protect account")
            await asyncio.sleep(300)
            sleep_base = min(sleep_base + 5.0, 30.0)

        except ChatAdminRequiredError:
            SESSION.op_running   = False
            SESSION.op_cancelled = True
            await event.respond(f"· not an admin in {dest}, cannot proceed")
            break

        except Exception as e:
            err_str = str(e).lower()
            if "already" in err_str or "participant" in err_str:
                user.result = "already"
                p["already"] += 1
            else:
                user.result = "error"
                p["other_errors"] += 1
                consecutive_errors += 1
                logger.warning(f"[growth] error for {user.id}: {e}")
                if consecutive_errors >= 5:
                    await event.respond("· 5 consecutive errors — backing off 30s")
                    await asyncio.sleep(30)
                    consecutive_errors = 0
                else:
                    await asyncio.sleep(smart_sleep(3))

    SESSION.op_running = False
    elapsed = time.time() - SESSION.op_start_time
    cancelled_note = "\n· stopped early" if SESSION.op_cancelled else ""

    await event.respond(
        f"· done\n\n"
        f"· processed   : {p['success']}\n"
        f"· restricted  : {p['privacy']}\n"
        f"· unavailable : {p['banned']}\n"
        f"· already in  : {p['already']}\n"
        f"· pauses      : {p['flood_pauses']}\n"
        f"· other       : {p['other_errors']}\n"
        f"· duration    : {format_duration(elapsed)}"
        f"{cancelled_note}"
    )


@safe_register(pattern=r'\.gstatus$')
async def growth_status(event):
    p = SESSION.op_progress

    if not SESSION.op_running and not p:
        return await event.edit(
            f"· idle\n"
            f"· in session : {len(SESSION.users)}\n"
            f"· rejected   : {len(SESSION.rejected_ids)}"
        )

    elapsed    = time.time() - SESSION.op_start_time if SESSION.op_start_time else 0
    done       = p.get("current_index", 0)
    total      = p.get("total", 0)
    pct        = (done / total * 100) if total else 0
    bar_filled = int(pct / 5)
    bar        = "█" * bar_filled + "░" * (20 - bar_filled)

    await event.edit(
        f"· dest     : {p.get('dest', '—')}\n"
        f"· running  : {format_duration(elapsed)}\n\n"
        f"  [{bar}] {pct:.1f}%\n"
        f"  {done} / {total}\n\n"
        f"· ok          : {p.get('success', 0)}\n"
        f"· restricted  : {p.get('privacy', 0)}\n"
        f"· unavailable : {p.get('banned', 0)}\n"
        f"· already in  : {p.get('already', 0)}\n"
        f"· pauses      : {p.get('flood_pauses', 0)}\n\n"
        f"· eta      : {eta_string(done, total, elapsed)}"
    )


@safe_register(pattern=r'\.gstop$')
async def growth_stop(event):
    if not SESSION.op_running:
        return await event.edit("· nothing is running")

    SESSION.op_cancelled = True
    await event.edit("· stop signal sent — will halt at next checkpoint")


@safe_register(pattern=r'\.gfilter(.*)')
async def growth_filter(event):
    args_raw = event.pattern_match.group(1).strip()

    if not args_raw:
        f = SESSION.filters
        return await event.edit(
            f"· max_last_seen    : {f['max_last_seen']}\n"
            f"  values: online | recently | last_week | last_month | any\n\n"
            f"· require_username : {f['require_username']}\n"
            f"· require_phone    : {f['require_phone']}\n"
            f"· exclude_premium  : {f['exclude_premium']}\n"
            f"· max_count        : {f['max_count']}\n\n"
            f"usage: `.gfilter max_last_seen=recently require_username=true max_count=2000`"
        )

    updated = []
    errors  = []

    for token in args_raw.split():
        if "=" not in token:
            errors.append(f"invalid token: {token}")
            continue
        key, val = token.split("=", 1)
        key, val = key.strip().lower(), val.strip().lower()

        if key == "max_last_seen":
            if val not in ["online", "recently", "last_week", "last_month", "any"]:
                errors.append(f"unknown value '{val}' for max_last_seen")
            else:
                SESSION.filters["max_last_seen"] = val
                updated.append(f"max_last_seen = {val}")

        elif key in ["require_username", "require_phone", "exclude_premium"]:
            SESSION.filters[key] = val in ["true", "1", "yes"]
            updated.append(f"{key} = {SESSION.filters[key]}")

        elif key == "max_count":
            try:
                SESSION.filters["max_count"] = int(val)
                updated.append(f"max_count = {val}")
            except ValueError:
                errors.append("max_count must be a number")
        else:
            errors.append(f"unknown key: {key}")

    lines = []
    if updated: lines.append("updated:\n" + "\n".join(f"  · {u}" for u in updated))
    if errors:  lines.append("errors:\n"  + "\n".join(f"  · {e}" for e in errors))
    await event.edit("\n\n".join(lines))


@safe_register(pattern=r'\.gclear$')
async def growth_clear(event):
    if SESSION.op_running:
        return await event.edit("· cannot clear while running — use `.gstop` first")

    count = len(SESSION.users)
    SESSION.clear_users()
    SESSION.op_progress   = {}
    SESSION.op_start_time = None

    await event.edit(
        f"· session cleared ({count} entries removed)\n"
        f"  filters and rejected cache preserved"
    )


@safe_register(pattern=r'\.gexport$')
async def growth_export(event):
    if not SESSION.users:
        return await event.edit("· nothing to export — collect users first")

    await event.edit(f"· preparing ({len(SESSION.users)} entries)...")
    try:
        with open(EXPORT_PATH, "w", encoding="utf-8") as f:
            f.write(SESSION.to_export())
        await event.client.send_file(
            event.chat_id,
            EXPORT_PATH,
            caption=(
                f"· {len(SESSION.users)} entries\n"
                f"· {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"reply with `.gimport` to restore"
            )
        )
        await event.delete()
    except Exception as e:
        await event.edit(f"· export failed: {e}")


@safe_register(pattern=r'\.gimport$')
async def growth_import(event):
    reply = await event.get_reply_message()
    if not reply or not reply.file:
        return await event.edit("· reply to a `.json` export file with `.gimport`")

    await event.edit("· loading...")
    try:
        data = await reply.download_media(bytes)
        SESSION.from_import(data.decode("utf-8"))
        await event.edit(
            f"· loaded {len(SESSION.users)} entries\n"
            f"  ready — `.addmembers @YourGroup`"
        )
    except Exception as e:
        await event.edit(f"· failed: {e}")


@safe_register(pattern=r'\.ghelp$')
async def growth_help(event):
    await event.edit(
        "growth engine — commands\n\n"
        "collect\n"
        "  .scrape @group           single source\n"
        "  .scrape @g1 @g2 @g3      multi-source, deduped\n\n"
        "move\n"
        "  .addmembers @dest        process collected list\n\n"
        "control\n"
        "  .gstatus                 live progress\n"
        "  .gstop                   cancel gracefully\n\n"
        "filters  (set before collecting)\n"
        "  .gfilter                 view current settings\n"
        "  .gfilter max_last_seen=recently\n"
        "  .gfilter require_username=true max_count=1000\n\n"
        "  max_last_seen values:\n"
        "  online > recently > last_week > last_month > any\n\n"
        "data\n"
        "  .gclear                  clear session\n"
        "  .gexport                 download list as json\n"
        "  .gimport (reply to file) restore list\n"
    )
