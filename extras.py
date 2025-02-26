import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import json
import asyncio
import logging
from datetime import datetime
import random
from main import conn, cursor, ZENTRONS_START, DAILY_BASE, NANOPULSE_LIMIT, ZENTRON_EMOJI, CHALLENGES, CONTRACTS, send_with_retry, get_balance, set_balance, get_daily_info, set_daily_info, get_challenges, set_challenges, check_and_refresh_challenges, get_contracts, set_contracts, get_nanopulse_count, set_nanopulse_count, get_last_nanopulse_reset, set_last_nanopulse_reset, get_enterprise, get_inventory, add_to_inventory, get_title

logger = logging.getLogger('Zentrix')

class Extras(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="daily", description="Claim your daily Zentrons")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        now = datetime.utcnow().date().isoformat()
        last_daily, streak = get_daily_info(user_id)
        
        if last_daily == now:
            embed = discord.Embed(title="Already Claimed", description="You’ve got today’s loot! Come back tomorrow.", color=0xFF3333)
            await send_with_retry(interaction, embed=embed, ephemeral=True)
            return
        
        last_date = datetime.fromisoformat(last_daily).date() if last_daily else None
        if last_date and (datetime.utcnow().date() - last_date).days > 1:
            streak = 0
        
        new_streak = streak + 1
        reward = min(DAILY_BASE * new_streak, 500)
        set_balance(user_id, get_balance(user_id) + reward)
        set_daily_info(user_id, now, new_streak)
        embed = discord.Embed(title="Daily Haul", description=f"Claimed **{reward} {ZENTRON_EMOJI}**!\nStreak: {new_streak} day{'s' if new_streak > 1 else ''}", color=0x00FFAA)
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="challenges", description="View your daily challenges")
    async def challenges(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        now = datetime.utcnow().date().isoformat()
        challenges = check_and_refresh_challenges(user_id, now)
        if not challenges:
            embed = discord.Embed(title="No Challenges", description="Something’s off—try again later!", color=0xFF3333)
        else:
            challenge_text = "\n".join(f"**{c['task']}**: {c['progress']}/{c['goal']} (Reward: {c['reward']} {ZENTRON_EMOJI})" for c in challenges)
            embed = discord.Embed(title="Daily Challenges", description=challenge_text, color=0x00FFAA)
            embed.set_footer(text="Complete them before midnight UTC!")
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="contracts", description="View and claim tech contracts")
    async def contracts(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        now = int(datetime.utcnow().timestamp())
        enterprise = get_enterprise(user_id)
        if not enterprise:
            embed = discord.Embed(title="No Empire", description="Start an enterprise to unlock contracts!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        contracts = check_and_refresh_contracts(user_id, datetime.utcnow().date().isoformat())
        if not contracts:
            embed = discord.Embed(title="No Contracts", description="Something’s off—try again later!", color=0xFF3333)
        else:
            contract_text = "\n".join(f"**{c['task']}**: {c['progress']}/{c['goal']} (Reward: {c['reward']} {ZENTRON_EMOJI} & {c['item']}) - {max(0, (c['start_time'] + 21600 - now) // 3600)}h left" for c in contracts)
            embed = discord.Embed(title=f"{enterprise['industry']} Tech Contracts", description=contract_text, color=0x00FFAA)
            embed.set_footer(text="Complete within 6 hours from reset!")
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="top", description="Check the Zentron kings")
    async def top(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        cursor.execute('SELECT user_id, balance, bank FROM users ORDER BY (balance + bank) DESC LIMIT 5')
        top_players = cursor.fetchall()
        leaderboard = [f"{i+1}. {interaction.guild.get_member(int(user_id)).name if interaction.guild.get_member(int(user_id)) else 'Unknown User'} - {balance + bank} {ZENTRON_EMOJI} ({get_title(balance + bank)})" for i, (user_id, balance, bank) in enumerate(top_players)]
        embed = discord.Embed(title="👑 Zentron Kings", description="\n".join(leaderboard) if leaderboard else "No kings yet!", color=0x00FFAA)
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="claim-bonus", description="Snag some extra Zentrons")
    async def claim_bonus(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        tax_pool = get_tax_pool()
        enterprise = get_enterprise(user_id)
        
        if not enterprise:
            embed = discord.Embed(title="No Empire", description="Need an enterprise to claim bonuses!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        bonus = min(tax_pool // 10, 50)
        if bonus <= 0:
            embed = discord.Embed(title="No Loot", description="Tax pool’s dry. Check later!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        set_balance(user_id, get_balance(user_id) + bonus)
        set_tax_pool(tax_pool - bonus)
        embed = discord.Embed(title="Bonus Snagged", description=f"Grabbed {bonus} {ZENTRON_EMOJI} from the pool!", color=0x00FFAA)
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="nanopulse", description="Send a NanoPulse to a mate")
    @app_commands.describe(target="Recipient")
    async def nanopulse(self, interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(thinking=True)
        sender_id = str(interaction.user.id)
        receiver_id = str(target.id)
        now = datetime.utcnow().date().isoformat()
        last_reset = get_last_nanopulse_reset(sender_id)
        
        if sender_id == receiver_id:
            response = "Self-Pulse? You can’t NanoPulse yourself, yaar!"
            await send_with_retry(interaction, response, ephemeral=True)
            return
        
        if last_reset != now:
            set_nanopulse_count(sender_id, 0)
            set_last_nanopulse_reset(sender_id, now)
        
        count = get_nanopulse_count(sender_id)
        if count >= NANOPULSE_LIMIT:
            response = "Pulse Limit! You’ve sent 3 NanoPulses today! Reset at midnight UTC."
            await send_with_retry(interaction, response, ephemeral=True)
            return
        
        set_nanopulse_count(sender_id, count + 1)
        set_balance(receiver_id, get_balance(receiver_id) + 10)
        response = f"NanoPulse Sent! You pulsed {target.name} with a NanoPulse! They got 10 {ZENTRON_EMOJI}. ({NANOPULSE_LIMIT - count - 1} left today)"
        
        challenges = check_and_refresh_challenges(sender_id, now)
        for challenge in challenges:
            if challenge["progress_key"] == "nanopulse_count":
                challenge["progress"] = min(challenge["progress"] + 1, challenge["goal"])
                logger.info(f"Updated nanopulse_count for {sender_id}: {challenge['progress']}/{challenge['goal']}")
                if challenge["progress"] >= challenge["goal"]:
                    set_balance(sender_id, get_balance(sender_id) + challenge["reward"])
                    response += f"\nChallenge Complete: Finished '{challenge['task']}'! +{challenge['reward']} {ZENTRON_EMOJI}"
                    challenges.remove(challenge)
        set_challenges(sender_id, challenges)
        
        contracts = check_and_refresh_contracts(sender_id, now)
        now_ts = int(datetime.utcnow().timestamp())
        for contract in contracts:
            if contract["progress_key"] == "nanopulse_count":
                contract["progress"] = min(contract["progress"] + 1, contract["goal"])
                if contract["progress"] >= contract["goal"] and now_ts < contract["start_time"] + 21600:
                    set_balance(sender_id, get_balance(sender_id) + contract["reward"])
                    add_to_inventory(sender_id, contract["item"])
                    response += f"\nContract Complete: Finished '{contract['task']}'! +{contract['reward']} {ZENTRON_EMOJI} & {contract['item']}"
                    contracts.remove(contract)
        set_contracts(sender_id, contracts)
        
        await send_with_retry(interaction, response)

    @app_commands.command(name="setup-updates", description="Set up the zentrix-updates channel (Admin only)")
    async def setup_updates(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user = interaction.user
        if not any(role.permissions.administrator for role in user.roles):
            embed = discord.Embed(title="No Permission", description="Only admins can set up the updates channel!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed, ephemeral=True)
            return
        
        guild = interaction.guild
        channel = discord.utils.get(guild.text_channels, name="zentrix-updates")
        if not channel:
            channel = await guild.create_text_channel("zentrix-updates")
        set_updates_channel(str(guild.id), str(channel.id))
        embed = discord.Embed(title="Updates Channel Set", description=f"Set {channel.name} as the updates channel!", color=0x00FFAA)
        await send_with_retry(interaction, embed=embed, ephemeral=True)

    @app_commands.command(name="help", description="Get the Zentrix rundown")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        embed = discord.Embed(title="Zentrix Rundown", description="Dominate with **Zentrons**—grind, risk, and rule!", color=0x00FFAA)
        embed.add_field(name="💰 Cash Flow", value="`/funds` - Check your stash\n`/bank action amount` - Deposit/withdraw\n`/inventory` - View your loot\n`/transfer @user amount` - Send Zentrons\n`/rob @user` - Steal wallet cash\n`/work` - Grind cash\n`/crime` - Risk big", inline=False)
        embed.add_field(name="🏢 Empire", value="`/industries` - Check options\n`/start-enterprise name industry` - Start it\n`/enterprise` - Check stats\n`/invest` - Grow with risk\n`/overclock` - Boost with risk\n`/use item` - Boost with loot", inline=False)
        embed.add_field(name="🎁 Extras", value="`/daily` - Daily loot\n`/challenges` - Daily tasks\n`/contracts` - Tech quests\n`/nanopulse @user` - Send a pulse\n`/claim-bonus` - Snag extras\n`/top` - See the kings", inline=False)
        embed.set_footer(text="Zentrix © 2025 | Grind to greatness")
        await send_with_retry(interaction, embed=embed)

async def setup(bot):
    await bot.add_cog(Extras(bot))

async def teardown(bot):
    await bot.remove_cog('Extras')