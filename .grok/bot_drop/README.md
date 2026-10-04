# Bot drop — TUI cannot poll Grok Tasks

Cloud Task results are invisible to this TUI (`Team ID … != None`).
The user is the bridge. **Prompt + filenames only.** No result paste in chat.

```
.grok/bot_drop/<team_id>/outbox/<filename>
```

Team id (this workspace): `b9e45917-7abd-481e-92d3-781841c9e368`

| Role | Does |
|---|---|
| This TUI Grok | Writes the prompt text + exact relative paths. Then **reads** `outbox/`. |
| User | Pastes that prompt to the parquet Grok Bot. Does not transcribe results. |
| Parquet Grok Bot | Creates the folder if missing. Writes **only** the named files. Named queries only. |

## Rules

- Bot writes. TUI reads. Do not edit each other’s files.
- One job per drop. Filename is the job id.
- JSON if the job is a named query copy; otherwise UTF-8 markdown.
- First line of every file: `team_id=` + the id above.
- No fifth atlas. No join 94k ↛ TRADE_OPENED. RESEARCH_ONLY. No G001.
- Do not overwrite `results/research/parquet_evidence_layer/**` from the bot unless the prompt names that path.

## Handshake

Bot writes `outbox/PING.md`. TUI replies in session when that file is readable.
