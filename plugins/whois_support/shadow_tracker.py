import os
import asyncio
import random
import math
from collections import Counter as counter, defaultdict as default_dict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional as optional
from telethon.tl.functions.messages import GetCommonChatsRequest as get_common_chats
from telethon.errors import (
    rpcerrorlist as rpc_error_list,
    FloodWaitError as flood_wait_error,
    ChatAdminRequiredError as chat_admin_error,
    ChannelPrivateError as channel_private_error,
    UserNotParticipantError as user_not_participant_error
)
from core.utils import log_error


@dataclass
class shadow_profile:
    target_id:           int
    mutual_chats:        list  = field(default_factory=list)
    total_messages:      int   = 0
    replies_to_me:       int   = 0
    messages_per_chat:   dict  = field(default_factory=dict)
    active_hours:        list  = field(default_factory=list)
    active_days:         list  = field(default_factory=list)
    words_pool:          list  = field(default_factory=list)
    recent_messages:     list  = field(default_factory=list)
    media_count:         dict  = field(default_factory=dict)
    emoji_pool:          list  = field(default_factory=list)
    language_hints:      list  = field(default_factory=list)
    msg_lengths:         list  = field(default_factory=list)
    forward_count:       int   = 0
    reply_timestamps:    list  = field(default_factory=list)
    msg_timestamps:      list  = field(default_factory=list)
    is_starter_count:    int   = 0
    is_responder_count:  int   = 0
    caps_count:          int   = 0
    question_count:      int   = 0
    exclamation_count:   int   = 0
    punctuation_sparse:  int   = 0
    sentiment_pos:       int   = 0
    sentiment_neg:       int   = 0
    sentiment_neu:       int   = 0
    thread_depths:       list  = field(default_factory=list)
    reply_lengths:       list  = field(default_factory=list)
    trigger_lengths:     list  = field(default_factory=list)
    words_per_sentence:  list  = field(default_factory=list)
    first_seen:          optional[datetime] = None
    last_seen:           optional[datetime] = None


stop_words = {
    "the","is","in","and","to","a","of","for","it","on","that","this",
    "with","you","i","my","was","are","be","at","an","or","if","me",
    "we","so","do","but","not","have","had","has","he","she","they",
    "ነው","እና","ላይ","ግን","ስለ","ወይም","አለ","ምን","ነኝ","ነበር",
    "ይሆናል","ሆኖ","ስለዚህ","ስለሆነ","ስለሆነም","እኔ","አንተ","ናቸው",
}

emoji_ranges = [
    (0x1f600, 0x1f64f),(0x1f300, 0x1f5ff),
    (0x1f680, 0x1f6ff),(0x2600,  0x26ff),
    (0x1f900, 0x1f9ff),(0x1fa00, 0x1fa9f),
]

pos_words = {
    "good","great","love","nice","thanks","amazing","happy","yes","sure",
    "perfect","awesome","cool","excellent","best","wonderful","beautiful",
    "ጥሩ","ድንቅ","አመሰግናለሁ","ያመሰግናሉ","እወዳለሁ",
}

neg_words = {
    "bad","hate","no","never","worst","ugly","wrong","stupid","terrible",
    "awful","horrible","disgusting","boring","useless","idiot","fake",
    "መጥፎ","ጥሩ አይደለም","አልወድም","አልፈልግም",
}


def _jitter(base: float, spread: float = 0.4) -> float:
    return base + random.uniform(-spread, spread) * base


async def _safe_sleep(base: float, spread: float = 0.5):
    await asyncio.sleep(max(0.01, _jitter(base, spread)))


async def _flood_safe(coro, retries: int = 5, base_wait: float = 6.0):
    for attempt in range(retries):
        try:
            return await coro
        except flood_wait_error as e:
            await asyncio.sleep(e.seconds + _jitter(5.0))
        except (chat_admin_error, channel_private_error, user_not_participant_error):
            return None
        except rpc_error_list.UserIsBotError:
            return None
        except Exception:
            if attempt == retries - 1:
                return None
            await _safe_sleep(base_wait * (attempt + 1))
    return None


def _extract_words(text: str) -> list:
    if not text:
        return []
    result = []
    for w in text.lower().split():
        c = w.strip(".,!?\"'(){}[]:;*~`@#—–…")
        if len(c) > 2 and c not in stop_words:
            result.append(c)
    return result


def _extract_emojis(text: str) -> list:
    return [
        ch for ch in (text or "")
        if any(lo <= ord(ch) <= hi for lo, hi in emoji_ranges)
    ]


def _detect_language(text: str) -> str:
    if not text:
        return "unknown"
    total = len([c for c in text if c.strip()])
    if total == 0:
        return "unknown"
    am = sum(1 for c in text if 0x1200 <= ord(c) <= 0x139f)
    ar = sum(1 for c in text if 0x0600 <= ord(c) <= 0x077f)
    if am / total > 0.20:
        return "amharic"
    if ar / total > 0.20:
        return "arabic"
    return "english"


