import os

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


async def setup(bot):
    await bot.add_cog(Economy(bot))
