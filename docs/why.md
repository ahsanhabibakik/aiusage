# "Can't you just use Claude Code's statusline?"

Yes — and if a terminal statusline is all you want, **you should**. Claude Code's built-in `/statusline` wizard can show session/weekly usage right in your terminal, with zero extra software. Anyone who tells you that is correct.

This page is the honest version of why aiusage exists anyway: who it's for, who it's *not* for, and what specific problem each feature was built to solve.

## Who does NOT need this tool

- You only ever check usage **while actively typing in a Claude Code session**, and a number in that terminal is enough.
- You don't care about spend estimates, trends, or being warned *before* hitting a limit.
- You don't use Codex or any other AI CLI alongside Claude.

For that profile, Claude Code's native statusline is simpler, has no extra process, and we'd rather you use it than install something you don't need. (`aiusage setup` deliberately refuses to overwrite an existing statusline for exactly this reason.)

## Who it IS for

One sentence: **people who want to know their usage state when they're *not* staring at a Claude Code terminal** — or who run more than one AI coding tool.

The native statusline has one structural limitation that no configuration can fix: it only exists inside a running Claude Code session. Close the terminal, switch to your browser, work in your editor — the information is gone precisely when you're most likely to burn through usage without noticing (long agentic runs, background tasks, multiple parallel sessions).

## What each feature solves

### System tray icons — *usage visible with zero terminals open*

**Problem:** you kick off a long agentic run, switch to the browser, and come back to "weekly limit reached." The statusline knew. You weren't looking at it.
**How:** two small badges per provider (session ○ / weekly □) live in the OS tray with the percentage drawn on the icon itself. Glanceable from any app, any time. Color shifts blue → amber → red as the state worsens.

### Desktop notifications — *warnings that find you, instead of you checking*

**Problem:** every display so far — native statusline included — is *pull*: you must look at it. Nobody looks at the right moment.
**How:** OS notifications fire when a window drops under 10% left, when it's fully spent, and — most usefully — when you're **on pace to run out before the reset**. Once per metric per window, so no nagging. This works with every Claude Code session closed.

### Burn-rate pacing — *"will I run out?" instead of "how much have I used?"*

**Problem:** "55% used" is ambiguous. Halfway through the window it's fine; two hours into a 7-day window it's an emergency. Raw percentages make you do that math in your head, every time.
**How:** every window is projected to its reset at your current rate and gets a verdict — on-course / tight / on pace to run out. The tray icon, statusline flame (⚠), dashboard bar color, and notifications all key off the *projection*, not the raw level. A half-full window burning too fast shows red **early**, while there's still time to slow down.

### Spend estimates + 30-day trend + per-model breakdown — *what is this actually costing?*

**Problem:** subscription users never see a dollar figure, so there's no intuition for what a heavy day "costs," which model is eating the budget, or whether this week is unusual.
**How:** your own local session logs (Claude Code's and Codex's) are scanned on your machine — nothing uploaded — and priced at API list rates: today / yesterday / last 30 days, a daily trend chart, and a ranked per-model cost table. That's how you discover things like "yesterday was a $125-equivalent day and 60% of it was one model."

### Multi-provider (Claude + Codex, auto-detected) — *one place instead of one statusline per tool*

**Problem:** Claude Code's statusline will only ever show Claude. If you also run Codex, its limits live in a different tool with different conventions.
**How:** if `~/.codex` exists, Codex's weekly limit, plan, reset credits, and local spend appear automatically alongside Claude's — same bars, same pacing, same notifications. No configuration; detection is purely local files.

### Local JSON API — *your usage data, scriptable*

**Problem:** data trapped inside one tool's UI can't feed your own scripts, widgets, or dashboards.
**How:** `GET http://127.0.0.1:8737/v1/usage` returns everything as normalized JSON (loopback-only; serves numbers, never credentials). The Claude Code statusline integration is itself just a consumer of this API — anything you build gets the same access.

### Web dashboard — *the detail view a one-line display can't hold*

**Problem:** trend charts, model breakdowns, pacing ticks, and multiple providers don't fit in one terminal line.
**How:** `http://127.0.0.1:8737` renders it all, with click-to-flip used/left and countdown/exact-time preferences.

## Why a background server at all?

This is the part the question is really about. The answer: **shared cache**.

The tray icons, notifications, dashboard, statusline, and API all need the same numbers. If each polled Anthropic/OpenAI independently — or on every statusline render, which happens constantly — you'd hammer endpoints that visibly throttle (we hit 429s during development doing exactly this). One tiny loopback process polls each provider **once per 5 minutes** (the same interval the reference macOS app, OpenUsage, settled on) and every surface reads from that cache. The statusline render path never touches the network at all — it can't slow your terminal down or contribute to rate limits, no matter how often it redraws.

Failed refreshes never blank your data either: the last known values stay up, marked with their age — the same way your battery icon doesn't vanish when the estimate is briefly stale.

## Design choices that came from real mistakes

These aren't hypothetical — each one was added after something actually went wrong during development:

- **No silent auto-update.** A tool that rewrites itself in the background is a supply-chain risk. Updates are one explicit command (`aiusage update`), plus a one-line notice when a newer version exists.
- **Never overwrite someone else's statusline.** `aiusage setup` detects a different existing statusline and refuses unless you pass `--force` — with a backup either way.
- **Don't trust exit codes that lie.** `pip` reports success upgrading a package that isn't on the index; our updater checks the index itself.
- **Stale-but-shown beats blank.** Rate-limited or offline, every surface keeps the last good reading with an age note instead of going empty.

## Summary

| You want… | Use |
|---|---|
| A number in the terminal while Claude Code is open | **Native `/statusline`** — simpler, use it |
| Usage visible outside the terminal (tray, any app) | aiusage |
| Warned *before* running out, even with terminals closed | aiusage |
| Dollar/token spend, trends, per-model costs | aiusage |
| Claude + Codex in one place | aiusage |
| Usage data your own scripts can read | aiusage |

Both can coexist: keep the native statusline in your terminal and run aiusage just for the tray, notifications, and dashboard.
