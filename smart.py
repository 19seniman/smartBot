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

payment_confirmed_users = {}
pending_sinyal_requests = {}
payment_text = None
payment_method_text = None  # Variable to store Ethereum wallet address or other payment method info

# Temporary storage for waiting confirmations, map from user_id to update.message
waiting_confirmations = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Gunakan perintah:\n"
        "/sinyal - untuk sinyal trading hari ini\n"
        "/pembayaran - info pembayaran\n"
        "/metodebayar - info metode pembayaran\n"
        "/konfirmasi - kirim bukti pembayaran ke admin"
    )

async def sinyal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat_id = update.message.chat_id
    pending_sinyal_requests[chat_id] = update.message
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

    if len(parts) != 3:
        await query.edit_message_text("Data callback tidak valid.")
        return

    action = parts[1]  # "tersedia" atau "tidak"
    try:
        target_chat_id = int(parts[2])
    except ValueError:
        await query.edit_message_text("ID pengguna tidak valid.")
        return

    if target_chat_id not in pending_sinyal_requests:
        await query.edit_message_text("Permintaan sudah diproses atau tidak ditemukan.")
        return

    pending_sinyal_requests.pop(target_chat_id)

    if action == "tersedia":
        global payment_text
        if payment_text:
            try:
                await context.bot.send_message(chat_id=target_chat_id, text=payment_text)
                payment_confirmed_users[target_chat_id] = True
                await query.edit_message_text(f"Sinyal trading tersedia. Pembayaran info telah dikirim ke user ID {target_chat_id}.")
            except Exception as e:
                logger.error(f"Error sending payment info to user {target_chat_id}: {e}")
                await query.edit_message_text(f"Gagal mengirim info pembayaran ke user ID {target_chat_id}.")
        else:
            await query.edit_message_text("Sinyal tersedia, tapi data pembayaran belum diset oleh pemilik bot.")
            await context.bot.send_message(
                OWNER_ID,
                "Mohon kirim teks pembayaran dengan perintah /setpayment untuk mengupdate info pembayaran."
            )
    elif action == "tidak":
        try:
            await context.bot.send_message(target_chat_id, "Maaf sinyal hari ini tidak tersedia.")
            await query.edit_message_text(f"Sinyal trading tidak tersedia untuk user ID {target_chat_id} telah dikonfirmasi.")
        except Exception as e:
            logger.error(f"Error notifying user {target_chat_id} about no signal: {e}")
            await query.edit_message_text("Terjadi kesalahan saat mengirim pesan ke user.")
    else:
        await query.edit_message_text("Aksi tidak dikenali.")

