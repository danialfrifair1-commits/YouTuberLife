import os
import math
import random
import sqlite3
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8884092010"))
DB_PATH = os.getenv("DB_PATH", "youtuberlive.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it in Railway Variables.")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row


def db(sql, params=(), fetch=False, many=False):
    cur = conn.cursor()
    if many:
        cur.executemany(sql, params)
    else:
        cur.execute(sql, params)
    conn.commit()
    if fetch:
        return cur.fetchall()
    return cur.lastrowid


def init_db():
    db("""
    CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        channel_name TEXT NOT NULL,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        coins INTEGER DEFAULT 1000,
        subscribers INTEGER DEFAULT 0,
        views INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0,
        comments INTEGER DEFAULT 0,
        videos INTEGER DEFAULT 0,
        fame INTEGER DEFAULT 0,
        best_views INTEGER DEFAULT 0,
        camera_level INTEGER DEFAULT 1,
        mic_level INTEGER DEFAULT 1,
        pc_level INTEGER DEFAULT 1,
        created_at TEXT
    )
    """)

    db("""
    CREATE TABLE IF NOT EXISTS youtubers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        photo_file_id TEXT,
        view_multiplier REAL DEFAULT 1.0,
        income_multiplier REAL DEFAULT 1.0,
        fame_multiplier REAL DEFAULT 1.0
    )
    """)

    db("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    defaults = {
        "base_upload_minutes": "60",
        "upload_minutes_per_level": "5",
        "base_views": "100",
        "views_per_level": "150",
        "base_coins": "50",
        "coins_per_level": "20",
        "camera_upgrade_base": "500",
        "mic_upgrade_base": "400",
        "pc_upgrade_base": "600",
        "channel_upgrade_base": "1000",
        "upgrade_growth": "1.6",
        "xp_per_video": "100",
        "max_level": "100",
    }
    for key, value in defaults.items():
        db("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))


def setting(key):
    row = db("SELECT value FROM settings WHERE key=?", (key,), fetch=True)
    return row[0]["value"] if row else None


def set_setting(key, value):
    db("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))


def get_player(user):
    row = db("SELECT * FROM players WHERE user_id=?", (user.id,), fetch=True)
    if row:
        return row[0]

    name = user.first_name or "Player"
    channel = f"{name} Gaming"
    db("""
        INSERT INTO players(user_id,name,channel_name,created_at)
        VALUES(?,?,?,?)
    """, (user.id, name, channel, datetime.utcnow().isoformat()))
    return db("SELECT * FROM players WHERE user_id=?", (user.id,), fetch=True)[0]


def xp_needed(level):
    return 500 + (level - 1) * 250


def add_xp(user_id, amount):
    row = db("SELECT level,xp FROM players WHERE user_id=?", (user_id,), fetch=True)[0]
    level, xp = row["level"], row["xp"] + amount
    max_level = int(setting("max_level"))
    while level < max_level and xp >= xp_needed(level):
        xp -= xp_needed(level)
        level += 1
    db("UPDATE players SET level=?,xp=? WHERE user_id=?", (level, xp, user_id))


def upload_minutes(level):
    base = int(setting("base_upload_minutes"))
    reduction = int(setting("upload_minutes_per_level"))
    return max(1, base - (level - 1) * reduction)


def calculate_video(level, camera, mic, pc):
    base_views = int(setting("base_views"))
    per_level = int(setting("views_per_level"))
    level_views = base_views + (level - 1) * per_level

    equipment_factor = 1 + ((camera - 1) + (mic - 1) + (pc - 1)) * 0.20
    low = max(10, int(level_views * 0.75 * equipment_factor))
    high = max(low + 1, int(level_views * 1.25 * equipment_factor))
    views = random.randint(low, high)

    base_coins = int(setting("base_coins"))
    coins_per_level = int(setting("coins_per_level"))
    coins = max(1, int((base_coins + (level - 1) * coins_per_level) * equipment_factor))
    likes = max(1, int(views * random.uniform(0.04, 0.11)))
    comments = max(1, int(views * random.uniform(0.003, 0.018)))
    fame = max(1, int(math.sqrt(views) / 4))

    return views, coins, likes, comments, fame


def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 یوتیوبرها", callback_data="youtubers"),
         InlineKeyboardButton("🎥 ساخت ویدیو", callback_data="video")],
        [InlineKeyboardButton("👤 پروفایل", callback_data="profile"),
         InlineKeyboardButton("🛒 فروشگاه", callback_data="shop")],
        [InlineKeyboardButton("🏆 رتبه‌بندی", callback_data="ranking")],
    ])


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 مدیریت یوتیوبرها", callback_data="admin_youtubers")],
        [InlineKeyboardButton("👥 مدیریت بازیکنان", callback_data="admin_players")],
        [InlineKeyboardButton("💰 اقتصاد و هزینه‌ها", callback_data="admin_economy")],
        [InlineKeyboardButton("📊 آمار بازی", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⚙️ تنظیمات بازی", callback_data="admin_settings")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="home")],
    ])


