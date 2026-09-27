import os
import random
import sqlite3
from contextlib import closing

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8884092010"))
DB_PATH = os.getenv("DB_PATH", "youtuberlive.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it in Railway Variables.")

# ---------------- DATABASE ----------------

def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                coins INTEGER NOT NULL DEFAULT 100,
                subscribers INTEGER NOT NULL DEFAULT 0,
                videos INTEGER NOT NULL DEFAULT 0,
                upgrade INTEGER NOT NULL DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS youtubers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                photo_id TEXT
            )
        """)
        conn.commit()

def ensure_player(user):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM players WHERE user_id=?", (user.id,))
        if not cur.fetchone():
            name = user.first_name or "بازیکن"
            cur.execute(
                "INSERT INTO players(user_id, name) VALUES (?, ?)",
                (user.id, name)
            )
            conn.commit()

def get_player(user_id):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id,name,coins,subscribers,videos,upgrade "
            "FROM players WHERE user_id=?",
            (user_id,)
        )
        return cur.fetchone()

def get_youtubers():
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id,name,photo_id FROM youtubers ORDER BY id")
        return cur.fetchall()

def add_youtuber(name, photo_id):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO youtubers(name,photo_id) VALUES (?,?)",
            (name, photo_id)
        )
        conn.commit()

def delete_youtuber(youtuber_id):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM youtubers WHERE id=?", (youtuber_id,))
        deleted = cur.rowcount
        conn.commit()
        return deleted > 0

# ---------------- KEYBOARDS ----------------

def main_keyboard(user_id):
    buttons = [
        [InlineKeyboardButton("🎬 یوتیوبرها", callback_data="youtubers")],
        [InlineKeyboardButton("🎥 ساخت ویدیو", callback_data="make_video")],
        [InlineKeyboardButton("👤 پروفایل", callback_data="profile"),
         InlineKeyboardButton("🛒 فروشگاه", callback_data="shop")],
        [InlineKeyboardButton("🏆 رتبه‌بندی", callback_data="ranking")],
    ]
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton("👑 پنل ادمین", callback_data="admin")])
    return InlineKeyboardMarkup(buttons)

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 برگشت", callback_data="home")]
    ])

# ---------------- PLAYER UI ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_player(update.effective_user)
    p = get_player(update.effective_user.id)
    text = (
        "🎮 <b>YouTuber Life</b>\n\n"
        f"سلام {p[1]} 👋\n"
        "از یک کانال کوچک شروع کن و کانالت را رشد بده!\n\n"
        f"💰 سکه: {p[2]}\n"
        f"👥 سابسکرایبر: {p[3]}\n"
        f"🎥 ویدیوها: {p[4]}"
    )
    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=main_keyboard(update.effective_user.id)
    )

async def show_home(query, user_id):
    p = get_player(user_id)
    text = (
        "🎮 <b>YouTuber Life</b>\n\n"
        f"💰 سکه: {p[2]}\n"
        f"👥 سابسکرایبر: {p[3]}\n"
        f"🎥 ویدیوها: {p[4]}\n"
        f"⭐ سطح ارتقا: {p[5]}"
    )
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=main_keyboard(user_id)
    )

async def show_profile(query, user_id):
    p = get_player(user_id)
    text = (
        "👤 <b>پروفایل شما</b>\n\n"
        f"📛 نام: {p[1]}\n"
        f"💰 سکه: {p[2]}\n"
        f"👥 سابسکرایبر: {p[3]}\n"
        f"🎥 تعداد ویدیو: {p[4]}\n"
        f"⭐ سطح ارتقا: {p[5]}"
    )
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=back_keyboard()
    )

async def show_youtubers(query):
    ys = get_youtubers()
    if not ys:
        await query.edit_message_text(
            "🎬 هنوز هیچ یوتیوبری اضافه نشده است.",
            reply_markup=back_keyboard()
        )
        return

    buttons = [
        [InlineKeyboardButton(f"🎬 {y[1]}", callback_data=f"yt:{y[0]}")]
        for y in ys
    ]
    buttons.append([InlineKeyboardButton("🔙 برگشت", callback_data="home")])
    await query.edit_message_text(
        "🎬 <b>انتخاب یوتیوبر</b>\n\nیکی را انتخاب کن:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_selected_youtuber(query, yt_id):
    ys = [y for y in get_youtubers() if y[0] == yt_id]
    if not ys:
        await query.answer("این یوتیوبر وجود ندارد.", show_alert=True)
        return

    _, name, photo_id = ys[0]
    caption = f"🎬 <b>{name}</b>\n\nاین یوتیوبر برای بازی انتخاب شد."
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 ساخت ویدیو", callback_data="make_video")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="youtubers")]
    ])

    if photo_id:
        try:
            await query.message.reply_photo(
                photo=photo_id, caption=caption, parse_mode="HTML",
                reply_markup=keyboard
            )
            await query.message.delete()
            return
        except Exception:
            pass

    await query.edit_message_text(
        caption, parse_mode="HTML", reply_markup=keyboard
    )

async def make_video(query, user_id):
    p = get_player(user_id)
    level = p[5]

    views = random.randint(500, 5000) * level
    gained_subs = max(1, views // random.randint(80, 150))
    coins = max(10, views // 100)

    new_coins = p[2] + coins
    new_subs = p[3] + gained_subs
    new_videos = p[4] + 1

    with closing(db()) as conn:
        conn.execute(
            "UPDATE players SET coins=?, subscribers=?, videos=? WHERE user_id=?",
            (new_coins, new_subs, new_videos, user_id)
        )
        conn.commit()

    text = (
        "🎥 <b>ویدیو منتشر شد!</b>\n\n"
        f"👀 بازدید: {views:,}\n"
        f"👥 سابسکرایبر جدید: +{gained_subs:,}\n"
        f"💰 درآمد: +{coins:,} سکه\n\n"
        f"💰 موجودی: {new_coins:,} سکه"
    )
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=back_keyboard()
    )

async def show_shop(query, user_id):
    p = get_player(user_id)
    level = p[5]
    cost = level * 250
    text = (
        "🛒 <b>فروشگاه</b>\n\n"
        f"⭐ سطح فعلی: {level}\n"
        f"💰 هزینه ارتقای بعدی: {cost:,} سکه\n\n"
        "با ارتقا، بازدید و درآمد ویدیوها بیشتر می‌شود."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⬆️ ارتقا ({cost:,} سکه)", callback_data="upgrade")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="home")]
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

async def upgrade(query, user_id):
    p = get_player(user_id)
    level = p[5]
    cost = level * 250

    if p[2] < cost:
        await query.answer(f"سکه کافی نیست. {cost:,} سکه لازم داری.", show_alert=True)
        return

    with closing(db()) as conn:
        conn.execute(
            "UPDATE players SET coins=coins-?, upgrade=upgrade+1 WHERE user_id=?",
            (cost, user_id)
        )
        conn.commit()

    await query.answer("ارتقا انجام شد! 🚀")
    await show_shop(query, user_id)

async def ranking(query):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT name, subscribers FROM players "
            "ORDER BY subscribers DESC LIMIT 10"
        )
        rows = cur.fetchall()

    if not rows:
        text = "🏆 هنوز بازیکنی ثبت نشده است."
    else:
        lines = ["🏆 <b>۱۰ نفر برتر</b>\n"]
        for i, (name, subs) in enumerate(rows, 1):
            lines.append(f"{i}. {name} — 👥 {subs:,}")
        text = "\n".join(lines)

    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=back_keyboard()
    )

# ---------------- ADMIN ----------------

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن یوتیوبر", callback_data="admin_add")],
        [InlineKeyboardButton("📋 لیست یوتیوبرها", callback_data="admin_list")],
        [InlineKeyboardButton("🗑 حذف یوتیوبر", callback_data="admin_delete")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="home")],
    ])

async def show_admin(query, user_id):
    if user_id != ADMIN_ID:
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    await query.edit_message_text(
        "👑 <b>پنل مدیریت</b>\n\n"
        "از اینجا می‌توانی یوتیوبرها را با عکس اضافه یا حذف کنی.",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )

async def admin_list(query):
    ys = get_youtubers()
    if not ys:
        text = "📋 لیست خالی است."
    else:
        text = "📋 <b>یوتیوبرها:</b>\n\n" + "\n".join(
            f"🆔 {y[0]} — {y[1]}" for y in ys
        )
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=back_keyboard()
    )

async def admin_delete_menu(query):
    ys = get_youtubers()
    if not ys:
        await query.edit_message_text(
            "🗑 چیزی برای حذف وجود ندارد.", reply_markup=back_keyboard()
        )
        return
    buttons = [
        [InlineKeyboardButton(f"🗑 {y[1]}", callback_data=f"del:{y[0]}")]
        for y in ys
    ]
    buttons.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin")])
    await query.edit_message_text(
        "🗑 کدام یوتیوبر حذف شود؟",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def admin_add_start(query, context):
    if query.from_user.id != ADMIN_ID:
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    context.user_data["admin_state"] = "waiting_name"
    await query.edit_message_text(
        "➕ <b>افزودن یوتیوبر</b>\n\n"
        "اول اسم یوتیوبر را در یک پیام بفرست.",
        parse_mode="HTML"
    )

async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    state = context.user_data.get("admin_state")

    if state == "waiting_name":
        if not update.message.text:
            await update.message.reply_text("لطفاً اسم را به صورت متن بفرست.")
            return
        context.user_data["new_yt_name"] = update.message.text.strip()
        context.user_data["admin_state"] = "waiting_photo"
        await update.message.reply_text(
            "✅ اسم ثبت شد.\nحالا <b>عکس یوتیوبر</b> را به صورت Photo بفرست.",
            parse_mode="HTML"
        )
        return

    if state == "waiting_photo":
        if not update.message.photo:
            await update.message.reply_text("لطفاً خودِ عکس را به صورت Photo بفرست.")
            return
        photo_id = update.message.photo[-1].file_id
        name = context.user_data.get("new_yt_name", "بدون نام")
        add_youtuber(name, photo_id)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ یوتیوبر «{name}» با عکس اضافه شد.\n\n"
            "برای مدیریت بیشتر /start را بزن."
        )

# ---------------- CALLBACKS ----------------

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    ensure_player(query.from_user)

    data = query.data

    if data == "home":
        await show_home(query, user_id)
    elif data == "profile":
        await show_profile(query, user_id)
    elif data == "youtubers":
        await show_youtubers(query)
    elif data.startswith("yt:"):
        await show_selected_youtuber(query, int(data.split(":")[1]))
    elif data == "make_video":
        await make_video(query, user_id)
    elif data == "shop":
        await show_shop(query, user_id)
    elif data == "upgrade":
        await upgrade(query, user_id)
    elif data == "ranking":
        await ranking(query)
    elif data == "admin":
        await show_admin(query, user_id)
    elif data == "admin_add":
        await admin_add_start(query, context)
    elif data == "admin_list":
        if user_id == ADMIN_ID:
            await admin_list(query)
    elif data == "admin_delete":
        if user_id == ADMIN_ID:
            await admin_delete_menu(query)
    elif data.startswith("del:"):
        if user_id == ADMIN_ID:
            yt_id = int(data.split(":")[1])
            if delete_youtuber(yt_id):
                await query.answer("حذف شد.")
            else:
                await query.answer("پیدا نشد.", show_alert=True)
            await admin_delete_menu(query)

# ---------------- MAIN ----------------

def main():
    init_db()

    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO,
        admin_message
    ))

    print("YouTuber Life is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
