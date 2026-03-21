---
name: conscious-feed
description: Master health check and repair loop for the ConsciousFeed scraping pipeline. Verifies infrastructure health, identifies broken scrapers, and repairs them one by one.
disable-model-invocation: true
allowed-tools: Skill
---

You are the operator for a self-healing scraping pipeline called ConsciousFeed. Your job is to check infrastructure health, find broken scrapers, and fix them. All interaction goes through the `conscious-feed-tools` MCP server.

## Phase 1: Infrastructure health check

Call `check_health` to verify the conductor is responsive. If it fails, **STOP immediately** and tell the user:
> "Infrastructure issue: conductor is unreachable. Please investigate before I proceed."

Call `list_scrapers` to get the fleet overview. Check that the response is valid.

Call `list_repair_containers` to check for stuck repairs. If any repair container has been running for more than 1 hour, **STOP and report** to the user.

Do NOT attempt to fix infrastructure issues yourself.

## Phase 2: Scraper health assessment

Only proceed here if Phase 1 passed cleanly.

Using the scraper list from Phase 1, summarise:
- Total scrapers
- How many are healthy / degraded / failing / pending
- How many have autorepair enabled

Call `list_repair_candidates` to get the candidates.

If there are no candidates and no failing scrapers, report:
> "All clear — fleet is healthy. N scrapers running, all passing."

And you're done.

## Phase 3: Repair loop

Only proceed here if Phase 2 found repair candidates or failing scrapers.

For each failing scraper, invoke the repair skill:
```
/repair-scraper <scraper-id>
```

Work through them **one at a time, sequentially**. After each repair:
- Confirm the test run succeeded
- Move to the next scraper

If a repair fails or you can't figure out the fix, **skip it** and move to the next. Report skipped scrapers at the end.

## Phase 4: Summary

After all repairs (or if there was nothing to repair), give a final summary:
- Infrastructure status
- Scrapers repaired successfully
- Scrapers skipped (with reason)
- Current fleet health

Call `find_events` with `event_type: "repair_completed"` and `limit: 20` to check recent repair outcomes.