async def pembayaran(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id in payment_confirmed_users and payment_confirmed_users[chat_id]:
        global payment_text
        if payment_text:
            await update.message.reply_text(payment_text)
        else:
            await update.message.reply_text("Info pembayaran belum tersedia.")
    else:
        await update.message.reply_text("Anda belum terkonfirmasi pembayaran. Silakan kontak admin.")

async def setpayment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Perintah ini hanya bisa dijalankan oleh pemilik bot.")
        return
    text = update.message.text
    parts = text.split(' ', 1)
    if len(parts) < 2:
        await update.message.reply_text("Tolong sertakan teks info pembayaran setelah perintah, misal:\n/setpayment Ini adalah info pembayaran saya...")
        return
    global payment_text
    payment_text = parts[1].strip()
    await update.message.reply_text("Info pembayaran berhasil diperbarui. Mengirimkan info pembayaran ke pengguna terkonfirmasi...")
    for uid in list(payment_confirmed_users.keys()):
        try:
            await context.bot.send_message(chat_id=uid, text=payment_text)
        except Exception as e:
            logger.error(f"Error sending updated payment info to user {uid}: {e}")

async def setmetodebayar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Perintah ini hanya bisa dijalankan oleh pemilik bot.")
        return
    text = update.message.text
    parts = text.split(' ', 1)
    if len(parts) < 2:
        await update.message.reply_text("Tolong sertakan teks metode pembayaran setelah perintah, misal:\n/setmetodebayar Wallet Ethereum: 0x123abc...")
        return
    global payment_method_text
    payment_method_text = parts[1].strip()
    await update.message.reply_text("Metode pembayaran berhasil diperbarui.")

async def metodebayar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global payment_method_text
    if payment_method_text:
        await update.message.reply_text(f"Metode pembayaran:\n{payment_method_text}")
    else:
        await update.message.reply_text("Info metode pembayaran belum tersedia.")

async def konfirmasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat_id = update.message.chat_id
    args = context.args
    if not args:
        await update.message.reply_text(
            "Silakan kirim bukti pembayaran Anda setelah perintah /konfirmasi, contoh:\n/konfirmasi Link atau tulisan bukti pembayaran Anda."
        )
        return
    bukti = ' '.join(args)
    try:
        # Kirim bukti konfirmasi ke pemilik bot
        await context.bot.send_message(
            OWNER_ID,
            f"Konfirmasi pembayaran dari @{user.username or user.full_name} (ID: {chat_id}):\n{bukti}"
        )
        # Simpan update.message utk menunggu balasan pemilik
        waiting_confirmations[OWNER_ID] = {
            'from_user_id': chat_id,
            'from_user_name': user.username or user.full_name,
            'message': update.message,
        }
        await update.message.reply_text("Terima kasih, bukti pembayaran Anda sudah dikirim ke admin. Mohon tunggu balasan konfirmasi.")
    except Exception as e:
        logger.error(f"Error mengirim konfirmasi pembayaran ke owner: {e}")
        await update.message.reply_text(
            "Maaf, terjadi kesalahan saat mengirim konfirmasi. Silakan coba lagi nanti."
        )

async def balas_konfirmasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler khusus untuk pemilik bot membalas konfirmasi pembayaran pengguna."""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        return  # Hanya pemilik bot yang boleh

    if not update.message.reply_to_message:
        await update.message.reply_text("Mohon balas pesan konfirmasi pembayaran pengguna untuk membalas.")
        return

    replied = update.message.reply_to_message
    # Cek apakah pesan yang dibalas adalah pesan bot yang meneruskan konfirmasi pembayaran
    # Kita simpan data pengguna berdasarkan last konfirmasi disimpan di waiting_confirmations (lebih baik pakai DB sebenarnya)
    # Namun di sini memakai mekanisme sederhana: cari key user_id dan cocokkan user chat_id dari pesan
    # Karena ini kasus sederhana, kita mengirim balasan ke user yang mengirim konfirmasi terakhir

    # Cari user yang difokuskan oleh balasan ini dari waiting_confirmations
    # Cari first user yang belum dikonfirmasi dengan key OWNER_ID
    info = waiting_confirmations.get(OWNER_ID)
    if not info:
        await update.message.reply_text("Tidak ada konfirmasi pembayaran pengguna yang sedang menunggu balasan.")
        return

    to_user_id = info['from_user_id']
    try:
        # Kirim balasan ke pengguna
        await context.bot.send_message(to_user_id, f"Pesan dari admin:\n{update.message.text}")
        await update.message.reply_text("Balasan konfirmasi telah dikirim ke pengguna.")
        # Hapus dari waiting_confirmations agar tidak dikirim ulang
        waiting_confirmations.pop(OWNER_ID, None)
    except Exception as e:
        logger.error(f"Error mengirim balasan konfirmasi ke user {to_user_id}: {e}")
        await update.message.reply_text("Gagal mengirim balasan ke pengguna.")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Perintah tidak dikenali. Gunakan /sinyal, /pembayaran, /metodebayar, atau /konfirmasi."
    )

waiting_confirmations = {}

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sinyal", sinyal))
    app.add_handler(CommandHandler("pembayaran", pembayaran))
    app.add_handler(CommandHandler("setpayment", setpayment))
    app.add_handler(CommandHandler("setmetodebayar", setmetodebayar))
    app.add_handler(CommandHandler("metodebayar", metodebayar))
    app.add_handler(CommandHandler("konfirmasi", konfirmasi))
    # Handler untuk pemilik membalas pesan konfirmasi pembayaran pengguna dengan membalas pesan itu
    app.add_handler(MessageHandler(filters.TEXT & filters.User(OWNER_ID), balas_konfirmasi))
    app.add_handler(CallbackQueryHandler(tombol_callback))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    print("Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()
