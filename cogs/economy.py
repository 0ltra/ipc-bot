import os
from datetime import datetime, timedelta

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None

    async def cog_load(self):
        self.pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))

    async def cog_unload(self):
        if self.pool:
            await self.pool.close()

    async def get_or_create_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT balance FROM users WHERE user_id = $1", user_id
            )
            if row is None:
                await conn.execute(
                    "INSERT INTO users (user_id, balance) VALUES ($1, 0)", user_id
                )
                return 0
            return row["balance"]

    @app_commands.command(name="balance", description="Check your IPC credit balance")
    async def balance(self, interaction: discord.Interaction):
        bal = await self.get_or_create_user(interaction.user.id)
        await interaction.response.send_message(
            f"💳 You have **{bal}** credits in your IPC account."
        )

    @app_commands.command(name="daily", description="Claim your daily IPC stipend")
    async def daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        async with self.pool.acquire() as conn:
            # Make sure the user exists first
            await self.get_or_create_user(user_id)

            row = await conn.fetchrow(
                "SELECT last_daily FROM users WHERE user_id = $1", user_id
            )
            last_daily = row["last_daily"]

            now = datetime.utcnow()

            if last_daily is not None:
                elapsed = now - last_daily
                if elapsed < timedelta(hours=24):
                    remaining = timedelta(hours=24) - elapsed
                    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                    minutes = remainder // 60
                    await interaction.response.send_message(
                        f"⏳ You've already claimed your stipend. "
                        f"Try again in {hours}h {minutes}m.",
                        ephemeral=True,
                    )
                    return

            reward = 100  # flat daily amount for now
            new_balance = await conn.fetchval(
                """
                UPDATE users
                SET balance = balance + $1, last_daily = $2
                WHERE user_id = $3
                RETURNING balance
                """,
                reward,
                now,
                user_id,
            )

            await interaction.response.send_message(
                f"💰 The IPC has deposited **{reward}** credits into your account. "
                f"New balance: **{new_balance}**."
            )


async def setup(bot):
    await bot.add_cog(Economy(bot))
