import discord
from discord.ext import commands, tasks
import sqlite3
import json
import asyncio
import logging
from datetime import datetime
import random

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Zentrix')

# Bot setup with intents (using commands.Bot)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)  # You can change the prefix or remove it if you only use slash commands

# SQLite setup (keep this as is from Part 1)
conn = sqlite3.connect('zentrix.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY, 
    balance INTEGER, 
    bank INTEGER,
    last_work INTEGER, 
    last_crime INTEGER, 
    last_daily TEXT, 
    daily_streak INTEGER,
    inventory TEXT,
    buffs TEXT,
    last_buff INTEGER,
    challenges TEXT,
    nanopulse_count INTEGER,
    last_nanopulse_reset TEXT,
    contracts TEXT,
    last_rob INTEGER
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS enterprises (user_id TEXT PRIMARY KEY, data TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS tax_pool (id INTEGER PRIMARY KEY, amount INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS server_config (guild_id TEXT PRIMARY KEY, updates_channel_id TEXT, surge_active INTEGER, surge_end INTEGER, surge_multiplier REAL)''')
cursor.execute('INSERT OR IGNORE INTO tax_pool (id, amount) VALUES (1, 0)')
cursor.execute('UPDATE users SET inventory = ? WHERE inventory IS NULL', (json.dumps({}),))
cursor.execute('UPDATE users SET buffs = ? WHERE buffs IS NULL', (json.dumps({}),))
cursor.execute('UPDATE users SET last_buff = ? WHERE last_buff IS NULL', (0,))
cursor.execute('UPDATE users SET challenges = ? WHERE challenges IS NULL', (json.dumps([]),))
cursor.execute('UPDATE users SET nanopulse_count = ? WHERE nanopulse_count IS NULL', (0,))
cursor.execute('UPDATE users SET last_nanopulse_reset = ? WHERE last_nanopulse_reset IS NULL', ('1970-01-01',))
cursor.execute('UPDATE users SET bank = ? WHERE bank IS NULL', (0,))
cursor.execute('UPDATE users SET contracts = ? WHERE contracts IS NULL', (json.dumps([]),))
cursor.execute('UPDATE users SET last_rob = ? WHERE last_rob IS NULL', (0,))
cursor.execute('UPDATE enterprises SET data = json_set(data, "$.profit_earned", 0) WHERE json_extract(data, "$.profit_earned") IS NULL')
conn.commit()

# Constants (keep these from Part 1)
ZENTRONS_START = 500
ENTERPRISE_COST = 200
EVENT_CYCLE = 86400
TAX_RATE = 0.05
WORK_COOLDOWN = 300
CRIME_COOLDOWN = 900
DAILY_BASE = 50
BUFF_COOLDOWN = 3600
NANOPULSE_LIMIT = 3
ROB_COOLDOWN = 3600
ZENTRON_EMOJI = "<:Zentron:1344239317240905748>"
# Enterprise tiers (super hard progression)
TIERS = [
    {"name": "Side Hustle", "profit": 10, "work_bonus": 5, "crime_bonus": 0, "invest_cost": 200, "success_rate": 0.75, "profit_needed": 0},
    {"name": "Startup", "profit": 25, "work_bonus": 10, "crime_bonus": 5, "invest_cost": 500, "success_rate": 0.70, "profit_needed": 1000},
    {"name": "Firm", "profit": 50, "work_bonus": 20, "crime_bonus": 10, "invest_cost": 1000, "success_rate": 0.65, "profit_needed": 5000},
    {"name": "Corp", "profit": 100, "work_bonus": 35, "crime_bonus": 20, "invest_cost": 2000, "success_rate": 0.60, "profit_needed": 15000},
    {"name": "Conglomerate", "profit": 200, "work_bonus": 50, "crime_bonus": 35, "invest_cost": 5000, "success_rate": 0.55, "profit_needed": 30000},
    {"name": "Empire", "profit": 400, "work_bonus": 75, "crime_bonus": 50, "invest_cost": 10000, "success_rate": 0.50, "profit_needed": 60000},
    {"name": "Dynasty", "profit": 750, "work_bonus": 100, "crime_bonus": 75, "invest_cost": None, "success_rate": 0, "profit_needed": None}
]

# Predefined industries
INDUSTRIES = {
    "Cybernetics": {"profit_mult": 1.5, "work_mult": 0.8, "crime_mult": 1.0, "focus": "Passive Income", "vibe": "High-tech cash flow for chill tycoons"},
    "Quantum Computing": {"profit_mult": 1.2, "work_mult": 1.2, "crime_mult": 1.2, "focus": "Balanced Growth", "vibe": "Smart tech for all-round players"},
    "Nanotech": {"profit_mult": 1.0, "work_mult": 1.5, "crime_mult": 0.8, "focus": "Work Grinding", "vibe": "Nano-powered hustle for grind kings"},
    "Dark Matter": {"profit_mult": 0.8, "work_mult": 1.0, "crime_mult": 1.5, "focus": "Crime Payouts", "vibe": "Shady deals for risk junkies"},
    "AI Dynasties": {"profit_mult": 1.1, "work_mult": 1.1, "crime_mult": 1.1, "focus": "Steady Gains", "vibe": "AI-driven wins for steady climbers"}
}

# Titles
TITLES = [
    (25000, "Overlord"),
    (10000, "Zentron Lord"),
    (5000, "Magnate"),
    (1000, "Hustler"),
    (0, "Rookie")
]

# Buffs
BUFFS = {
    "NanoChip": {"multiplier": 1.25, "duration": 3600, "type": "work", "anti_rob": False},
    "Tech Relic": {"multiplier": 1.5, "duration": 86400, "type": "profit", "anti_rob": False},
    "Crypto Key": {"multiplier": 1.5, "duration": 3600, "type": "crime", "anti_rob": False},
    "Dark Cache": {"multiplier": 2.0, "duration": 43200, "type": "all", "anti_rob": False},
    "Secure Vault": {"multiplier": 1.0, "duration": 86400, "type": "anti_rob", "anti_rob": True}
}

# Challenges
CHALLENGES = [
    {"task": "Earn 500 Zentrons", "goal": 500, "progress_key": "earned", "reward": 100},
    {"task": "Use /work 5 times", "goal": 5, "progress_key": "work_count", "reward": 75},
    {"task": "Use /crime 3 times", "goal": 3, "progress_key": "crime_count", "reward": 50},
    {"task": "Invest in your enterprise", "goal": 1, "progress_key": "invest_count", "reward": 150},
    {"task": "Send 2 NanoPulses", "goal": 2, "progress_key": "nanopulse_count", "reward": 60}
]

# Tech Contracts (Mini-Quests)
CONTRACTS = {
    "Cybernetics": [
        {"task": "Earn 2000 Zentrons from profit", "goal": 2000, "progress_key": "profit_earned", "reward": 500, "item": "Tech Relic"},
        {"task": "Reach tier 3", "goal": 3, "progress_key": "tier_level", "reward": 300, "item": "NanoChip"}
    ],
    "Quantum Computing": [
        {"task": "Complete 5 challenges", "goal": 5, "progress_key": "challenges_completed", "reward": 400, "item": "Crypto Key"},
        {"task": "Earn 1000 Zentrons total", "goal": 1000, "progress_key": "earned", "reward": 250, "item": "NanoChip"}
    ],
    "Nanotech": [
        {"task": "Use /work 10 times", "goal": 10, "progress_key": "work_count", "reward": 350, "item": "NanoChip"},
        {"task": "Earn 1500 Zentrons from /work", "goal": 1500, "progress_key": "work_earned", "reward": 400, "item": "Tech Relic"}
    ],
    "Dark Matter": [
        {"task": "Earn 1000 Zentrons from /crime", "goal": 1000, "progress_key": "crime_earned", "reward": 450, "item": "Dark Cache"},
        {"task": "Use /crime 7 times", "goal": 7, "progress_key": "crime_count", "reward": 300, "item": "Crypto Key"}
    ],
    "AI Dynasties": [
        {"task": "Send 5 NanoPulses", "goal": 5, "progress_key": "nanopulse_count", "reward": 350, "item": "NanoChip"},
        {"task": "Reach tier 4", "goal": 4, "progress_key": "tier_level", "reward": 400, "item": "Tech Relic"}
    ]
}
# Utility functions
def get_balance(user_id: str) -> int:
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result is None:
        set_balance(user_id, ZENTRONS_START)
        return ZENTRONS_START
    return result[0] if result[0] is not None else ZENTRONS_START

def set_balance(user_id: str, amount: int):
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, amount, last_work, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, bank, json.dumps(contracts), last_rob))
    conn.commit()

def get_bank(user_id: str) -> int:
    cursor.execute('SELECT bank FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0

def set_bank(user_id: str, amount: int):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, amount, json.dumps(contracts), last_rob))
    conn.commit()

def get_last_work(user_id: str) -> int:
    cursor.execute('SELECT last_work FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0

def set_last_work(user_id: str, timestamp: int):
    balance = get_balance(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, timestamp, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, bank, json.dumps(contracts), last_rob))
    conn.commit()

def get_last_crime(user_id: str) -> int:
    cursor.execute('SELECT last_crime FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0

def set_last_crime(user_id: str, timestamp: int):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, timestamp, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, bank, json.dumps(contracts), last_rob))
    conn.commit()
def get_daily_info(user_id: str) -> tuple:
    cursor.execute('SELECT last_daily, daily_streak FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result is None or result[0] is None:
        return (None, 0)
    return (result[0], result[1] if result[1] is not None else 0)

def set_daily_info(user_id: str, last_daily: str, streak: int):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, last_crime, last_daily, streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, bank, json.dumps(contracts), last_rob))
    conn.commit()

def get_inventory(user_id: str) -> dict:
    cursor.execute('SELECT inventory FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return json.loads(result[0]) if result and result[0] is not None else {}

def set_inventory(user_id: str, inventory: dict):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, bank, json.dumps(contracts), last_rob))
    conn.commit()

def add_to_inventory(user_id: str, item: str, amount: int = 1):
    inventory = get_inventory(user_id)
    inventory[item] = inventory.get(item, 0) + amount
    set_inventory(user_id, inventory)

def remove_from_inventory(user_id: str, item: str):
    inventory = get_inventory(user_id)
    if item in inventory and inventory[item] > 0:
        inventory[item] -= 1
        if inventory[item] == 0:
            del inventory[item]
        set_inventory(user_id, inventory)
        return True
    return False

def get_buffs(user_id: str) -> dict:
    cursor.execute('SELECT buffs FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return json.loads(result[0]) if result and result[0] is not None else {}

def set_buffs(user_id: str, buffs: dict):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, bank, json.dumps(contracts), last_rob))
    conn.commit()
def get_last_buff(user_id: str) -> int:
    cursor.execute('SELECT last_buff FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0

def set_last_buff(user_id: str, timestamp: int):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), timestamp, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, bank, json.dumps(contracts), last_rob))
    conn.commit()

def apply_buff(user_id: str, buff_type: str) -> float:
    buffs = get_buffs(user_id)
    now = int(datetime.utcnow().timestamp())
    multiplier = 1.0
    for item, end_time in list(buffs.items()):
        if now > end_time:
            del buffs[item]
        elif BUFFS[item]["type"] in [buff_type, "all"]:
            multiplier *= BUFFS[item]["multiplier"]
    set_buffs(user_id, buffs)
    return multiplier

def is_anti_rob_active(user_id: str) -> bool:
    buffs = get_buffs(user_id)
    now = int(datetime.utcnow().timestamp())
    for item, end_time in list(buffs.items()):
        if now > end_time:
            del buffs[item]
        elif item == "Secure Vault" and BUFFS[item]["anti_rob"]:
            return True
    set_buffs(user_id, buffs)
    return False

def get_challenges(user_id: str) -> list:
    cursor.execute('SELECT challenges FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return json.loads(result[0]) if result and result[0] is not None else []

def set_challenges(user_id: str, challenges: list):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, bank, json.dumps(contracts), last_rob))
    conn.commit()

async def send_with_retry(interaction, content=None, embed=None, ephemeral=False):
    retries = 3
    delay = 5  # Start with 5-second delay
    for attempt in range(retries):
        try:
            if interaction.response.is_done():
                if embed:
                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                else:
                    await interaction.followup.send(content, ephemeral=ephemeral)
            else:
                if embed:
                    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
                else:
                    await interaction.response.send_message(content, ephemeral=ephemeral)
            return
        except discord.errors.HTTPException as e:
            if e.status == 429:  # Rate limit hit
                logger.warning(f"Rate limit hit! Retrying in {delay} seconds... Attempt {attempt + 1}/{retries}")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise  # Other errors, let them fail
    error_response = "Oops! I’m being rate limited by Discord. Try again in a bit!"
    if interaction.response.is_done():
        await interaction.followup.send(error_response, ephemeral=True)
    else:
        await interaction.response.send_message(error_response, ephemeral=True)
def check_and_refresh_challenges(user_id: str, current_date: str) -> list:
    challenges = get_challenges(user_id)
    last_daily = get_daily_info(user_id)[0]
    if not challenges or last_daily != current_date:
        challenges = random.sample(CHALLENGES, 3)
        for challenge in challenges:
            challenge["progress"] = 0
        set_challenges(user_id, challenges)
    return challenges

def get_contracts(user_id: str) -> list:
    cursor.execute('SELECT contracts FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return json.loads(result[0]) if result and result[0] is not None else []

def set_contracts(user_id: str, contracts: list):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, bank, json.dumps(contracts), last_rob))
    conn.commit()

def check_and_refresh_contracts(user_id: str, current_date: str) -> list:
    contracts = get_contracts(user_id)
    enterprise = get_enterprise(user_id)
    if not enterprise:
        return []
    last_daily = get_daily_info(user_id)[0]
    if not contracts or last_daily != current_date:
        industry_contracts = CONTRACTS[enterprise["industry"]]
        contracts = random.sample(industry_contracts, min(3, len(industry_contracts)))
        for contract in contracts:
            contract["progress"] = 0
            contract["start_time"] = int(datetime.utcnow().timestamp())
        set_contracts(user_id, contracts)
    return contracts

def get_nanopulse_count(user_id: str) -> int:
    cursor.execute('SELECT nanopulse_count FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0

def set_nanopulse_count(user_id: str, count: int):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), count, last_nanopulse_reset, bank, json.dumps(contracts), last_rob))
    conn.commit()

def get_last_nanopulse_reset(user_id: str) -> str:
    cursor.execute('SELECT last_nanopulse_reset FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else '1970-01-01'

def set_last_nanopulse_reset(user_id: str, reset_date: str):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    last_rob = get_last_rob(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, reset_date, bank, json.dumps(contracts), last_rob))
    conn.commit()

def get_last_rob(user_id: str) -> int:
    cursor.execute('SELECT last_rob FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0

def set_last_rob(user_id: str, timestamp: int):
    balance = get_balance(user_id)
    last_work = get_last_work(user_id)
    last_crime = get_last_crime(user_id)
    last_daily, daily_streak = get_daily_info(user_id)
    inventory = get_inventory(user_id)
    buffs = get_buffs(user_id)
    last_buff = get_last_buff(user_id)
    challenges = get_challenges(user_id)
    nanopulse_count = get_nanopulse_count(user_id)
    last_nanopulse_reset = get_last_nanopulse_reset(user_id)
    bank = get_bank(user_id)
    contracts = get_contracts(user_id)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, last_work, last_crime, last_daily, daily_streak, inventory, buffs, last_buff, challenges, nanopulse_count, last_nanopulse_reset, bank, contracts, last_rob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, balance, last_work, last_crime, last_daily, daily_streak, json.dumps(inventory), json.dumps(buffs), last_buff, json.dumps(challenges), nanopulse_count, last_nanopulse_reset, bank, json.dumps(contracts), timestamp))
    conn.commit()

def get_title(balance: int) -> str:
    for threshold, title in TITLES:
        if balance >= threshold:
            return title
    return "Rookie"

def get_enterprise(user_id: str) -> dict:
    cursor.execute('SELECT data FROM enterprises WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return json.loads(result[0]) if result and result[0] is not None else None

def set_enterprise(user_id: str, enterprise_data: dict):
    cursor.execute('INSERT OR REPLACE INTO enterprises (user_id, data) VALUES (?, ?)', (user_id, json.dumps(enterprise_data)))
    conn.commit()

def get_tax_pool() -> int:
    cursor.execute('SELECT amount FROM tax_pool WHERE id = 1')
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0

def set_tax_pool(amount: int):
    cursor.execute('UPDATE tax_pool SET amount = ? WHERE id = 1', (amount,))
    conn.commit()

def get_updates_channel(guild_id: str) -> str:
    cursor.execute('SELECT updates_channel_id FROM server_config WHERE guild_id = ?', (guild_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else None

def set_updates_channel(guild_id: str, channel_id: str):
    cursor.execute('INSERT OR REPLACE INTO server_config (guild_id, updates_channel_id, surge_active, surge_end, surge_multiplier) VALUES (?, ?, COALESCE((SELECT surge_active FROM server_config WHERE guild_id = ?), 0), COALESCE((SELECT surge_end FROM server_config WHERE guild_id = ?), 0), COALESCE((SELECT surge_multiplier FROM server_config WHERE guild_id = ?), 1.0))', 
                   (guild_id, channel_id, guild_id, guild_id, guild_id))
    conn.commit()

async def get_surge_multiplier(guild_id: str) -> float:
    cursor.execute('SELECT surge_active, surge_end, surge_multiplier FROM server_config WHERE guild_id = ?', (guild_id,))
    result = cursor.fetchone()
    if result and result[0] and int(datetime.utcnow().timestamp()) < result[1]:
        return result[2]
    return 1.0

# Load cogs and run bot
async def setup_bot():
    await bot.wait_until_ready()
    # Load cogs
    await bot.load_extension("venture")
    await bot.load_extension("extras")
    logger.info("Cogs loaded successfully")

@bot.event
async def on_ready():
    logger.info(f'Zentrix activated as {bot.user} (ID: {bot.user.id})')
    await setup_bot()
    logger.info('Commands deployed globally')

# Background tasks (keep from Part 6, but update to use bot instead of client)
async def profit_cycle():
    await bot.wait_until_ready()
    while not bot.is_closed():
        total_tax = 0
        cursor.execute('SELECT user_id, data FROM enterprises')
        for user_id, data in cursor.fetchall():
            enterprise = json.loads(data)
            now = int(datetime.utcnow().timestamp())
            profit = enterprise["profit"]
            if enterprise["overclock_active"] and now < enterprise["overclock_end"]:
                profit *= 3
            elif now < enterprise["crash_end"]:
                profit //= 2
            profit = int(profit * apply_buff(user_id, "profit"))
            tax = int(profit * TAX_RATE)
            net_profit = profit - tax
            current_balance = get_balance(user_id)
            enterprise["profit_earned"] = enterprise.get("profit_earned", 0) + net_profit
            set_enterprise(user_id, enterprise)
            set_balance(user_id, current_balance + net_profit)
            total_tax += tax
            logger.info(f"Profit: {net_profit} Zentrons (tax: {tax}) to {user_id} from {enterprise['name']}")
            await asyncio.sleep(1)  # 1-second delay per user
        set_tax_pool(get_tax_pool() + total_tax)
        await asyncio.sleep(3600)

async def market_shift():
    await bot.wait_until_ready()
    while not bot.is_closed():
        shift = "dip" if datetime.utcnow().hour % 2 == 0 else "surge"
        cursor.execute('SELECT user_id, data FROM enterprises')
        for user_id, data in cursor.fetchall():
            enterprise = json.loads(data)
            enterprise["profit"] = max(5, enterprise["profit"] - 5) if shift == "dip" else enterprise["profit"] + 5
            set_enterprise(user_id, enterprise)
        for guild in bot.guilds:
            channel_id = get_updates_channel(str(guild.id))
            if channel_id:
                channel = guild.get_channel(int(channel_id))
                if channel:
                    await channel.send(f"📈 **Market Shift**: {shift.capitalize()} hits! Empire profits tweaked.")
        await asyncio.sleep(EVENT_CYCLE)

async def zentron_surge():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(random.randint(43200, 86400))  # 12-24 hours
        for guild in bot.guilds:
            now = int(datetime.utcnow().timestamp())
            duration = random.randint(3600, 7200)  # 1-2 hours
            multiplier = 3.0 if random.random() < 0.05 else 2.0  # 5% chance for 3x, else 2x
            cursor.execute('UPDATE server_config SET surge_active = 1, surge_end = ?, surge_multiplier = ? WHERE guild_id = ?', 
                           (now + duration, multiplier, str(guild.id)))
            conn.commit()
            channel_id = get_updates_channel(str(guild.id))
            if channel_id:
                channel = guild.get_channel(int(channel_id))
                if channel:
                    await channel.send(f"⚡ **Zentron Surge!** All rewards x{multiplier} for {(duration // 3600)}h{(duration % 3600) // 60}m!")
        await asyncio.sleep(duration)

# Main execution
async def main():
    async with bot:
        bot.loop.create_task(profit_cycle())
        bot.loop.create_task(market_shift())
        bot.loop.create_task(zentron_surge())
        await bot.start('MTM0Mzk3MjIyOTQ4MTc2Mjg5OA.GXSvO-.ixHx4L5sc_I2lUdJo6YyuhS9DnzAXB0q7gDZqc')  # Replace with your token

if __name__ == "__main__":
    asyncio.run(main())