def profile_text(p):
    needed = xp_needed(p["level"])
    return f"""╔══════════════════════╗
       🎬 YOUTUBER LIFE
╚══════════════════════╝

👤 نام: {p["name"]}
🏆 لول: {p["level"]}
⭐ XP: {p["xp"]:,} / {needed:,}

📺 کانال: {p["channel_name"]}
👥 سابسکرایبر: {p["subscribers"]:,}
👀 بازدید کل: {p["views"]:,}

💰 موجودی: {p["coins"]:,} 🪙
🔥 شهرت: {p["fame"]:,}
🎬 ویدیوها: {p["videos"]}

━━━━━━━━━━━━━━━━━━
📊 آمار کانال
❤️ لایک: {p["likes"]:,}
💬 کامنت: {p["comments"]:,}
🎯 بهترین ویدیو: {p["best_views"]:,} بازدید
━━━━━━━━━━━━━━━━━━

🎒 تجهیزات
📷 دوربین: Level {p["camera_level"]}
🎙 میکروفون: Level {p["mic_level"]}
💻 سیستم: Level {p["pc_level"]}"""


def profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 آمار کانال", callback_data="stats"),
         InlineKeyboardButton("🎒 تجهیزات", callback_data="equipment")],
        [InlineKeyboardButton("🏆 دستاوردها", callback_data="achievements")],
        [InlineKeyboardButton("✏️ ویرایش کانال", callback_data="edit_channel")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="home")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_user)
    await update.effective_message.reply_text(
        f"🎬 به YouTuber Life خوش اومدی، {p['name']}!\n\n"
        "برای باز کردن بازی می‌تونی /start بزنی یا داخل گروه بنویسی «یوتیوب».",
        reply_markup=main_keyboard(),
    )


