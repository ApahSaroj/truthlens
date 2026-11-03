# Hosting TruthLens as a public web app

The included `Dockerfile` runs the same web app people get on their own PC, for anyone with a browser. It works on
any container host: a Hugging Face Space (Docker SDK, port 7860), Render, Railway, Fly.io, or your own server.

```bash
docker build -t truthlens .
docker run -p 7860:7860 -v truthlens-data:/data truthlens        # then open http://localhost:7860
docker build --build-arg SYNC_AT_BUILD=1 -t truthlens .           # optional: refresh official data while building
```

Note: the Dockerfile was written and reviewed but **not built or run in our tests** (no Docker in the sandbox). The
same server was run directly with uvicorn and tested over HTTP; see "What was measured" below.

## One process, one worker

The container runs `uvicorn truthlens.api:app --workers 1`. Keep it at one worker: running checks, their results and
the uploaded documents behind the Deep check button live in that process's memory only, never on disk, so a second
worker would not find the first one's checks (the page would show "no such check"). To serve more people, run more
containers behind a load balancer with sticky sessions.

Consequences: a restart loses running checks and finished results (people just run the check again). Results are kept
for `TRUTHLENS_JOB_TTL` seconds (30 minutes in the Dockerfile).

## Environment variables

Set in the Dockerfile (change them with your host's settings):

| Variable | Dockerfile value | What it does |
|---|---|---|
| `PORT` | 7860 | port uvicorn listens on |
| `TRUTHLENS_PUBLIC` | 1 | public mode (limits below) |
| `TRUTHLENS_TRUST_PROXY` | 1 | take the caller's address from the first `X-Forwarded-For` hop. Set it only behind a proxy that sets that header (Hugging Face, Render, Fly); otherwise callers could fake their address and dodge the rate limits |
| `TRUTHLENS_SYNC_ON_START` | 1 | at startup, refresh the official data in the background if it is missing or more than 7 days old; Quick checks use the bundled data meanwhile |
| `TRUTHLENS_DATA_DIR` | /data | synced official data and the shared live-answer cache |
| `TRUTHLENS_CACHE` | /data/cache | per-source request cache |
| `TRUTHLENS_RATE_CHECKS` | 20 | checks (Quick or Deep) per hour per address |
| `TRUTHLENS_RATE_DEEP` | 5 | Deep checks per hour per address |
| `TRUTHLENS_MAX_JOBS` | 4 | checks running at the same time; more are refused until one finishes |
| `TRUTHLENS_JOB_TTL` | 1800 | seconds a finished result is kept in memory |
| `TRUTHLENS_LIVE_CACHE_MB` | 300 | size cap of the shared live-answer cache (oldest answers dropped first) |

Other useful ones (defaults in brackets): `TRUTHLENS_LIVE_CACHE_DAYS` [7] how long a live answer is reused;
`TRUTHLENS_LIVE_CACHE=0` turns that cache off; `TRUTHLENS_LIVE_BUDGET` [60] seconds of live-source time per document;
`TRUTHLENS_CONNECT_TIMEOUT` [5] and `TRUTHLENS_READ_TIMEOUT` [10] per request; `TRUTHLENS_WORKERS` [12] claims checked at
once; `TRUTHLENS_PER_HOST` [3] requests at once per server; `TRUTHLENS_FALLBACK_CLAIMS` [20] how many of the most
important claims may use the slow fallback sources; `TRUTHLENS_CONTACT_EMAIL` sent to Crossref and OpenAlex;
`TRUTHLENS_ALLOW_CORRECTIONS=1` accepts "This verdict is wrong" reports in public mode; `TRUTHLENS_OFFLINE=1` never
contacts any server. Do not set AI or search keys on a public server unless you accept paying for every visitor's
checks; visitors can bring their own key for one check (it is never stored).

## What public mode does

- Per-address limits: 20 checks and 5 Deep checks per hour by default; over the limit the server answers 429 with
  "Limit reached ... Try again in about N min".
- At most 4 checks run at once (`TRUTHLENS_MAX_JOBS`).
- Uploads (15 MB max) are read in memory and never written to disk; results stay in memory for 30 minutes.
- Only the address that ran a Quick check can start its Deep check.
- "This verdict is wrong" reports are not stored unless `TRUTHLENS_ALLOW_CORRECTIONS=1`.
- `/health` reports the version, the mode, how fresh the data is, the live cache size and the limits.

Limits we know of:

- `POST /sync` ("Update now") is not rate-limited: any visitor can start an update, though only one runs at a time.
- Limits are per address, so many people behind one office or mobile network share them.
- Rate-limit counters are in memory; a restart resets them.
- A Deep check sends requests from your server to government and research servers. Some of them answered HTTP 429
  (OpenAlex, Semantic Scholar) or timed out (the Lok Sabha archive on Hugging Face) even from a single user in our tests;
  heavier public use will see more of that. Claims affected say "Couldn't check", never wrong.

## Memory and disk (measured, not in a container)

Measured on 3 Nov 2026 in a Linux sandbox via a US proxy, one uvicorn worker started by `start_truthlens.sh` from a
fresh extract, checking the 51-claim test draft (details: [`data/perf_v052.md`](data/perf_v052.md)):

| | |
|---|---|
| RAM, just started | 36.8 MB |
| RAM, after a Quick check | 66-68 MB |
| RAM, peak during a Deep check | 149.7 MB (and it stays near there afterwards) |
| Disk, code and bundled data | about 19 MB |
| Disk, Python packages (virtual environment) | 110 MB |
| Disk, live-answer cache after one Deep check | 4.8 MB (capped at 300 MB in the Dockerfile) |

Not measured: several checks at once (allowed up to 4; plan for more RAM, roughly 512 MB as a cautious starting
point is our estimate, not a measurement), a container image's size, a `truthlens sync` run's peak memory.

## Persistent storage

Mount persistent storage at `/data` if the host offers it (Hugging Face Spaces: enable persistent storage, which is
mounted at `/data`). Without it the synced data and the live-answer cache start empty after every restart: Quick
checks still work from the bundled data, and the startup sync refreshes the rest in the background.