def _score_sentiment(text: str) -> str:
    if not text:
        return "neutral"
    low = text.lower()
    words = set(low.split())
    pos = len(words & pos_words)
    neg = len(words & neg_words)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _words_per_sentence(text: str) -> float:
    if not text:
        return 0.0
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def _infer_timezone(peak_hours: list) -> str:
    if not peak_hours:
        return "unknown"
    counts = counter(peak_hours)
    peak = counts.most_common(1)[0][0]
    assumed = 14
    offset = assumed - peak
    offset = max(-12, min(14, offset))
    sign = "+" if offset >= 0 else "-"
    return f"utc{sign}{abs(offset)}"


def _detect_sleep_window(hour_counts: counter) -> str:
    if not hour_counts:
        return "unknown"
    inactive = [h for h in range(24) if hour_counts.get(h, 0) == 0]
    if len(inactive) < 3:
        return "no clear sleep window"
    runs, run = [], []
    for h in range(48):
        if h % 24 in inactive:
            run.append(h % 24)
        else:
            if len(run) >= 3:
                runs.append(run[:])
            run = []
    if not runs:
        return "no clear sleep window"
    longest = max(runs, key=len)
    return f"{longest[0]:02d}:00 - {longest[-1]:02d}:59 utc"


def _reply_speed_profile(gaps: list) -> str:
    if not gaps:
        return "unknown"
    avg = sum(gaps) / len(gaps)
    if avg < 60:
        return f"instant (~{int(avg)}s)"
    if avg < 300:
        return f"fast (~{int(avg//60)}m)"
    if avg < 1800:
        return f"moderate (~{int(avg//60)}m)"
    return f"slow (~{int(avg//3600)}h)"


def _bar(value: int, total: int, width: int = 10) -> str:
    if total == 0:
        return "░" * width
    filled = round((value / total) * width)
    return "█" * filled + "░" * (width - filled)


def _section(title: str) -> list:
    return ["", f"--- {title} ---"]


