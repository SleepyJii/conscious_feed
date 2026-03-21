---
name: check-repair-candidates
description: Check the ConsciousFeed orchestrator for scrapers that are failing and eligible for repair. Use when the user asks about broken scrapers, pipeline health, or repair status.
---

Check the ConsciousFeed fleet health using MCP tools.

1. Call `check_health` to verify the conductor is responsive.
2. Call `list_scrapers` to get the full fleet picture.
3. Call `list_repair_candidates` to see which scrapers need repair.
4. Call `list_repair_containers` to check for active repairs.

Present a concise summary:
- Which scrapers are healthy, degraded, or failing
- Which have autorepair enabled
- Which are repair candidates (failing + autorepair)
- Whether any repair jobs are currently running
