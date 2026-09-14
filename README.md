A Discord economy bot themed around the Astral Express's favorite gambler, Aventurine, and the Interastral Peace Corporation. Earn credits, gamble them away, and see who's climbing the corporate ladder.

## What it does

This started as a simple `/balance` command and grew into a full economy system:

- **`/balance`** – check your credit balance
- **`/daily`** – claim a daily stipend from the IPC (80-120 credits, 24h cooldown)
- **`/work`** – do a job for the IPC (20-50 credits, 1h cooldown)
- **`/weekly`** – collect your stock dividend (500-800 credits, 7 day cooldown)
- **`/give @user amount`** – send credits to someone else
- **`/blackjack bet`** – play a full hand of blackjack against the dealer, with Hit/Stand buttons
- **`/leaderboard`** – see the top 10 richest investors in the server

## Tech stack

- **Python** + [discord.py](https://discordpy.readthedocs.io/) for the bot itself
- **PostgreSQL** for persistent storage, accessed with `asyncpg`
- **Docker + docker-compose** so the whole thing (bot + database) spins up with one command
- **pytest** for testing core game logic
- Cog-based architecture — each feature set lives in its own file under `cogs/`

## Running it locally

You'll need Python 3.9+ and a Discord bot token ([create one here](https://discord.com/developers/applications)).

```bash
git clone https://github.com/yourusername/ipc-bot.git
cd ipc-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql://localhost/ipcbot


You'll need Postgres running locally with a database and table set up:

```bash
createdb ipcbot
psql ipcbot -c "
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    last_daily TIMESTAMP,
    last_work TIMESTAMP,
    last_weekly TIMESTAMP
);
"
```

Then just run it:

```bash
python3 main.py
```

## Running it with Docker (easier)

If you've got Docker installed, this is the whole setup:

```bash
docker-compose up --build
```

That builds the bot image, pulls Postgres, and wires them together — no local Python or Postgres install needed. Data persists across restarts thanks to a named volume.

## Running tests

```bash
pytest
```

Currently covers the blackjack hand-value logic, including ace handling (aces count as 11 unless that would bust the hand, in which case they drop to 1 — the trickiest part of blackjack scoring to get right).

## Notes

- Slash commands sync per-guild during development for instant updates; swap to a global sync before deploying anywhere permanent.
- The `/blackjack` payout for a natural blackjack (21 on the deal) is 1.5x the bet, same as standard casino rules.
