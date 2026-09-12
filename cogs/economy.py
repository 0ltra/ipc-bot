import os
import random
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

            now = datetime.utcnow()  # noqa: DTZ003

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

    @app_commands.command(name="give", description="Transfer credits to another user")
    @app_commands.describe(
        user="Who to send credits to", amount="How many credits to send"
    )
    async def give(
        self, interaction: discord.Interaction, user: discord.Member, amount: int
    ):
        sender_id = interaction.user.id
        recipient_id = user.id

        if amount <= 0:
            await interaction.response.send_message(
                "⚠️ Amount must be greater than 0.", ephemeral=True
            )
            return

        if recipient_id == sender_id:
            await interaction.response.send_message(
                "⚠️ You can't send credits to yourself.", ephemeral=True
            )
            return

        await self.get_or_create_user(sender_id)
        await self.get_or_create_user(recipient_id)

        async with self.pool.acquire() as conn, conn.transaction():
            sender_balance = await conn.fetchval(
                "SELECT balance FROM users WHERE user_id = $1 FOR UPDATE",
                sender_id,
            )

            if sender_balance < amount:
                await interaction.response.send_message(
                    f"⚠️ Insufficient funds. You have **{sender_balance}** credits.",
                    ephemeral=True,
                )
                return

            await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE user_id = $2",
                amount,
                sender_id,
            )
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                amount,
                recipient_id,
            )

        await interaction.response.send_message(
            f"✅ Sent **{amount}** credits to {user.mention}."
        )

    @app_commands.command(
        name="gamble",
        description="Roll the Gaiathra Dice and risk your credits",
    )
    @app_commands.describe(amount="How many credits to wager")
    async def gamble(self, interaction: discord.Interaction, amount: int):
        user_id = interaction.user.id

        if amount <= 0:
            await interaction.response.send_message(
                "⚠️ Wager must be greater than 0.", ephemeral=True
            )
            return

        balance = await self.get_or_create_user(user_id)

        if balance < amount:
            await interaction.response.send_message(
                f"⚠️ Insufficient funds. You have **{balance}** credits.",
                ephemeral=True,
            )
            return

        roll = random.randint(1, 100)

        if roll <= 45:
            # Loss
            outcome = -amount
            message = (
                f"🎲 The Gaiathra Dice roll **{roll}**. Luck wasn't on your side — "
                f"you lost **{amount}** credits."
            )
        elif roll <= 90:
            # Win 1:1
            outcome = amount
            message = (
                f"🎲 The Gaiathra Dice roll **{roll}**. Fortune favors you — "
                f"you won **{amount}** credits!"
            )
        else:
            # Rare jackpot, 3x payout
            outcome = amount * 3
            message = (
                f"🎲 The Gaiathra Dice roll **{roll}**. JACKPOT — "
                f"Aventurine himself would be proud. You won **{outcome}** credits!"
            )

        async with self.pool.acquire() as conn:
            new_balance = await conn.fetchval(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2 RETURNING balance",
                outcome,
                user_id,
            )

        await interaction.response.send_message(
            f"{message}\nNew balance: **{new_balance}**."
        )


async def setup(bot):
    await bot.add_cog(Economy(bot))