async def youtube_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    text = (update.effective_message.text or "").strip().lower()
    if text in {"یوتیوب", "youtube", "یوتیوبر", "youtuber"}:
        get_player(update.effective_user)
        await update.effective_message.reply_text(
            "🎬 پنل YouTuber Life",
            reply_markup=main_keyboard()
        )


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.effective_message.reply_text("⛔ دسترسی ندارید.")
        return
    await update.effective_message.reply_text("👑 پنل مدیریت", reply_markup=admin_keyboard())


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    p = get_player(user)
    data = q.data

    if data == "home":
        await q.edit_message_text("🎬 پنل اصلی YouTuber Life", reply_markup=main_keyboard())

    elif data == "profile":
        await q.edit_message_text(profile_text(p), reply_markup=profile_keyboard())

    elif data == "stats":
        await q.edit_message_text(
            f"📊 آمار کانال\n\n"
            f"📺 {p['channel_name']}\n"
            f"👥 سابسکرایبر: {p['subscribers']:,}\n"
            f"👀 بازدید: {p['views']:,}\n"
            f"❤️ لایک: {p['likes']:,}\n"
            f"💬 کامنت: {p['comments']:,}\n"
            f"🔥 شهرت: {p['fame']:,}\n"
            f"🎬 ویدیو: {p['videos']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 پروفایل", callback_data="profile")]])
        )

    elif data == "equipment":
        await q.edit_message_text(
            f"🎒 تجهیزات\n\n📷 دوربین: Level {p['camera_level']}\n"
            f"🎙 میکروفون: Level {p['mic_level']}\n💻 سیستم: Level {p['pc_level']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 ارتقا", callback_data="shop")],
                                                [InlineKeyboardButton("🔙 پروفایل", callback_data="profile")]])
        )

    elif data == "achievements":
        achievements = []
        if p["videos"] >= 1: achievements.append("🎬 اولین ویدیو")
        if p["videos"] >= 10: achievements.append("🔥 10 ویدیو")
        if p["subscribers"] >= 1000: achievements.append("👥 1K سابسکرایبر")
        if p["views"] >= 100000: achievements.append("👀 100K بازدید")
        if p["level"] >= 10: achievements.append("🏆 Level 10")
        text = "🏆 دستاوردها\n\n" + ("\n".join(achievements) if achievements else "هنوز دستاوردی باز نشده.")
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 پروفایل", callback_data="profile")]]))

    elif data == "edit_channel":
        context.user_data["awaiting_channel_name"] = True
        await q.edit_message_text("✏️ نام جدید کانالت رو به صورت یک پیام بفرست.")

    elif data == "video":
        minutes = upload_minutes(p["level"])
        await q.edit_message_text(
            f"🎥 ساخت ویدیو\n\n"
            f"🏆 لول فعلی: {p['level']}\n"
            f"⏱ زمان آپلود: {minutes} دقیقه\n"
            f"👀 سطح لول روی بازدید اثر می‌گذارد.\n\n"
            "برای شروع، روی دکمه زیر بزن.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 شروع آپلود", callback_data="start_upload")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="home")]
            ])
        )

    elif data == "start_upload":
        minutes = upload_minutes(p["level"])
        context.job_queue.run_once(finish_video, minutes * 60, data={"user_id": user.id, "chat_id": q.message.chat_id})
        await q.edit_message_text(
            f"⏳ ویدیو در حال آپلود است...\n\n"
            f"🏆 لول: {p['level']}\n"
            f"⏱ زمان باقی‌مانده: {minutes} دقیقه\n\n"
            "وقتی آپلود تمام شود نتیجه ارسال می‌شود."
        )

    elif data == "shop":
        await show_shop(q, p)

    elif data.startswith("upgrade_"):
        kind = data.replace("upgrade_", "")
        await upgrade(q, p, kind)

    elif data == "youtubers":
        rows = db("SELECT * FROM youtubers ORDER BY id DESC", fetch=True)
        if not rows:
            text = "🎬 هنوز یوتیوبری اضافه نشده."
            kb = [[InlineKeyboardButton("🔙 بازگشت", callback_data="home")]]
        else:
            text = "🎬 انتخاب یوتیوبر\n\n"
            kb = []
            for r in rows:
                kb.append([InlineKeyboardButton(r["name"], callback_data=f"yt_{r['id']}")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="home")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("yt_"):
        yt_id = int(data.split("_")[1])
        row = db("SELECT * FROM youtubers WHERE id=?", (yt_id,), fetch=True)
        if not row:
            await q.edit_message_text("این یوتیوبر پیدا نشد.", reply_markup=main_keyboard())
            return
        r = row[0]
        await q.edit_message_text(
            f"🎬 {r['name']}\n\n"
            f"📈 ضریب بازدید: x{r['view_multiplier']}\n"
            f"💰 ضریب درآمد: x{r['income_multiplier']}\n"
            f"🔥 ضریب شهرت: x{r['fame_multiplier']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 یوتیوبرها", callback_data="youtubers")]])
        )

    elif data == "ranking":
        rows = db("SELECT name,level,subscribers,views FROM players ORDER BY subscribers DESC, views DESC LIMIT 10", fetch=True)
        text = "🏆 رتبه‌بندی\n\n"
        for i, r in enumerate(rows, 1):
            text += f"{i}. {r['name']} — Lv.{r['level']} — 👥 {r['subscribers']:,}\n"
        await q.edit_message_text(text or "هنوز بازیکنی نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="home")]]))

    elif data == "admin":
        if user.id != ADMIN_ID:
            return
        await q.edit_message_text("👑 پنل مدیریت", reply_markup=admin_keyboard())

    elif data.startswith("admin_"):
        if user.id != ADMIN_ID:
            return
        await admin_action(q, context, data)


async def show_shop(q, p):
    growth = float(setting("upgrade_growth"))
    def cost(base, level):
        return int(float(base) * (growth ** (level - 1)))

    cam = cost(setting("camera_upgrade_base"), p["camera_level"])
    mic = cost(setting("mic_upgrade_base"), p["mic_level"])
    pc = cost(setting("pc_upgrade_base"), p["pc_level"])
    channel = cost(setting("channel_upgrade_base"), max(1, p["level"]))

    text = f"""🛒 فروشگاه ارتقا

💰 موجودی: {p['coins']:,} 🪙

📷 دوربین — Level {p['camera_level']}
هزینه ارتقا: {cam:,} 🪙

🎙 میکروفون — Level {p['mic_level']}
هزینه ارتقا: {mic:,} 🪙

💻 سیستم — Level {p['pc_level']}
هزینه ارتقا: {pc:,} 🪙

📺 کانال — Level {p['level']}
هزینه ارتقا: {channel:,} 🪙"""

    kb = [
        [InlineKeyboardButton(f"📷 ارتقای دوربین ({cam:,})", callback_data="upgrade_camera")],
        [InlineKeyboardButton(f"🎙 ارتقای میکروفون ({mic:,})", callback_data="upgrade_mic")],
        [InlineKeyboardButton(f"💻 ارتقای سیستم ({pc:,})", callback_data="upgrade_pc")],
        [InlineKeyboardButton(f"📺 ارتقای کانال ({channel:,})", callback_data="upgrade_channel")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="home")]
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))


