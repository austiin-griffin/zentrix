import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import json
import asyncio
import logging
from datetime import datetime
import random
from main import conn, cursor, ZENTRONS_START, ENTERPRISE_COST, EVENT_CYCLE, TAX_RATE, WORK_COOLDOWN, CRIME_COOLDOWN, BUFF_COOLDOWN, ROB_COOLDOWN, ZENTRON_EMOJI, TIERS, INDUSTRIES, BUFFS, send_with_retry, get_balance, set_balance, get_bank, set_bank, get_last_work, set_last_work, get_last_crime, set_last_crime, get_daily_info, set_daily_info, get_inventory, set_inventory, add_to_inventory, remove_from_inventory, get_buffs, set_buffs, get_last_buff, set_last_buff, apply_buff, is_anti_rob_active, get_challenges, set_challenges, check_and_refresh_challenges, get_contracts, set_contracts, check_and_refresh_contracts, get_nanopulse_count, set_nanopulse_count, get_last_nanopulse_reset, set_last_nanopulse_reset, get_last_rob, set_last_rob, get_title, get_enterprise, set_enterprise, get_tax_pool, set_tax_pool, get_updates_channel, set_updates_channel, get_surge_multiplier

logger = logging.getLogger('Zentrix')

class Venture(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="funds", description="Check your Zentrons stash")
    async def funds(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        balance = get_balance(user_id)
        bank = get_bank(user_id)
        title = get_title(balance + bank)
        embed = discord.Embed(title=f"💰 Your Stash - {title}", description=f"**Wallet**: {balance} {ZENTRON_EMOJI}\n**Bank**: {bank} {ZENTRON_EMOJI}", color=0x00FFAA)
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="bank", description="Manage your Zentron bank")
    @app_commands.describe(action="deposit or withdraw", amount="Zentrons to move")
    async def bank(self, interaction: discord.Interaction, action: str, amount: int):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        balance = get_balance(user_id)
        bank = get_bank(user_id)
        
        if action.lower() not in ["deposit", "withdraw"]:
            embed = discord.Embed(title="Invalid Action", description="Use 'deposit' or 'withdraw'!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed, ephemeral=True)
            return
        
        if amount <= 0:
            embed = discord.Embed(title="Invalid Amount", description="Amount must be positive!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed, ephemeral=True)
            return
        
        if action.lower() == "deposit":
            if balance < amount:
                embed = discord.Embed(title="Not Enough", description=f"You only have {balance} {ZENTRON_EMOJI} in your wallet!", color=0xFF3333)
            else:
                set_balance(user_id, balance - amount)
                set_bank(user_id, bank + amount)
                embed = discord.Embed(title="Deposit Successful", description=f"Stored {amount} {ZENTRON_EMOJI} in your bank!", color=0x00FFAA)
        else:  # withdraw
            if bank < amount:
                embed = discord.Embed(title="Not Enough", description=f"You only have {bank} {ZENTRON_EMOJI} in your bank!", color=0xFF3333)
            else:
                set_balance(user_id, balance + amount)
                set_bank(user_id, bank - amount)
                embed = discord.Embed(title="Withdrawal Successful", description=f"Pulled {amount} {ZENTRON_EMOJI} from your bank!", color=0x00FFAA)
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="rob", description="Steal Zentrons from someone’s wallet")
    @app_commands.describe(target="User to rob")
    async def rob(self, interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(thinking=True)
        robber_id = str(interaction.user.id)
        target_id = str(target.id)
        now = int(datetime.utcnow().timestamp())
        last_rob = get_last_rob(robber_id)
        
        if robber_id == target_id:
            response = "Self-Rob? You can’t rob yourself, yaar!"
            await send_with_retry(interaction, response, ephemeral=True)
            return
        
        if now - last_rob < ROB_COOLDOWN:
            remaining = ROB_COOLDOWN - (now - last_rob)
            response = f"Cooldown! Wait {remaining // 60}m {remaining % 60}s before robbing again!"
            await send_with_retry(interaction, response)
            return
        
        target_balance = get_balance(target_id)
        if is_anti_rob_active(target_id):
            response = f"Rob Blocked! {target.name} has a Secure Vault active—no loot for you!"
            await send_with_retry(interaction, response)
            return
        
        if target_balance < 100:
            response = f"Too Poor! {target.name} doesn’t have enough to rob (min 100 {ZENTRON_EMOJI})!"
            await send_with_retry(interaction, response)
            return
        
        success = random.random() < 0.5
        rob_amount = int(target_balance * random.uniform(0.05, 0.2))
        
        if success:
            set_balance(target_id, target_balance - rob_amount)
            set_balance(robber_id, get_balance(robber_id) + rob_amount)
            response = f"Heist Success! You stole {rob_amount} {ZENTRON_EMOJI} from {target.name}!"
        else:
            fine = int(get_balance(robber_id) * 0.25)
            set_balance(robber_id, max(0, get_balance(robber_id) - fine))
            response = f"Caught! You got nabbed and paid a {fine} {ZENTRON_EMOJI} fine!"
        
        set_last_rob(robber_id, now)
        await send_with_retry(interaction, response)

    @app_commands.command(name="inventory", description="Check your rare loot")
    async def inventory(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        inventory = get_inventory(user_id)
        if not inventory:
            embed = discord.Embed(title="🎒 Inventory", description="Your stash is empty! Grind with /work or /crime.", color=0xFF3333)
        else:
            items = "\n".join(f"**{item}**: {count}" for item, count in inventory.items())
            embed = discord.Embed(title="🎒 Inventory", description=items, color=0x00FFAA)
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="use", description="Activate a buff from your inventory")
    @app_commands.describe(item="Item to use (NanoChip, Tech Relic, Crypto Key, Dark Cache, Secure Vault)")
    async def use(self, interaction: discord.Interaction, item: str):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        now = int(datetime.utcnow().timestamp())
        last_buff = get_last_buff(user_id)
        
        if item not in BUFFS:
            embed = discord.Embed(title="Invalid Item", description="Use: NanoChip, Tech Relic, Crypto Key, Dark Cache, or Secure Vault!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed, ephemeral=True)
            return
        
        if now - last_buff < BUFF_COOLDOWN:
            remaining = BUFF_COOLDOWN - (now - last_buff)
            embed = discord.Embed(title="Cooldown", description=f"Wait {remaining // 60}m {remaining % 60}s to use another buff!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed, ephemeral=True)
            return
        
        if not remove_from_inventory(user_id, item):
            embed = discord.Embed(title="No Item", description=f"You don’t have a {item} in your inventory!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        buffs = get_buffs(user_id)
        buffs[item] = now + BUFFS[item]["duration"]
        set_buffs(user_id, buffs)
        set_last_buff(user_id, now)
        buff_type = BUFFS[item]["type"]
        duration = BUFFS[item]["duration"] // 3600
        if item == "Secure Vault":
            embed = discord.Embed(title="Buff Activated", description=f"Used **Secure Vault**! Rob protection active for {duration} hour{'s' if duration > 1 else ''}.", color=0x00FFAA)
        else:
            embed = discord.Embed(title="Buff Activated", description=f"Used **{item}**! +{int((BUFFS[item]['multiplier'] - 1) * 100)}% {buff_type} income for {duration} hour{'s' if duration > 1 else ''}.", color=0x00FFAA)
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="industries", description="View industry options for your empire")
    async def industries(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        embed = discord.Embed(title="Industry Options", description="Choose your empire’s path with /start-enterprise!", color=0x00FFAA)
        for industry, data in INDUSTRIES.items():
            embed.add_field(
                name=f"{industry}",
                value=f"**Focus**: {data['focus']}\n"
                      f"**Perks**: Profit: {data['profit_mult']}x, Work: {data['work_mult']}x, Crime: {data['crime_mult']}x\n"
                      f"**Vibe**: {data['vibe']}",
                inline=True
            )
        embed.set_footer(text="Pick wisely—your industry shapes your grind!")
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="start-enterprise", description="Launch your empire")
    @app_commands.describe(name="Enterprise name", industry="Industry (Cybernetics, Quantum Computing, Nanotech, Dark Matter, AI Dynasties)")
    async def start_enterprise(self, interaction: discord.Interaction, name: str, industry: str):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        balance = get_balance(user_id)
        
        if industry not in INDUSTRIES:
            embed = discord.Embed(title="Invalid Industry", description="Choose: Cybernetics, Quantum Computing, Nanotech, Dark Matter, AI Dynasties! Use /industries to check details.", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        if balance < ENTERPRISE_COST:
            embed = discord.Embed(title="Broke Vibes", description=f"Need {ENTERPRISE_COST} {ZENTRON_EMOJI}, you’ve got {balance}. Grind with /work!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        if get_enterprise(user_id):
            embed = discord.Embed(title="Already Bossin'", description="You’ve got an enterprise running!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        enterprise_data = {
            "name": name,
            "industry": industry,
            "tier": 0,
            "profit": int(TIERS[0]["profit"] * INDUSTRIES[industry]["profit_mult"]),
            "work_bonus": int(TIERS[0]["work_bonus"] * INDUSTRIES[industry]["work_mult"]),
            "crime_bonus": int(TIERS[0]["crime_bonus"] * INDUSTRIES[industry]["crime_mult"]),
            "profit_earned": 0,
            "overclock_active": False,
            "overclock_end": 0,
            "crash_end": 0,
            "created": datetime.utcnow().isoformat()
        }
        set_balance(user_id, balance - ENTERPRISE_COST)
        set_enterprise(user_id, enterprise_data)
        embed = discord.Embed(title="Empire Born", description=f"**{name}** ({industry} - {TIERS[0]['name']}) is live! Cost: {ENTERPRISE_COST} {ZENTRON_EMOJI}.", color=0x00FFAA)
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="enterprise", description="Scope your empire’s stats")
    async def enterprise(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        enterprise = get_enterprise(user_id)
        if not enterprise:
            embed = discord.Embed(title="No Empire", description="Start one with /start-enterprise!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed, ephemeral=True)
            return
        tier_info = TIERS[enterprise["tier"]]
        next_tier = TIERS[enterprise["tier"] + 1] if enterprise["tier"] < len(TIERS) - 1 else None
        now = int(datetime.utcnow().timestamp())
        profit = enterprise["profit"]
        if enterprise["overclock_active"] and now < enterprise["overclock_end"]:
            profit *= 3
            status = f"Overclocked (ends in {(enterprise['overclock_end'] - now) // 60}m)"
        elif now < enterprise["crash_end"]:
            profit //= 2
            status = f"Crashed (recovers in {(enterprise['crash_end'] - now) // 60}m)"
        else:
            status = "Normal"
        embed = discord.Embed(title=f"🏢 {enterprise['name']} ({enterprise['industry']})", color=0x00FFAA)
        embed.add_field(name="Tier", value=tier_info["name"], inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Passive", value=f"{profit} {ZENTRON_EMOJI}/hr", inline=True)
        embed.add_field(name="Work Bonus", value=f"+{enterprise['work_bonus']} {ZENTRON_EMOJI}", inline=True)
        embed.add_field(name="Crime Bonus", value=f"+{enterprise['crime_bonus']} {ZENTRON_EMOJI}", inline=True)
        embed.add_field(name="Profit Earned", value=f"{enterprise['profit_earned']} {ZENTRON_EMOJI}", inline=False)
        embed.set_footer(text=f"Next tier: {next_tier['name']} ({next_tier['invest_cost']} {ZENTRON_EMOJI}, {int(next_tier['success_rate'] * 100)}% chance, Need {next_tier['profit_needed']} earned)" if next_tier else "Dynasty achieved!")
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="invest", description="Risk Zentrons to grow your empire")
    async def invest(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        enterprise = get_enterprise(user_id)
        balance = get_balance(user_id)
        
        if not enterprise:
            embed = discord.Embed(title="No Empire", description="Start one with /start-enterprise!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        if enterprise["tier"] >= len(TIERS) - 1:
            embed = discord.Embed(title="Dynasty Achieved", description="Your empire’s at the top!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        next_tier = enterprise["tier"] + 1
        invest_cost = TIERS[next_tier]["invest_cost"]
        profit_needed = TIERS[next_tier]["profit_needed"]
        
        if balance < invest_cost:
            embed = discord.Embed(title="Short on Cash", description=f"Need {invest_cost} {ZENTRON_EMOJI}, you’ve got {balance}. Grind more!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed, ephemeral=True)
            return
        
        if enterprise["profit_earned"] < profit_needed:
            embed = discord.Embed(title="Not Ready", description=f"Need {profit_needed} {ZENTRON_EMOJI} earned from profit (you’ve got {enterprise['profit_earned']}). Keep grinding!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        set_balance(user_id, balance - invest_cost)
        success = random.random() < TIERS[next_tier]["success_rate"]
        jackpot = success and random.random() < 0.03
        
        if success:
            enterprise["tier"] = min(next_tier + (1 if jackpot else 0), len(TIERS) - 1)
            enterprise["profit"] = int(TIERS[enterprise["tier"]]["profit"] * INDUSTRIES[enterprise["industry"]]["profit_mult"])
            enterprise["work_bonus"] = int(TIERS[enterprise["tier"]]["work_bonus"] * INDUSTRIES[enterprise["industry"]]["work_mult"])
            enterprise["crime_bonus"] = int(TIERS[enterprise["tier"]]["crime_bonus"] * INDUSTRIES[enterprise["industry"]]["crime_mult"])
            set_enterprise(user_id, enterprise)
            if random.random() < 0.05:
                drop = random.choice(["NanoChip", "Tech Relic", "Crypto Key", "Dark Cache"])
                add_to_inventory(user_id, drop)
                embed = discord.Embed(title="Investment Paid Off!", description=f"**{enterprise['name']}** is now a {TIERS[enterprise['tier']]['name']}!" + 
                                      (f" JACKPOT! Skipped a tier!" if jackpot else "") + f"\nBonus: Found a **{drop}**!", color=0x00FFAA)
            else:
                embed = discord.Embed(title="Investment Paid Off!", description=f"**{enterprise['name']}** is now a {TIERS[enterprise['tier']]['name']}!" + 
                                      (f" JACKPOT! Skipped a tier!" if jackpot else ""), color=0x00FFAA)
        else:
            embed = discord.Embed(title="Investment Flopped", description=f"Lost {invest_cost} {ZENTRON_EMOJI}. Better luck next time!", color=0xFF3333)
        
        challenges = check_and_refresh_challenges(user_id, datetime.utcnow().date().isoformat())
        for challenge in challenges:
            if challenge["progress_key"] == "invest_count" and success:
                challenge["progress"] = min(challenge["progress"] + 1, challenge["goal"])
                logger.info(f"Updated invest_count for {user_id}: {challenge['progress']}/{challenge['goal']}")
                if challenge["progress"] >= challenge["goal"]:
                    set_balance(user_id, get_balance(user_id) + challenge["reward"])
                    embed.add_field(name="Challenge Complete", value=f"Finished '{challenge['task']}'! +{challenge['reward']} {ZENTRON_EMOJI}", inline=False)
                    challenges.remove(challenge)
        set_challenges(user_id, challenges)
        
        contracts = check_and_refresh_contracts(user_id, datetime.utcnow().date().isoformat())
        now = int(datetime.utcnow().timestamp())
        for contract in contracts:
            if contract["progress_key"] == "tier_level" and success:
                contract["progress"] = enterprise["tier"]
                if contract["progress"] >= contract["goal"] and now < contract["start_time"] + 21600:
                    set_balance(user_id, get_balance(user_id) + contract["reward"])
                    add_to_inventory(user_id, contract["item"])
                    embed.add_field(name="Contract Complete", value=f"Finished '{contract['task']}'! +{contract['reward']} {ZENTRON_EMOJI} & {contract['item']}", inline=False)
                    contracts.remove(contract)
        set_contracts(user_id, contracts)
        
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="overclock", description="Boost your empire at a risk")
    async def overclock(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        enterprise = get_enterprise(user_id)
        balance = get_balance(user_id)
        now = int(datetime.utcnow().timestamp())
        
        if not enterprise:
            embed = discord.Embed(title="No Empire", description="Start one with /start-enterprise!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed, ephemeral=True)
            return
        
        if enterprise["overclock_active"] and now < enterprise["overclock_end"]:
            remaining = (enterprise["overclock_end"] - now) // 60
            embed = discord.Embed(title="Already Overclocked", description=f"Your empire’s boosted for {remaining}m!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed, ephemeral=True)
            return
        
        if now < enterprise["crash_end"]:
            remaining = (enterprise["crash_end"] - now) // 60
            embed = discord.Embed(title="Crashed", description=f"Your empire’s recovering for {remaining}m!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        cost = int(balance * 0.1)
        if cost < 100:
            embed = discord.Embed(title="Too Low", description=f"Need at least 1000 {ZENTRON_EMOJI} to overclock (10% of wallet)!", color=0xFF3333)
            await send_with_retry(interaction, embed=embed)
            return
        
        set_balance(user_id, balance - cost)
        enterprise["overclock_active"] = True
        enterprise["overclock_end"] = now + 3600  # 1 hour
        if random.random() < 0.2:  # 20% crash chance
            enterprise["overclock_active"] = False
            enterprise["crash_end"] = now + 7200  # 2 hours
            set_enterprise(user_id, enterprise)
            embed = discord.Embed(title="Overclock Crashed", description=f"Paid {cost} {ZENTRON_EMOJI}, but your empire crashed! Half profit for 2 hours.", color=0xFF3333)
        else:
            set_enterprise(user_id, enterprise)
            embed = discord.Embed(title="Overclock Engaged", description=f"Paid {cost} {ZENTRON_EMOJI}—triple profit for 1 hour!", color=0x00FFAA)
        
        await send_with_retry(interaction, embed=embed)

    @app_commands.command(name="work", description="Grind some Zentrons")
    async def work(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        last_work = get_last_work(user_id)
        now = int(datetime.utcnow().timestamp())
        
        if now - last_work < WORK_COOLDOWN:
            remaining = WORK_COOLDOWN - (now - last_work)
            response = f"**Chill Out! Wait {remaining // 60}m {remaining % 60}s before grinding again!**"
            await send_with_retry(interaction, response)
            return
        
        surge_mult = await get_surge_multiplier(str(interaction.guild.id))
        enterprise = get_enterprise(user_id)
        base_earn = random.randint(10, 30)
        bonus = enterprise["work_bonus"] if enterprise else 0
        total = int((base_earn + bonus) * apply_buff(user_id, "work") * surge_mult)
        rare_drop = ""
        
        if random.random() < 0.05:
            drop = random.choice([("NanoChip", random.randint(50, 150)), ("Tech Relic", random.randint(200, 500))])
            total += drop[1]
            rare_drop = f"\n**Rare Drop! Found a {drop[0]}! +{drop[1]} {ZENTRON_EMOJI}**"
            add_to_inventory(user_id, drop[0])
        
        set_balance(user_id, get_balance(user_id) + total)
        set_last_work(user_id, now)
        bonus_text = f" (+{bonus} from {enterprise['name']})" if enterprise else ""
        response = f"**Work Paid Off! Earned {total} {ZENTRON_EMOJI}!{bonus_text}{rare_drop}{' [Surge x{surge_mult}]' if surge_mult > 1 else ''}**"
        
        challenges = check_and_refresh_challenges(user_id, datetime.utcnow().date().isoformat())
        for challenge in challenges:
            if challenge["progress_key"] == "work_count":
                challenge["progress"] = min(challenge["progress"] + 1, challenge["goal"])
                logger.info(f"Updated work_count for {user_id}: {challenge['progress']}/{challenge['goal']}")
                if challenge["progress"] >= challenge["goal"]:
                    set_balance(user_id, get_balance(user_id) + challenge["reward"])
                    response += f"\nChallenge Complete: Finished '{challenge['task']}'! +{challenge['reward']} {ZENTRON_EMOJI}"
                    challenges.remove(challenge)
            elif challenge["progress_key"] == "earned":
                challenge["progress"] = min(challenge["progress"] + total, challenge["goal"])
                logger.info(f"Updated earned for {user_id}: {challenge['progress']}/{challenge['goal']}")
                if challenge["progress"] >= challenge["goal"]:
                    set_balance(user_id, get_balance(user_id) + challenge["reward"])
                    response += f"\nChallenge Complete: Finished '{challenge['task']}'! +{challenge['reward']} {ZENTRON_EMOJI}"
                    challenges.remove(challenge)
        set_challenges(user_id, challenges)
        
        contracts = check_and_refresh_contracts(user_id, datetime.utcnow().date().isoformat())
        for contract in contracts:
            if contract["progress_key"] == "work_count":
                contract["progress"] = min(contract["progress"] + 1, contract["goal"])
                if contract["progress"] >= contract["goal"] and now < contract["start_time"] + 21600:
                    set_balance(user_id, get_balance(user_id) + contract["reward"])
                    add_to_inventory(user_id, contract["item"])
                    response += f"\nContract Complete: Finished '{contract['task']}'! +{contract['reward']} {ZENTRON_EMOJI} & {contract['item']}"
                    contracts.remove(contract)
            elif contract["progress_key"] == "work_earned":
                contract["progress"] = min(contract["progress"] + total, contract["goal"])
                if contract["progress"] >= contract["goal"] and now < contract["start_time"] + 21600:
                    set_balance(user_id, get_balance(user_id) + contract["reward"])
                    add_to_inventory(user_id, contract["item"])
                    response += f"\nContract Complete: Finished '{contract['task']}'! +{contract['reward']} {ZENTRON_EMOJI} & {contract['item']}"
                    contracts.remove(contract)
            elif contract["progress_key"] == "earned":
                contract["progress"] = min(contract["progress"] + total, contract["goal"])
                if contract["progress"] >= contract["goal"] and now < contract["start_time"] + 21600:
                    set_balance(user_id, get_balance(user_id) + contract["reward"])
                    add_to_inventory(user_id, contract["item"])
                    response += f"\nContract Complete: Finished '{contract['task']}'! +{contract['reward']} {ZENTRON_EMOJI} & {contract['item']}"
                    contracts.remove(contract)
        set_contracts(user_id, contracts)
        
        await send_with_retry(interaction, response)

    @app_commands.command(name="transfer", description="Send Zentrons to a mate")
    @app_commands.describe(target="Recipient", amount="Zentrons to send")
    async def transfer(self, interaction: discord.Interaction, target: discord.User, amount: int):
        await interaction.response.defer(thinking=True)
        sender_id = str(interaction.user.id)
        receiver_id = str(target.id)
        sender_balance = get_balance(sender_id)
        
        if sender_balance < amount:
            response = f"**Transfer Failed! Not enough Zentrons! You have {sender_balance} {ZENTRON_EMOJI}.**"
            await send_with_retry(interaction, response)
            return
        
        set_balance(sender_id, sender_balance - amount)
        set_balance(receiver_id, get_balance(receiver_id) + amount)
        response = f"**Transfer Done! {amount} {ZENTRON_EMOJI} sent to {target.name}!**"
        await send_with_retry(interaction, response)

    @app_commands.command(name="crime", description="Take a risky shot for Zentrons")
    async def crime(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        last_crime = get_last_crime(user_id)
        now = int(datetime.utcnow().timestamp())
        
        if now - last_crime < CRIME_COOLDOWN:
            remaining = CRIME_COOLDOWN - (now - last_crime)
            response = f"**Lay Low! Wait {remaining // 60}m {remaining % 60}s before your next heist!**"
            await send_with_retry(interaction, response)
            return
        
        surge_mult = await get_surge_multiplier(str(interaction.guild.id))
        enterprise = get_enterprise(user_id)
        bonus = enterprise["crime_bonus"] if enterprise else 0
        outcomes = [
            ("Jackpot! You hacked a vault!", random.randint(100, 300)),
            ("Smooth gig, scored some cash.", random.randint(20, 50)),
            ("Bust! Got nothing this time.", 0),
            ("Caught! Paid a small fine.", -random.randint(10, 30)),
            ("Busted big! Lost a chunk.", -random.randint(50, 100))
        ]
        outcome, change = random.choice(outcomes)
        total_change = int((change + bonus) * apply_buff(user_id, "crime") * surge_mult)
        rare_drop = ""
        
        if total_change > 0 and random.random() < 0.1:
            drop = random.choice([("Crypto Key", random.randint(100, 300)), ("Dark Cache", random.randint(500, 1000))])
            total_change += drop[1]
            rare_drop = f"\n**Bonus Loot! Snagged a {drop[0]}! +{drop[1]} {ZENTRON_EMOJI}**"
            add_to_inventory(user_id, drop[0])
        
        new_balance = max(0, get_balance(user_id) + total_change)
        set_balance(user_id, new_balance)
        set_last_crime(user_id, now)
        bonus_text = f"(+{bonus} from {enterprise['name']})" if enterprise and total_change > 0 else''
        response = f"**{outcome} | {total_change if total_change != 0 else 'No'} {ZENTRON_EMOJI}{bonus_text}{rare_drop}{' [Surge x{surge_mult}]' if surge_mult > 1 else ''} | New balance: {new_balance}**"
        
        challenges = check_and_refresh_challenges(user_id, datetime.utcnow().date().isoformat())
        for challenge in challenges:
            if challenge["progress_key"] == "crime_count":
                challenge["progress"] = min(challenge["progress"] + 1, challenge["goal"])
                logger.info(f"Updated crime_count for {user_id}: {challenge['progress']}/{challenge['goal']}")
                if challenge["progress"] >= challenge["goal"]:
                    set_balance(user_id, get_balance(user_id) + challenge["reward"])
                    response += f"\nChallenge Complete: Finished '{challenge['task']}'! +{challenge['reward']} {ZENTRON_EMOJI}"
                    challenges.remove(challenge)
            elif challenge["progress_key"] == "earned" and total_change > 0:
                challenge["progress"] = min(challenge["progress"] + total_change, challenge["goal"])
                logger.info(f"Updated earned for {user_id}: {challenge['progress']}/{challenge['goal']}")
                if challenge["progress"] >= challenge["goal"]:
                    set_balance(user_id, get_balance(user_id) + challenge["reward"])
                    response += f"\nChallenge Complete: Finished '{challenge['task']}'! +{challenge['reward']} {ZENTRON_EMOJI}"
                    challenges.remove(challenge)
        set_challenges(user_id, challenges)
        
        contracts = check_and_refresh_contracts(user_id, datetime.utcnow().date().isoformat())
        for contract in contracts:
            if contract["progress_key"] == "crime_count":
                contract["progress"] = min(contract["progress"] + 1, contract["goal"])
                if contract["progress"] >= contract["goal"] and now < contract["start_time"] + 21600:
                    set_balance(user_id, get_balance(user_id) + contract["reward"])
                    add_to_inventory(user_id, contract["item"])
                    response += f"\nContract Complete: Finished '{contract['task']}'! +{contract['reward']} {ZENTRON_EMOJI} & {contract['item']}"
                    contracts.remove(contract)
            elif contract["progress_key"] == "crime_earned" and total_change > 0:
                contract["progress"] = min(contract["progress"] + total_change, contract["goal"])
                if contract["progress"] >= contract["goal"] and now < contract["start_time"] + 21600:
                    set_balance(user_id, get_balance(user_id) + contract["reward"])
                    add_to_inventory(user_id, contract["item"])
                    response += f"\nContract Complete: Finished '{contract['task']}'! +{contract['reward']} {ZENTRON_EMOJI} & {contract['item']}"
                    contracts.remove(contract)
            elif contract["progress_key"] == "earned" and total_change > 0:
                contract["progress"] = min(contract["progress"] + total_change, contract["goal"])
                if contract["progress"] >= contract["goal"] and now < contract["start_time"] + 21600:
                    set_balance(user_id, get_balance(user_id) + contract["reward"])
                    add_to_inventory(user_id, contract["item"])
                    response += f"\nContract Complete: Finished '{contract['task']}'! +{contract['reward']} {ZENTRON_EMOJI} & {contract['item']}"
                    contracts.remove(contract)
        set_contracts(user_id, contracts)
        
        await send_with_retry(interaction, response)

async def setup(bot):
    await bot.add_cog(Venture(bot))

async def teardown(bot):
    await bot.remove_cog('Venture')