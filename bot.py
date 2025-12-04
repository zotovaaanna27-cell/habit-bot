import os
import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

HABITS = {
    "water": "Пить воду 💧",
    "reading": "Читать 📚",
    "movement": "Двигаться 🚶‍♀️",
    "selfcare": "Что-то приятное себе 💛",
}

user_state = {
    "habits": [],
    "logs": [],
}


def today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def last_7_days() -> list[str]:
    days = []
    today = datetime.utcnow().date()
    for i in range(7):
        days.append((today - timedelta(days=i)).strftime("%Y-%m-%d"))
    return list(reversed(days))


def set_log_for_today(habit_id: str, status: str) -> None:
    d = today_str()
    for entry in user_state["logs"]:
        if entry["date"] == d and entry["habit_id"] == habit_id:
            entry["status"] = status
            return
    user_state["logs"].append({"date": d, "habit_id": habit_id, "status": status})


def compute_stats():
    days = last_7_days()
    stats = {}

    for h in user_state["habits"]:
        stats[h] = {
            "label": HABITS[h],
            "total_done": 0,
            "best_streak": 0,
        }

    for habit_id in user_state["habits"]:
        best_streak = 0
        current_streak = 0
        for d in days:
            day_log = None
            for entry in user_state["logs"]:
                if entry["date"] == d and entry["habit_id"] == habit_id:
                    day_log = entry
                    break
            if day_log and day_log["status"] == "done":
                stats[habit_id]["total_done"] += 1
                current_streak += 1
                if current_streak > best_streak:
                    best_streak = current_streak
            else:
                current_streak = 0
        stats[habit_id]["best_streak"] = best_streak

    return stats


def habits_keyboard():
    buttons = []
    current = set(user_state["habits"])
    for habit_id, label in HABITS.items():
        selected = "✅ " if habit_id in current else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{selected}{label}",
                    callback_data=f"toggle_{habit_id}",
                )
            ]
        )
    buttons.append([InlineKeyboardButton("Готово ✅", callback_data="done_habits")])
    return InlineKeyboardMarkup(buttons)


def today_keyboard():
    buttons = []
    d = today_str()

    for habit_id in user_state["habits"]:
        label = HABITS[habit_id]
        status_text = ""

        for entry in user_state["logs"]:
            if entry["date"] == d and entry["habit_id"] == habit_id:
                if entry["status"] == "done":
                    status_text = "— уже отмечено как 'сделано' ✅"
                elif entry["status"] == "skipped":
                    status_text = "— уже отмечено как 'пропущено' ❌"
                break

        row = [
            InlineKeyboardButton(f"{label}", callback_data="noop"),
            InlineKeyboardButton("✅", callback_data=f"today_{habit_id}_done"),
            InlineKeyboardButton("❌", callback_data=f"today_{habit_id}_skipped"),
        ]
        buttons.append(row)

        if status_text:
            buttons.append(
                [InlineKeyboardButton(status_text, callback_data="noop")]
            )

    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Привет! Я твой личный мини-трекер привычек 🌱\n\n"
        "Помогу мягко отслеживать до 3 ежедневных привычек и показывать прогресс за неделю.\n\n"
        "Выбери привычки, которые хочешь трекать (до трёх штук):"
    )
    await update.message.reply_text(text, reply_markup=habits_keyboard())


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_state["habits"]:
        await update.message.reply_text(
            "Ты ещё не выбрала привычки. Нажми /start и добавь 1–3 привычки 🙌"
        )
        return

    text = (
        "Чек-ин за сегодня 🌞\n\n"
        "Отметь, что уже сделала по своим привычкам.\n"
        "Нажимай ✅ если выполнено, ❌ если решила пропустить."
    )
    await update.message.reply_text(text, reply_markup=today_keyboard())


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_state["habits"]:
        await update.message.reply_text(
            "Пока привычки не выбраны. Добавь их через /start, и я начну считать статистику 📊"
        )
        return

    stats_data = compute_stats()
    if not stats_data:
        await update.message.reply_text(
            "Пока нет данных за последние 7 дней. Попробуй отметить привычки через /today 🌱"
        )
        return

    lines = ["Твоя статистика за последние 7 дней 📊", ""]
    for habit_id, s in stats_data.items():
        lines.append(
            f"{s['label']} — {s['total_done']} / 7 дней, лучшая серия: {s['best_streak']} дня(ей) подряд"
        )

    await update.message.reply_text("\n".join(lines))


async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "noop":
        return

    if data.startswith("toggle_"):
        habit_id = data.split("toggle_")[1]
        current = user_state["habits"]
        if habit_id in current:
            current.remove(habit_id)
        else:
            if len(current) >= 3:
                await query.edit_message_text(
                    "Можно выбрать не более трёх привычек.\n\n"
                    "Сними одну из уже выбранных или нажми 'Готово ✅'.",
                    reply_markup=habits_keyboard(),
                )
                return
            current.append(habit_id)

        await query.edit_message_text(
            "Выбери привычки, которые хочешь трекать (до трёх штук):",
            reply_markup=habits_keyboard(),
        )
        return

    if data == "done_habits":
        if not user_state["habits"]:
            await query.edit_message_text(
                "Ты пока не выбрала ни одной привычки. Выбери хотя бы одну 🙌",
                reply_markup=habits_keyboard(),
            )
            return

        labels = [HABITS[h] for h in user_state["habits"]]
        text = (
            "Отлично! Сегодня будем трекать:\n"
            f"- " + "\n- ".join(labels) + "\n\n"
            "Когда захочешь отметить прогресс — нажми /today.\n"
            "Посмотреть статистику за неделю — /stats."
        )
        await query.edit_message_text(text)
        return

    if data.startswith("today_"):
        _, habit_id, status = data.split("_")
        if habit_id not in HABITS:
            return

        if status == "done":
            set_log_for_today(habit_id, "done")
        elif status == "skipped":
            set_log_for_today(habit_id, "skipped")

        try:
            await query.edit_message_reply_markup(reply_markup=today_keyboard())
        except Exception as e:
            logger.warning("Ошибка при обновлении клавиатуры today: %s", e)
        return


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is not set")

    application: Application = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(handle_callbacks))

    application.run_polling()


if __name__ == "__main__":
    main()
