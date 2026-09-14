import os
import random

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


def new_deck():
    deck = [f"{rank}{suit}" for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    return deck


def hand_value(hand):
    value = 0
    aces = 0
    for card in hand:
        rank = card[:-1]
        if rank in ("J", "Q", "K"):
            value += 10
        elif rank == "A":
            aces += 1
            value += 11
        else:
            value += int(rank)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value


def format_hand(hand):
    return " ".join(hand)


class BlackjackView(discord.ui.View):
    def __init__(self, cog, user_id, bet, deck, player_hand, dealer_hand):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your game.", ephemeral=True
            )
            return False
        return True

    def build_embed(self, reveal_dealer=False):
        player_val = hand_value(self.player_hand)
        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.dark_gold())
        embed.add_field(
            name="Your Hand",
            value=f"{format_hand(self.player_hand)} (**{player_val}**)",
            inline=False,
        )
        if reveal_dealer:
            dealer_val = hand_value(self.dealer_hand)
            embed.add_field(
                name="Dealer Hand",
                value=f"{format_hand(self.dealer_hand)} (**{dealer_val}**)",
                inline=False,
            )
        else:
            embed.add_field(
                name="Dealer Hand",
                value=f"{self.dealer_hand[0]} ❓",
                inline=False,
            )
        return embed

    async def end_game(self, interaction, result_text, payout):
        self.finished = True
        for child in self.children:
            child.disabled = True

        async with self.cog.pool.acquire() as conn:
            new_balance = await conn.fetchval(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2 RETURNING balance",
                payout,
                self.user_id,
            )

        embed = self.build_embed(reveal_dealer=True)
        embed.add_field(
            name="Result",
            value=f"{result_text}\nNew balance: **{new_balance}**",
            inline=False,
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_hand.append(self.deck.pop())
        player_val = hand_value(self.player_hand)

        if player_val > 21:
            await self.end_game(
                interaction, f"💥 Bust! You lost **{self.bet}** credits.", -self.bet
            )
            return

        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        while hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

        player_val = hand_value(self.player_hand)
        dealer_val = hand_value(self.dealer_hand)

        if dealer_val > 21 or player_val > dealer_val:
            await self.end_game(
                interaction, f"🎉 You win! +**{self.bet}** credits.", self.bet
            )
        elif player_val == dealer_val:
            await self.end_game(interaction, "🤝 Push — bet returned.", 0)
        else:
            await self.end_game(
                interaction, f"😔 Dealer wins. -**{self.bet}** credits.", -self.bet
            )


class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None

    async def cog_load(self):
        self.pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))

    async def cog_unload(self):
        if self.pool:
            await self.pool.close()

    async def get_balance(self, user_id: int):
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

    @app_commands.command(name="blackjack", description="Play a game of blackjack")
    @app_commands.describe(bet="How many credits to wager")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        if bet <= 0:
            await interaction.response.send_message(
                "⚠️ Bet must be greater than 0.", ephemeral=True
            )
            return

        balance = await self.get_balance(interaction.user.id)
        if balance < bet:
            await interaction.response.send_message(
                f"⚠️ Insufficient funds. You have **{balance}** credits.", ephemeral=True
            )
            return

        deck = new_deck()
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        view = BlackjackView(
            self, interaction.user.id, bet, deck, player_hand, dealer_hand
        )
        embed = view.build_embed()

        if hand_value(player_hand) == 21:
            async with self.pool.acquire() as conn:
                new_balance = await conn.fetchval(
                    "UPDATE users SET balance = balance + $1 WHERE user_id = $2 RETURNING balance",
                    int(bet * 1.5),
                    interaction.user.id,
                )
            embed = view.build_embed(reveal_dealer=True)
            embed.add_field(
                name="Result",
                value=f"🂡 Blackjack! +**{int(bet * 1.5)}** credits.\nNew balance: **{new_balance}**",
                inline=False,
            )
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Blackjack(bot))
