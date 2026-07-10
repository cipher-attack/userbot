# ⚠ anti-ban warning

project akasha is a heavy-duty userbot. telegram's anti-spam algorithms are highly aggressive against automated user accounts. if you run modules like `.shadow` or `.addmembers` recklessly, your account will be permanently banned. 

read and strictly follow these rules to keep your session alive.

### 1. the burner rule (account age)
- **never** use a fresh account (less than 6 months old) or a voip (virtual) number for this bot.
- **never** use your personal/main account for the `growth` engine (`.scrape` / `.addmembers`). 
- aged accounts with normal human chat history have a much higher trust score and can survive scraping.

### 2. the speed limit (do not alter code)
- the core uses `asyncio.sleep` and `_jitter` to simulate human latency.
- do not lower these delays to make the bot "faster". telegram detects static api calls. the random micro-delays are what keeps you hidden.

### 3. osint or shadow tracker (`.shadow`)
- scraping thousands of messages across multiple groups triggers telegram's data limits.
- do not run `.shadow` on multiple targets at the exact same time. let one dump finish before starting another.
- if telegram throws a `floodwait`, the bot will pause. do not restart the bot to bypass this pause.

### 4. growth engine (`.addmembers`)
- adding users to groups is the #1 reason userbots get banned.
- telegram limits how many users an account can invite per day (usually ~40-50).
- accept that accounts running the growth module *will* eventually get restricted (spam-blocked). always use disposable accounts for this module.

### 5. autopilot (`.auto`)
- running `.auto ai` 24/7 makes you look like a bot. 
- use context modes and simulate typing delays to blend in. turn it off when you are actually sleeping to match your normal timezone activity.

### 6. api keys
- always use your own `api_id` and `api_hash` from my.telegram.org.
- never use public or leaked api keys, as telegram bans all accounts attached to flagged keys.

---
**disclaimer:** you are solely responsible for your account. the developers of project akasha hold no liability if your telegram account is muted, restricted, or permanently deleted. use responsibly.