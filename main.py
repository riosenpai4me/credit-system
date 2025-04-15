import discord
from discord.ext import commands, tasks
import sqlite3
import time
import json

# تحميل الإعدادات من config.json
with open('config.json') as f:
    config = json.load(f)

TOKEN = config['token']
OWNER_ID = int(config['owner_id'])
ROLES = config['roles']

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ID القناة يلي بدك البوت يرسل فيها
CHANNEL_ID = 123456789012345678  # ← غيّر هذا

# Loop يشتغل كل 30 ثانية
@tasks.loop(seconds=30)
async def notify_every_30_seconds():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("🔁 رسالة كل 30 ثانية! استغل وقتك وفعّل الكريدت 💸")

def create_db():
    conn = sqlite3.connect('credits.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS credits (
                    user_id INTEGER PRIMARY KEY, 
                    credits INTEGER DEFAULT 0, 
                    last_daily INTEGER DEFAULT 0,
                    message_count INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def add_credits(user_id, amount):
    conn = sqlite3.connect('credits.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM credits WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        new_credits = result[0] + amount
        c.execute("UPDATE credits SET credits = ? WHERE user_id = ?", (new_credits, user_id))
    else:
        c.execute("INSERT INTO credits (user_id, credits) VALUES (?, ?)", (user_id, amount))
    conn.commit()
    conn.close()

def subtract_credits(user_id, amount):
    conn = sqlite3.connect('credits.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM credits WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        new_credits = max(result[0] - amount, 0)
        c.execute("UPDATE credits SET credits = ? WHERE user_id = ?", (new_credits, user_id))
    conn.commit()
    conn.close()

def get_credits(user_id):
    conn = sqlite3.connect('credits.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM credits WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def can_claim_daily(user_id):
    conn = sqlite3.connect('credits.db')
    c = conn.cursor()
    c.execute("SELECT last_daily FROM credits WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        last_claim = result[0]
        return int(time.time()) - last_claim >= 86400
    return True

def update_daily_time(user_id):
    conn = sqlite3.connect('credits.db')
    c = conn.cursor()
    c.execute("UPDATE credits SET last_daily = ? WHERE user_id = ?", (int(time.time()), user_id))
    conn.commit()
    conn.close()

def increment_message_count(user_id):
    conn = sqlite3.connect('credits.db')
    c = conn.cursor()
    c.execute("SELECT message_count FROM credits WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        new_count = result[0] + 1
        c.execute("UPDATE credits SET message_count = ? WHERE user_id = ?", (new_count, user_id))
    else:
        c.execute("INSERT INTO credits (user_id, message_count) VALUES (?, ?)", (user_id, 1))
    conn.commit()
    conn.close()

def check_message_reward(user_id):
    conn = sqlite3.connect('credits.db')
    c = conn.cursor()
    c.execute("SELECT message_count FROM credits WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0] >= 20:
        add_credits(user_id, 1000)
        c.execute("UPDATE credits SET message_count = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    conn.commit()
    conn.close()
    return False

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}! Ready to roll! 🎉')
    notify_every_30_seconds.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    user_id = message.author.id
    increment_message_count(user_id)
    if check_message_reward(user_id):
        await message.channel.send(f'🎉 {message.author.display_name} حصل على 1000 كريدت لإرساله 20 رسالة!')
    await bot.process_commands(message)

@bot.command()
async def credits(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = member.id
    credit = "∞" if user_id == OWNER_ID else get_credits(user_id)
    await ctx.send(f'💰 {member.display_name} لديه **{credit}** كريدت!')

@bot.command()
async def add(ctx, amount: int, member: discord.Member = None):
    if ctx.author.id != OWNER_ID:
        return await ctx.send('🚫 فقط صاحب البوت يقدر يستخدم هذا الأمر!')
    member = member or ctx.author
    add_credits(member.id, amount)
    await ctx.send(f'✅ تم إضافة {amount} كريدت لـ {member.display_name}.')

@bot.command()
async def subtract(ctx, amount: int, member: discord.Member = None):
    member = member or ctx.author
    subtract_credits(member.id, amount)
    await ctx.send(f'💸 تم خصم {amount} كريدت من {member.display_name}.')

@bot.command()
async def daily(ctx):
    user_id = ctx.author.id
    if can_claim_daily(user_id):
        add_credits(user_id, 1000)
        update_daily_time(user_id)
        await ctx.send(f'🎁 {ctx.author.display_name}، حصلت على 1000 كريدت اليومية!')
    else:
        await ctx.send(f'⏳ {ctx.author.display_name}، لقد أخذت الكريدت اليومي! جرب بعد 24 ساعة.')

@bot.command()
async def leaderboard(ctx):
    conn = sqlite3.connect('credits.db')
    c = conn.cursor()
    c.execute("SELECT user_id, credits FROM credits ORDER BY credits DESC LIMIT 10")
    top = c.fetchall()
    conn.close()

    msg = "🏆 **أفضل 10** 🏆\n"
    for i, (uid, credits) in enumerate(top, 1):
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else f"User({uid})"
        msg += f"{i}. {name} — {credits} كريدت\n"
    await ctx.send(msg)

@bot.command()
async def buy(ctx, *, role_name: str):
    user = ctx.author
    if role_name not in ROLES:
        return await ctx.send("❌ الرتبة غير موجودة! تأكد من الاسم.")

    cost = ROLES[role_name]
    if user.id == OWNER_ID or get_credits(user.id) >= cost:
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            return await ctx.send("❌ هذه الرتبة غير موجودة في السيرفر.")

        if user.id != OWNER_ID:
            subtract_credits(user.id, cost)

        await user.add_roles(role)
        await ctx.send(f'🎉 {user.display_name} اشترى رتبة **{role_name}**!')
    else:
        await ctx.send(f'❌ لا تملك كريدت كافي! تحتاج {cost} كريدت.')

@bot.command()
async def transfer(ctx, amount: int, member: discord.Member):
    sender_id = ctx.author.id
    receiver_id = member.id

    if sender_id == OWNER_ID:
        add_credits(receiver_id, amount)
        await ctx.send(f'🚀 أنت (الزعيم 😎) أعطيت {amount} كريدت لـ {member.display_name}.')
    else:
        if get_credits(sender_id) < amount:
            return await ctx.send("❌ ما عندك كريدت كافي!")
        subtract_credits(sender_id, amount)
        add_credits(receiver_id, amount)
        await ctx.send(f'🔄 {ctx.author.display_name} حول {amount} كريدت لـ {member.display_name}.')

create_db()
bot.run(TOKEN)
