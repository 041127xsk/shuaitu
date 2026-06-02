# stzb-helper-v2 Performance Materialized Stats Design

Date: 2026-06-02
Status: Approved for implementation planning

## Goal

Optimize stzb-helper-v2 for databases with hundreds of thousands to over one million battle reports.

The main user-facing goals are:

- Team query should return the team list quickly.
- Win-rate query should avoid repeatedly scanning and aggregating the full `battle_report` table.
- Newly captured battle reports should update derived statistics incrementally.
- A team result should be expandable to show related raw battle reports after the initial result is already visible.
- `battle_report` remains the only source of truth.

## Non-Goals

- Do not change battle report field meanings.
- Do not replace or delete raw `battle_report` data.
- Do not require a server process outside the desktop app.
- Do not add scraping frequency changes.
- Do not change game protocol parsing semantics except where write batching or logging directly affects performance.

## Current Problem

The current query path computes effective teams and win-rate statistics from `battle_report` at request time. Recent changes added short-lived in-process caches and indexes, but million-row data still makes repeated CTEs, sorting, grouping, and Go-side merging expensive.

The capture path also invalidates query caches after each inserted battle report. For batch capture, this can cause repeated recalculation pressure.

## Recommended Architecture

Add a derived data layer built from `battle_report`.

### Tables

`player_team_snapshot`

Stores the latest effective team rows used by the team query page.

Suggested fields:

- `id`
- `player_name`
- `role`
- `idu`
- `hero1_id`, `hero2_id`, `hero3_id`
- `hero1_level`, `hero2_level`, `hero3_level`
- `hero1_star`, `hero2_star`, `hero3_star`
- `total_star`
- `hp`
- `all_skill_info`
- `gear`
- `hero_type`
- `last_time`
- `last_battle_id`
- `lineup_key`
- `normalized_skill_key`
- `source_updated_at`

`team_winrate_stats`

Stores win/loss/draw aggregation derived from raw battle reports.

Suggested fields:

- `id`
- `mode`: `player` or `team`
- `player_name`
- `players`
- `role`
- `idu`
- `hero1_id`, `hero2_id`, `hero3_id`
- `hero1_level`, `hero2_level`, `hero3_level`
- `hero1_star`, `hero2_star`, `hero3_star`
- `total_star`
- `all_skill_info`
- `lineup_key`
- `normalized_skill_key`
- `total_battles`
- `win_count`
- `loss_count`
- `draw_count`
- `win_rate`
- `last_time`
- `last_battle_id`

`materialized_state`

Tracks whether derived tables are ready and what raw data they cover.

Suggested fields:

- `name`: `player_team_snapshot` or `team_winrate_stats`
- `version`
- `status`: `ready`, `building`, `stale`, `failed`
- `last_battle_id`
- `battle_report_count`
- `started_at`
- `finished_at`
- `last_error`

## Data Flow

Raw battle reports are still written to `battle_report` first.

After successful insert:

1. Convert the raw battle report into attack-side and defend-side candidate team rows.
2. Update `player_team_snapshot` for affected players and lineups.
3. Update `team_winrate_stats` counters for affected player/team aggregates.
4. Mark derived state as ready through the latest processed battle id.

For large imports or long auto-scroll sessions, support deferred refresh:

1. Insert raw battle reports in batches.
2. Mark derived tables as stale during the batch.
3. Rebuild or catch up derived tables once the batch finishes.

## Team Query Behavior

The team query page should read from `player_team_snapshot` first.

The initial response returns only snapshot data:

- player
- lineup
- levels
- stars
- skills
- role
- latest time
- team id

This keeps the first result fast.

The page then supports expanding a team row or card. On first expansion, it calls a new related-battles API that queries raw `battle_report` for that specific team.

Suggested API:

`GetPlayerTeamRelatedBattles(playerName, role, idu, hero1ID, hero2ID, hero3ID, page, pageSize)`

Returned fields:

- `battle_id`
- `time`
- `role`
- `result_label`
- `opponent_name`
- `opponent_union_name`
- `attack_hp`
- `defend_hp`
- `all_skill_info`

The frontend should cache expanded battle results for the current page session.

## Win-Rate Query Behavior

The win-rate page should read from `team_winrate_stats`.

The win-rate table is a materialized result of raw battle reports, not a separate rule system. Its counters are derived using the same attack/defend result rules already used by current SQL:

- For attack side, `result IN (1,2,3,4,10,18,19)` is win.
- For attack side, `result = 0` is loss.
- For attack side, `result IN (6,7,8,13)` is draw.
- For defend side, attack win values become defend losses.
- For defend side, `result = 0` is defend win.

If the derived table is missing, stale, or failed, the UI should show status. A temporary fallback to the original raw query may remain available, but it should be clearly marked as slower.

## Rebuild Strategy

Add a backend command:

`RebuildMaterializedStats()`

It should:

1. Set both derived states to `building`.
2. Clear or replace derived rows in a transaction-safe way.
3. Scan `battle_report` in deterministic `battle_id` order.
4. Recompute snapshots and win-rate stats.
5. Set state to `ready`.

For very large databases, rebuilding should log progress periodically and avoid blocking the UI thread.

## Incremental Strategy

Add a small update service in Go:

- `ApplyBattleReportToMaterializedStats(report BattleReport)`
- `ApplyBattleReportsToMaterializedStats(reports []BattleReport)`
- `GetMaterializedStatsStatus()`

Single capture can call the single-row path.

Batch capture can call the batch path or mark stale and rebuild after the run.

## Error Handling

- If raw insert succeeds but derived update fails, keep the raw report and mark derived state `stale` or `failed`.
- Queries should never delete raw data.
- Rebuild should be idempotent.
- Derived tables should be versioned so future rule changes can trigger rebuild.

## Frontend Design

Team query:

- Initial search shows snapshot results.
- Each team card or row can expand.
- Expanded related battle reports load on demand.
- Loading/error state is scoped to that expanded team, not the whole page.

Win-rate query:

- Show whether statistics are ready.
- If stats are rebuilding, show progress/status and disable expensive repeated raw fallback by default.
- Keep existing page filters where possible.

## Testing Plan

Backend tests:

- Building snapshot rows keeps latest effective teams.
- Snapshot conflict rules match existing `buildEffectivePlayerTeams` behavior.
- Win-rate counters match current raw SQL result rules.
- Incremental update produces the same result as full rebuild for the same sample reports.
- Derived state marks stale/failed correctly on update errors.

Frontend tests or manual verification:

- Team query shows initial results before related battles are loaded.
- Expanding a team loads related battles once and caches them for the session.
- Win-rate page reads materialized stats and shows stale/building status.

Performance checks:

- Rebuild time for a large local database.
- Team query latency from snapshot table.
- Win-rate query latency from stats table.
- Related battle expansion latency for one team.

## Rollout

1. Add schema and status APIs.
2. Add full rebuild and tests.
3. Switch team query to snapshot table.
4. Add related battle expansion API and frontend UI.
5. Add win-rate materialized stats.
6. Add incremental update during capture.
7. Keep raw query fallback until materialized path is verified.

## Documentation Updates Needed After Implementation

- `PROJECT_MEMORY.md`: record current implementation status.
- `TODO.md`: mark this performance task complete or partially complete.
- `DECISIONS.md`: record the materialized stats decision.
- `RUNBOOK.md`: document rebuild/status commands and expected usage.
