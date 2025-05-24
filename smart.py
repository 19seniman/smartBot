import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not TOKEN or OWNER_ID == 0:
    raise EnvironmentError("BOT_TOKEN and OWNER_ID must be set in environment variables")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

payment_confirmed_users = {}
pending_sinyal_requests = {}
payment_text = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Gunakan perintah:\n"
        "/sinyal - untuk sinyal trading hari ini\n"
        "/pembayaran - info pembayaran\n"
        "/konfirmasi - kirim bukti pembayaran ke admin"
    )


async def sinyal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat_id = update.message.chat_id

    pending_sinyal_requests[chat_id] = update.message

    keyboard = [
        [
            InlineKeyboardButton(
                "Sinyal tersedia", callback_data=f"sinyal_tersedia_{chat_id}"
            ),
            InlineKeyboardButton(
                "Sinyal tidak tersedia", callback_data="sinyal_tidak_tersedia"
            ),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            OWNER_ID,
            f"Permintaan sinyal trading hari ini dari @{user.username or user.full_name} (ID: {chat_id}). Pilih jawaban:",
            reply_markup=reply_markup,
        )
        await update.message.reply_text(
            "Permintaan sinyal trading Anda telah dikirim ke pemilik bot. Mohon tunggu konfirmasi."
        )
    except Exception as e:
        logger.error(f"Error sending message to owner: {e}")
        await update.message.reply_text(
            "Maaf, terjadi kesalahan saat mengirim permintaan ke pemilik bot."
        )


async def tombol_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id != OWNER_ID:
        await query.edit_message_text("Anda bukan pemilik bot. Akses ditolak.")
        return

    data = query.data  # Example: sinyal_tersedia_123456789 or sinyal_tidak_tersedia
    logger.info(f"Received callback data: {data}")

    parts = data.split("_", 2)  # limit split to max 3 parts

    action = parts[0] if len(parts) > 0 else None
    status = parts[1] if len(parts) > 1 else None
    target_chat_id_str = parts[2] if len(parts) > 2 else None

    if action != "sinyal":
        await query.edit_message_text("Data callback tidak valid (prefix salah).")
        return

    global payment_text

    if status == "tersedia":
        if target_chat_id_str is None:
            await query.edit_message_text("ID pengguna tidak ditemukan.")
            return
        try:
            target_chat_id = int(target_chat_id_str)
        except ValueError:
            await query.edit_message_text("ID pengguna tidak valid.")
            return
        if target_chat_id not in pending_sinyal_requests:
            await query.edit_message_text("Permintaan sudah diproses atau tidak ditemukan.")
            return
        pending_sinyal_requests.pop(target_chat_id)
        if payment_text:
            try:
                await context.bot.send_message(
                    chat_id=target_chat_id, text=payment_text
                )
                payment_confirmed_users[target_chat_id] = True
                await query.edit_message_text(
                    f"Sinyal trading tersedia. Pembayaran info telah dikirim ke user ID {target_chat_id}."
                )
            except Exception as e:
                logger.error(
                    f"Error sending payment info to user {target_chat_id}: {e}"
                )
                await query.edit_message_text(
                    f"Gagal mengirim info pembayaran ke user ID {target_chat_id}."
                )
        else:
            await query.edit_message_text(
                "Sinyal tersedia, tapi data pembayaran belum diset oleh pemilik bot."
            )
            await context.bot.send_message(
                OWNER_ID,
                "Mohon kirim teks pembayaran dengan perintah /setpayment untuk mengupdate info pembayaran.",
            )
    elif status == "tidak":
        # For 'tidak' status, no target_chat_id expected, send a general message
        await query.edit_message_text("Sinyal trading tidak tersedia telah dikonfirmasi.")
        try:
            # Optionally notify all users waiting for signal that it's not available
            for chat_id in list(pending_sinyal_requests.keys()):
                await context.bot.send_message(
                    chat_id,
                    "Maaf sinyal hari ini tidak tersedia/sedang padat pengguna. Mohon coba lagi beberapa jam ke depan.",
                )
            # Clear all pending requests after notifying
            pending_sinyal_requests.clear()
        except Exception as e:
            logger.error(f"Error notifying users about no signal: {e}")
    else:
        await query.edit_message_text("Aksi callback tidak dikenali.")


async def pembayaran(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id in payment_confirmed_users and payment_confirmed_users[chat_id]:
        global payment_text
        if payment_text:
            await update.message.reply_text(payment_text)
        else:
            await update.message.reply_text("Info pembayaran belum tersedia.")
    else:
        await update.message.reply_text(
            "Anda belum terkonfirmasi pembayaran. Silakan kontak admin."
        )


async def setpayment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Perintah ini hanya bisa dijalankan oleh pemilik bot.")
        return
    text = update.message.text
    parts = text.split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text(
            "Tolong sertakan teks info pembayaran setelah perintah, misal:\n/setpayment Ini adalah info pembayaran saya..."
        )
        return
    global payment_text
    payment_text = parts[1].strip()
    await update.message.reply_text(
        "Info pembayaran berhasil diperbarui. Mengirimkan info pembayaran ke pengguna terkonfirmasi..."
    )
    for uid in list(payment_confirmed_users.keys()):
        try:
            await context.bot.send_message(chat_id=uid, text=payment_text)
        except Exception as e:
            logger.error(f"Error sending updated payment info to user {uid}: {e}")


async def konfirmasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat_id = update.message.chat_id
    args = context.args
    if not args:
        await update.message.reply_text(
            "Silakan kirim bukti pembayaran Anda setelah perintah /konfirmasi, contoh:\n/konfirmasi Link atau tulisan bukti pembayaran Anda."
        )
        return
    bukti = " ".join(args)
    try:
        await context.bot.send_message(
            OWNER_ID,
            f"Konfirmasi pembayaran dari @{user.username or user.full_name} (ID: {chat_id}):\n{bukti}",
        )
        await update.message.reply_text(
            "Terima kasih, bukti pembayaran Anda sudah dikirim ke admin."
        )
    except Exception as e:
        logger.error(f"Error mengirim konfirmasi pembayaran ke owner: {e}")
        await update.message.reply_text(
            "Maaf, terjadi kesalahan saat mengirim konfirmasi. Silakan coba lagi nanti."
        )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Perintah tidak dikenali. Gunakan /sinyal, /pembayaran, atau /konfirmasi."
    )


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sinyal", sinyal))
    app.add_handler(CommandHandler("pembayaran", pembayaran))
    app.add_handler(CommandHandler("setpayment", setpayment))
    app.add_handler(CommandHandler("konfirmasi", konfirmasi))
    app.add_handler(CallbackQueryHandler(tombol_callback))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()

