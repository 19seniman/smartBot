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

TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', '0'))  # Set your Telegram user ID in env

if not TOKEN or OWNER_ID == 0:
    raise EnvironmentError("BOT_TOKEN and OWNER_ID must be set in environment variables")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store payment confirmed users: {user_id: True}
payment_confirmed_users = {}

# Store pending sinyal requests: {user_id: update}
pending_sinyal_requests = {}

# Store current payment info image file_id and text (set by owner)
payment_image_file_id = None
payment_text = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Gunakan perintah:\n"
        "/sinyal - untuk sinyal trading hari ini\n"
        "/pembayaran - info pembayaran"
    )

async def sinyal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat_id = update.message.chat_id

    # Register pending request for this user
    pending_sinyal_requests[chat_id] = update.message

    # Notify owner
    keyboard = [
        [
            InlineKeyboardButton("Sinyal tersedia", callback_data=f"sinyal_tersedia_{chat_id}"),
            InlineKeyboardButton("Sinyal tidak tersedia", callback_data=f"sinyal_tidak_tersedia_{chat_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await context.bot.send_message(
            OWNER_ID,
            f"Permintaan sinyal trading hari ini dari @{user.username or user.full_name} (ID: {chat_id}). Pilih jawaban:",
            reply_markup=reply_markup,
        )
        await update.message.reply_text("Permintaan sinyal trading Anda telah dikirim ke pemilik bot. Mohon tunggu konfirmasi.")
    except Exception as e:
        logger.error(f"Error sending message to owner: {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat mengirim permintaan ke pemilik bot.")

async def tombol_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id != OWNER_ID:
        await query.edit_message_text("Anda bukan pemilik bot. Akses ditolak.")
        return

    data = query.data  # Format: sinyal_tersedia_<chat_id> or sinyal_tidak_tersedia_<chat_id>
    parts = data.split('_')
    if len(parts) < 3:
        await query.edit_message_text("Data callback tidak valid.")
        return
    action = parts[1]
    target_chat_id = int(parts[2])

    if target_chat_id not in pending_sinyal_requests:
        await query.edit_message_text("Permintaan sudah diproses atau tidak ditemukan.")
        return

    # Remove pending request as it is processed now
    pending_sinyal_requests.pop(target_chat_id)

    if action == "tersedia":
        # Send payment info to user (only if payment info set)
        if payment_image_file_id and payment_text:
            try:
                await context.bot.send_photo(chat_id=target_chat_id, photo=payment_image_file_id, caption=payment_text)
                payment_confirmed_users[target_chat_id] = True
                await query.edit_message_text(f"Sinyal trading tersedia. Pembayaran info telah dikirim ke user ID {target_chat_id}.")
            except Exception as e:
                logger.error(f"Error sending payment info to user {target_chat_id}: {e}")
                await query.edit_message_text(f"Gagal mengirim info pembayaran ke user ID {target_chat_id}.")
        else:
            await query.edit_message_text("Sinyal tersedia, tapi data pembayaran belum diset oleh pemilik bot.")
            await context.bot.send_message(OWNER_ID, 
                "Mohon upload gambar pembayaran dan kirim teks pembayaran dengan perintah /setpayment untuk mengupdate info pembayaran.")
    elif action == "tidak":
        try:
            await context.bot.send_message(target_chat_id, "Sinyal hari ini tidak tersedia.")
            await query.edit_message_text(f"Sinyal trading tidak tersedia untuk user ID {target_chat_id} telah dikonfirmasi.")
        except Exception as e:
            logger.error(f"Error notifying user {target_chat_id} about no signal: {e}")
            await query.edit_message_text("Terjadi kesalahan saat mengirim pesan ke user.")
    else:
        await query.edit_message_text("Aksi tidak dikenali.")

async def pembayaran(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id in payment_confirmed_users and payment_confirmed_users[chat_id]:
        if payment_image_file_id and payment_text:
            await update.message.reply_photo(photo=payment_image_file_id, caption=payment_text)
        else:
            await update.message.reply_text("Info pembayaran belum tersedia.")
    else:
        await update.message.reply_text("Anda belum terkonfirmasi pembayaran. Silakan kontak admin.")

async def setpayment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner command to set/update payment info with image and caption text."""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Perintah ini hanya bisa dijalankan oleh pemilik bot.")
        return

    if not update.message.photo:
        await update.message.reply_text("Tolong kirim gambar pembayaran bersamaan dengan perintah ini (caption sebagai teks pembayaran).")
        return

    global payment_image_file_id, payment_text

    # Get the largest photo
    photo = update.message.photo[-1]
    payment_image_file_id = photo.file_id

    # Use message caption as payment text
    payment_text = update.message.caption or "Info pembayaran tidak ada"

    await update.message.reply_text("Info pembayaran berhasil diperbarui. Mengirimkan info pembayaran ke pengguna terkonfirmasi...")

    # Send updated payment info to all confirmed users
    for user_id in list(payment_confirmed_users.keys()):
        try:
            await context.bot.send_photo(chat_id=user_id, photo=payment_image_file_id, caption=payment_text)
        except Exception as e:
            logger.error(f"Error sending updated payment info to user {user_id}: {e}")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Perintah tidak dikenali. Gunakan /sinyal atau /pembayaran.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sinyal", sinyal))
    app.add_handler(CommandHandler("pembayaran", pembayaran))
    app.add_handler(CommandHandler("setpayment", setpayment))
    app.add_handler(CallbackQueryHandler(tombol_callback))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    print("Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()