async def upgrade(q, p, kind):
    growth = float(setting("upgrade_growth"))
    if kind == "camera":
        level = p["camera_level"]; base = int(setting("camera_upgrade_base"))
        cost = int(base * (growth ** (level - 1))); column = "camera_level"
    elif kind == "mic":
        level = p["mic_level"]; base = int(setting("mic_upgrade_base"))
        cost = int(base * (growth ** (level - 1))); column = "mic_level"
    elif kind == "pc":
        level = p["pc_level"]; base = int(setting("pc_upgrade_base"))
        cost = int(base * (growth ** (level - 1))); column = "pc_level"
    elif kind == "channel":
        level = p["level"]; base = int(setting("channel_upgrade_base"))
        cost = int(base * (growth ** (level - 1))); column = None
    else:
        return

    if p["coins"] < cost:
        await q.answer("❌ سکه کافی نیست.", show_alert=True)
        return

    if column:
        db(f"UPDATE players SET coins=coins-?, {column}={column}+1 WHERE user_id=?", (cost, p["user_id"]))
    else:
        db("UPDATE players SET coins=coins-? WHERE user_id=?", (cost, p["user_id"]))
        add_xp(p["user_id"], 250)

    await q.answer("✅ ارتقا انجام شد!")
    p = get_player(q.from_user)
    await show_shop(q, p)


async def finish_video(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    p = db("SELECT * FROM players WHERE user_id=?", (data["user_id"],), fetch=True)
    if not p:
        return
    p = p[0]

    views, coins, likes, comments, fame = calculate_video(
        p["level"], p["camera_level"], p["mic_level"], p["pc_level"]
    )
    db("""
        UPDATE players SET
        coins=coins+?, views=views+?, likes=likes+?, comments=comments+?,
        videos=videos+1, fame=fame+?, best_views=CASE WHEN ? > best_views THEN ? ELSE best_views END
        WHERE user_id=?
    """, (coins, views, likes, comments, fame, views, views, p["user_id"]))

    # subscribers grow from views and level
    subs = max(1, int(views * random.uniform(0.003, 0.015)))
    db("UPDATE players SET subscribers=subscribers+? WHERE user_id=?", (subs, p["user_id"]))
    add_xp(p["user_id"], int(setting("xp_per_video")))

    newp = get_player(type("U", (), {"id": p["user_id"], "first_name": p["name"]})())
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"""✅ آپلود کامل شد!

🎬 ویدیوی جدید منتشر شد

👀 بازدید: +{views:,}
👥 سابسکرایبر: +{subs:,}
❤️ لایک: +{likes:,}
💬 کامنت: +{comments:,}
💰 درآمد: +{coins:,} 🪙
🔥 شهرت: +{fame}

🏆 لول: {newp['level']}
⭐ XP: {newp['xp']:,} / {xp_needed(newp['level']):,}""",
        reply_markup=main_keyboard()
    )