def _format_report(p: shadow_profile, username: str, name: str) -> str:
    now = str(datetime.now(timezone.utc))[:16] + " utc"
    lines = []

    lines += [
        "--- profile dump ---",
        f"date : {now}",
        f"name : {name}",
        f"user : {username}",
        f"id   : {p.target_id}",
    ]

    if p.first_seen:
        lines.append(f"first seen : {str(p.first_seen)[:10]}")
    if p.last_seen:
        lines.append(f"last seen  : {str(p.last_seen)[:16]} utc")
    if p.first_seen and p.last_seen:
        span = (p.last_seen - p.first_seen).days
        lines.append(f"active span: {span} days")

    lines += _section("shared groups")
    if p.mutual_chats:
        for i, chat in enumerate(p.mutual_chats, 1):
            lines.append(f"{i:>2}. {chat}")
    else:
        lines.append("none found.")

    lines += _section("stats")
    lines += [
        f"total msgs   : {p.total_messages}",
        f"replies to me: {p.replies_to_me}",
        f"forwards     : {p.forward_count}",
    ]

    if p.is_starter_count + p.is_responder_count > 0:
        total_conv = p.is_starter_count + p.is_responder_count
        start_pct = int(p.is_starter_count  / total_conv * 100)
        resp_pct = int(p.is_responder_count / total_conv * 100)
        lines += [
            f"starts chat  : {start_pct}%",
            f"replies      : {resp_pct}%",
        ]

    if p.msg_lengths:
        avg_len = sum(p.msg_lengths) / len(p.msg_lengths)
        med_len = sorted(p.msg_lengths)[len(p.msg_lengths) // 2]
        lines += [
            f"avg msg len  : {avg_len:.0f} chars",
            f"median len   : {med_len} chars",
        ]

    if p.words_per_sentence:
        avg_wps = sum(p.words_per_sentence) / len(p.words_per_sentence)
        lines.append(f"words/sent   : {avg_wps:.1f}")

    lines += _section("writing habits")
    total_txt = max(p.total_messages, 1)
    lines += [
        f"caps msgs    : {p.caps_count} ({int(p.caps_count/total_txt*100)}%)",
        f"questions    : {p.question_count}",
        f"exclamations : {p.exclamation_count}",
        f"lazy punct   : {p.punctuation_sparse} msgs",
    ]

    if p.reply_lengths and p.trigger_lengths:
        avg_reply = sum(p.reply_lengths) / len(p.reply_lengths)
        avg_trigger = sum(p.trigger_lengths) / len(p.trigger_lengths)
        ratio = avg_reply / max(avg_trigger, 1)
        style = "expander" if ratio > 1.2 else ("compressor" if ratio < 0.8 else "mirror")
        lines.append(f"reply ratio  : {ratio:.2f} ({style})")

    if p.thread_depths:
        avg_depth = sum(p.thread_depths) / len(p.thread_depths)
        lines.append(f"avg depth    : {avg_depth:.1f} replies deep")

    lines += _section("vibe check")
    sent_total = max(p.sentiment_pos + p.sentiment_neg + p.sentiment_neu, 1)
    for label, count in [("positive", p.sentiment_pos), ("negative", p.sentiment_neg), ("neutral", p.sentiment_neu)]:
        pct = int(count / sent_total * 100)
        lines.append(f"{label:<10} {_bar(pct, 100, 10)} {pct}%")

    lines += _section("routines")
    if p.reply_timestamps:
        gaps = sorted(p.reply_timestamps)
        profile = _reply_speed_profile(gaps)
        lines.append(f"reply speed : {profile}")

    if p.active_hours:
        tz_est = _infer_timezone(p.active_hours)
        lines.append(f"timezone    : {tz_est}")

    hour_counts = counter(p.active_hours)
    sleep_win = _detect_sleep_window(hour_counts)
    lines.append(f"sleep window: {sleep_win}")

    wknd = sum(1 for d in p.active_days if d >= 5)
    wkday = sum(1 for d in p.active_days if d < 5)
    if wknd + wkday > 0:
        wknd_pct = int(wknd / (wknd + wkday) * 100)
        pattern = "weekend-heavy" if wknd_pct > 55 else ("weekday-heavy" if wknd_pct < 35 else "balanced")
        lines.append(f"week pattern: {pattern} ({wknd_pct}% weekend)")

    lines += _section("hourly activity (utc)")
    if p.active_hours:
        max_h = max(hour_counts.values()) if hour_counts else 1
        for hour in range(24):
            count = hour_counts.get(hour, 0)
            bar = _bar(count, max_h, 10)
            h12 = hour % 12 or 12
            per = "am" if hour < 12 else "pm"
            lines.append(f"{h12:>2}:00 {per} {bar} {count}")
        peak3 = hour_counts.most_common(3)
        lines.append("")
        lines.append("peaks: " + " | ".join(f"{h%12 or 12}:00 {'am' if h<12 else 'pm'}" for h, _ in peak3))

    lines += _section("weekly pattern")
    if p.active_days:
        day_counts = counter(p.active_days)
        max_d = max(day_counts.values()) if day_counts else 1
        days_lbl = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        for d in range(7):
            count = day_counts.get(d, 0)
            bar = _bar(count, max_d, 10)
            lines.append(f"{days_lbl[d]} {bar} {count}")

    lines += _section("language")
    if p.language_hints:
        lang_c = counter(p.language_hints)
        top_lang = lang_c.most_common(1)[0][0]
        for lang, count in lang_c.most_common():
            pct = int(count / len(p.language_hints) * 100)
            lines.append(f"{lang:<12} {_bar(pct, 100, 10)} {pct}%")
        lines.append(f"primary: {top_lang}")

    if p.messages_per_chat:
        lines += _section("chat activity")
        sorted_chats = sorted(p.messages_per_chat.items(), key=lambda x: x[1], reverse=True)
        total_m = sum(v for _, v in sorted_chats)
        for title, count in sorted_chats:
            bar = _bar(count, total_m, 10)
            pct = int(count / total_m * 100)
            lines.append(f"{title[:18]:<18} {bar} {count} ({pct}%)")

    if p.media_count:
        lines += _section("media types")
        for mtype, count in sorted(p.media_count.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"{mtype:<16} {count}")

    if p.emoji_pool:
        emoji_c = counter(p.emoji_pool)
        lines += _section("top emojis")
        row = ""
        for emoji, count in emoji_c.most_common(10):
            row += f"{emoji}x{count} "
        lines.append(row)

    if p.words_pool:
        filtered = [w for w in p.words_pool if w not in stop_words]
        word_c = counter(filtered)
        top_words = word_c.most_common(20)
        lines += _section("top words")
        max_wc = top_words[0][1] if top_words else 1
        for word, count in top_words:
            bar = _bar(count, max_wc, 8)
            lines.append(f"{word:<16} {bar} x{count}")

    if p.recent_messages:
        lines += _section(f"latest texts ({min(len(p.recent_messages), 40)})")
        for msg in p.recent_messages[:40]:
            clean = msg.replace("\n", " | ")
            lines.append(f"- {clean}")

    lines += ["", "--- eof ---", ""]
    return "\n".join(lines)


async def _fetch_mutual_chats(client, user_id: int) -> list:
    result = await _flood_safe(
        client(get_common_chats(user_id=user_id, max_id=0, limit=100))
    )
    return result.chats if result else []


async def compile_shadow_data(client, user, current_chat_id: int) -> str:
    p = shadow_profile(target_id=user.id)
    me = await client.get_me()
    my_id = me.id

    mutual_objects = await _fetch_mutual_chats(client, user.id)
    p.mutual_chats = [getattr(c, "title", "unknown") for c in mutual_objects]

    chats_to_scan = {current_chat_id: "current chat"}
    for c in mutual_objects:
        chats_to_scan[c.id] = getattr(c, "title", "unknown")

    batch_size = 350
    msg_sleep = 0.055
    chat_sleep = 3.2
    batch_sleep = 9.0
    batch_every = 3
    scanned_chats = 0
    prev_msg_time: optional[datetime] = None

    for chat_id, chat_title in chats_to_scan.items():
        msg_count = 0
        consecutive = 0

        try:
            async for msg in client.iter_messages(
                chat_id, from_user=user.id, limit=batch_size
            ):
                try:
                    p.total_messages += 1
                    msg_count += 1
                    consecutive += 1

                    if msg.date:
                        dt = msg.date.astimezone(timezone.utc)
                        p.active_hours.append(dt.hour)
                        p.active_days.append(dt.weekday())
                        p.msg_timestamps.append(dt)

                        if prev_msg_time:
                            gap = abs((dt - prev_msg_time).total_seconds())
                            if gap < 3600:
                                p.reply_timestamps.append(gap)
                        prev_msg_time = dt

                        if p.first_seen is None or dt < p.first_seen:
                            p.first_seen = dt
                        if p.last_seen is None or dt > p.last_seen:
                            p.last_seen = dt

                    if msg.text:
                        text = msg.text
                        p.msg_lengths.append(len(text))
                        p.recent_messages.append(f"[{chat_title}] {text}")
                        p.words_pool.extend(_extract_words(text))
                        p.emoji_pool.extend(_extract_emojis(text))
                        p.language_hints.append(_detect_language(text))
                        p.words_per_sentence.append(_words_per_sentence(text))

                        if text == text.upper() and len(text) > 3:
                            p.caps_count += 1
                        if "?" in text:
                            p.question_count += 1
                        if "!" in text:
                            p.exclamation_count += 1
                        if not any(c in text for c in ".!?,;:"):
                            p.punctuation_sparse += 1

                        sent = _score_sentiment(text)
                        if sent == "positive":
                            p.sentiment_pos += 1
                        elif sent == "negative":
                            p.sentiment_neg += 1
                        else:
                            p.sentiment_neu += 1

                    if msg.forward:
                        p.forward_count += 1

                    if msg.media:
                        mtype = type(msg.media).__name__.lower().replace("messagemedia", "")
                        p.media_count[mtype] = p.media_count.get(mtype, 0) + 1

                    if msg.reply_to_msg_id:
                        p.is_responder_count += 1
                        try:
                            reply_msg = await _flood_safe(msg.get_reply_message())
                            if reply_msg:
                                if getattr(reply_msg, "sender_id", None) == my_id:
                                    p.replies_to_me += 1
                                if reply_msg.text and msg.text:
                                    p.reply_lengths.append(len(msg.text))
                                    p.trigger_lengths.append(len(reply_msg.text))
                                depth = 0
                                cur = reply_msg
                                while getattr(cur, "reply_to_msg_id", None) and depth < 10:
                                    depth += 1
                                    cur = await _flood_safe(cur.get_reply_message()) or cur
                                    if not hasattr(cur, "reply_to_msg_id"):
                                        break
                                p.thread_depths.append(depth)
                        except Exception:
                            pass
                    else:
                        p.is_starter_count += 1

                    if consecutive % 50 == 0:
                        await _safe_sleep(msg_sleep * 10, 0.5)
                    else:
                        await asyncio.sleep(msg_sleep + random.uniform(0.0, 0.025))

                except flood_wait_error as e:
                    await asyncio.sleep(e.seconds + _jitter(5.0))
                except Exception:
                    continue

        except flood_wait_error as e:
            await asyncio.sleep(e.seconds + _jitter(7.0))
        except (chat_admin_error, channel_private_error, user_not_participant_error):
            pass
        except Exception:
            pass

        if msg_count > 0:
            p.messages_per_chat[chat_title] = msg_count

        scanned_chats += 1

        if scanned_chats % batch_every == 0:
            await _safe_sleep(batch_sleep, 0.4)
        else:
            await _safe_sleep(chat_sleep, 0.5)

    uname = f"@{user.username}" if getattr(user, "username", None) else "no username"
    fname = (getattr(user, "first_name", None) or "").strip()
    lname = (getattr(user, "last_name",  None) or "").strip()
    name = f"{fname} {lname}".strip() or "unknown"

    content = _format_report(p, uname, name)
    file_name = f"profile_{user.id}.txt"

    with open(file_name, "w", encoding="utf-8") as f:
        f.write(content)

    return file_name