async def admin_action(q, context, data):
    if data == "admin_youtubers":
        await q.edit_message_text(
            "🎬 مدیریت یوتیوبرها",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ افزودن یوتیوبر", callback_data="admin_add_yt")],
                [InlineKeyboardButton("📋 لیست یوتیوبرها", callback_data="admin_list_yt")],
                [InlineKeyboardButton("🗑 حذف یوتیوبر", callback_data="admin_delete_yt")],
                [InlineKeyboardButton("🔙 پنل ادمین", callback_data="admin")],
            ])
        )
    elif data == "admin_add_yt":
        context.user_data["admin_step"] = "yt_name"
        await q.edit_message_text("➕ نام یوتیوبر را بفرست.")
    elif data == "admin_list_yt":
        rows = db("SELECT * FROM youtubers ORDER BY id", fetch=True)
        text = "📋 یوتیوبرها\n\n"
        for r in rows:
            text += f"#{r['id']} — {r['name']} | 👀x{r['view_multiplier']} | 💰x{r['income_multiplier']}\n"
        await q.edit_message_text(text or "لیست خالی است.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 مدیریت", callback_data="admin_youtubers")]]))
    elif data == "admin_delete_yt":
        rows = db("SELECT id,name FROM youtubers ORDER BY id", fetch=True)
        kb = [[InlineKeyboardButton(f"🗑 {r['name']}", callback_data=f"admin_del_{r['id']}")] for r in rows]
        kb.append([InlineKeyboardButton("🔙 مدیریت", callback_data="admin_youtubers")])
        await q.edit_message_text("یوتیوبر موردنظر را انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("admin_del_"):
        yt_id = int(data.split("_")[-1])
        db("DELETE FROM youtubers WHERE id=?", (yt_id,))
        await q.edit_message_text("✅ یوتیوبر حذف شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 مدیریت", callback_data="admin_youtubers")]]))
    elif data == "admin_players":
        rows = db("SELECT name,level,coins,subscribers FROM players ORDER BY subscribers DESC LIMIT 15", fetch=True)
        text = "👥 بازیکنان\n\n"
        for r in rows:
            text += f"👤 {r['name']} | Lv.{r['level']} | 🪙 {r['coins']:,} | 👥 {r['subscribers']:,}\n"
        await q.edit_message_text(text or "بازیکنی نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 پنل ادمین", callback_data="admin")]]))
    elif data == "admin_economy":
        await q.edit_message_text(
            "💰 اقتصاد و هزینه‌ها\n\n"
            f"📷 دوربین: {setting('camera_upgrade_base')} پایه\n"
            f"🎙 میکروفون: {setting('mic_upgrade_base')} پایه\n"
            f"💻 سیستم: {setting('pc_upgrade_base')} پایه\n"
            f"📺 کانال: {setting('channel_upgrade_base')} پایه\n"
            f"📈 ضریب رشد: {setting('upgrade_growth')}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ تغییر هزینه‌ها", callback_data="admin_settings")],
                                                [InlineKeyboardButton("🔙 پنل ادمین", callback_data="admin")]])
        )
    elif data == "admin_stats":
        players = db("SELECT COUNT(*) c FROM players", fetch=True)[0]["c"]
        yts = db("SELECT COUNT(*) c FROM youtubers", fetch=True)[0]["c"]
        videos = db("SELECT COALESCE(SUM(videos),0) s FROM players", fetch=True)[0]["s"]
        views = db("SELECT COALESCE(SUM(views),0) s FROM players", fetch=True)[0]["s"]
        await q.edit_message_text(
            f"📊 آمار بازی\n\n👥 بازیکنان: {players}\n🎬 یوتیوبرها: {yts}\n"
            f"🎥 ویدیوها: {videos:,}\n👀 بازدید کل: {views:,}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 پنل ادمین", callback_data="admin")]])
        )
    elif data == "admin_broadcast":
        context.user_data["admin_step"] = "broadcast"
        await q.edit_message_text("📢 پیام همگانی را بفرست.")
    elif data == "admin_settings":
        await q.edit_message_text(
            "⚙️ تنظیمات بازی\n\n"
            f"⏱ زمان پایه آپلود: {setting('base_upload_minutes')} دقیقه\n"
            f"📉 کاهش زمان هر لول: {setting('upload_minutes_per_level')} دقیقه\n"
            f"👀 بازدید پایه: {setting('base_views')}\n"
            f"📈 بازدید هر لول: {setting('views_per_level')}\n"
            f"📷 هزینه دوربین: {setting('camera_upgrade_base')}\n"
            f"🎙 هزینه میکروفون: {setting('mic_upgrade_base')}\n"
            f"💻 هزینه سیستم: {setting('pc_upgrade_base')}\n"
            f"📺 هزینه کانال: {setting('channel_upgrade_base')}\n"
            f"📈 ضریب رشد هزینه: {setting('upgrade_growth')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏱ زمان آپلود", callback_data="admin_edit_upload")],
                [InlineKeyboardButton("👀 بازدید", callback_data="admin_edit_views")],
                [InlineKeyboardButton("💰 هزینه ارتقا", callback_data="admin_edit_costs")],
                [InlineKeyboardButton("🔙 پنل ادمین", callback_data="admin")],
            ])
        )
    elif data == "admin_edit_upload":
        context.user_data["admin_step"] = "edit_upload"
        await q.edit_message_text("فرمت: زمان_پایه کاهش_هر_لول\nمثال: 60 5")
    elif data == "admin_edit_views":
        context.user_data["admin_step"] = "edit_views"
        await q.edit_message_text("فرمت: بازدید_پایه بازدید_هر_لول\nمثال: 100 150")
    elif data == "admin_edit_costs":
        context.user_data["admin_step"] = "edit_costs"
        await q.edit_message_text("فرمت: دوربین میکروفون سیستم کانال ضریب\nمثال: 500 400 600 1000 1.6")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.effective_message.text or "").strip()

    if context.user_data.get("awaiting_channel_name"):
        if len(text) > 40:
            await update.effective_message.reply_text("نام کانال خیلی طولانی است.")
            return
        db("UPDATE players SET channel_name=? WHERE user_id=?", (text, user.id))
        context.user_data.pop("awaiting_channel_name", None)
        await update.effective_message.reply_text("✅ نام کانال تغییر کرد.", reply_markup=main_keyboard())
        return

    step = context.user_data.get("admin_step")
    if user.id == ADMIN_ID and step:
        if step == "yt_name":
            context.user_data["yt_name"] = text
            context.user_data["admin_step"] = "yt_photo"
            await update.effective_message.reply_text("🖼 حالا عکس یوتیوبر را به صورت Photo بفرست.")
            return

        if step == "broadcast":
            context.user_data.pop("admin_step", None)
            rows = db("SELECT user_id FROM players", fetch=True)
            sent = 0
            for r in rows:
                try:
                    await context.bot.send_message(r["user_id"], f"📢 پیام مدیریت:\n\n{text}")
                    sent += 1
                except Exception:
                    pass
            await update.effective_message.reply_text(f"✅ پیام برای {sent} بازیکن ارسال شد.")
            return

        if step == "edit_upload":
            try:
                base, reduction = map(int, text.split())
                set_setting("base_upload_minutes", base)
                set_setting("upload_minutes_per_level", reduction)
                context.user_data.pop("admin_step", None)
                await update.effective_message.reply_text("✅ تنظیم زمان آپلود ذخیره شد.", reply_markup=admin_keyboard())
            except Exception:
                await update.effective_message.reply_text("فرمت اشتباه است. مثال: 60 5")
            return

        if step == "edit_views":
            try:
                base, per = map(int, text.split())
                set_setting("base_views", base)
                set_setting("views_per_level", per)
                context.user_data.pop("admin_step", None)
                await update.effective_message.reply_text("✅ تنظیم بازدید ذخیره شد.", reply_markup=admin_keyboard())
            except Exception:
                await update.effective_message.reply_text("فرمت اشتباه است. مثال: 100 150")
            return

        if step == "edit_costs":
            try:
                cam, mic, pc, channel, growth = text.split()
                for key, value in [
                    ("camera_upgrade_base", cam),
                    ("mic_upgrade_base", mic),
                    ("pc_upgrade_base", pc),
                    ("channel_upgrade_base", channel),
                    ("upgrade_growth", growth),
                ]:
                    set_setting(key, value)
                context.user_data.pop("admin_step", None)
                await update.effective_message.reply_text("✅ هزینه‌ها ذخیره شدند.", reply_markup=admin_keyboard())
            except Exception:
                await update.effective_message.reply_text("فرمت اشتباه است. مثال: 500 400 600 1000 1.6")
            return

    await youtube_keyword(update, context)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID or context.user_data.get("admin_step") != "yt_photo":
        return

    name = context.user_data.get("yt_name")
    photo_id = update.effective_message.photo[-1].file_id
    db("""
        INSERT INTO youtubers(name,photo_file_id)
        VALUES(?,?)
        ON CONFLICT(name) DO UPDATE SET photo_file_id=excluded.photo_file_id
    """, (name, photo_id))
    context.user_data.pop("admin_step", None)
    context.user_data.pop("yt_name", None)
    await update.effective_message.reply_text(f"✅ یوتیوبر «{name}» اضافه شد.", reply_markup=admin_keyboard())


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("YouTuber Life bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
