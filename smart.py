async def tombol_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id != OWNER_ID:
        await query.edit_message_text("Anda bukan pemilik bot. Akses ditolak.")
        return

    data = query.data  # Format: sinyal_tersedia_<chat_id> or sinyal_tidak_tersedia_<chat_id>
    parts = data.split('_')
    
    if len(parts) != 3:  # Memastikan kita memiliki tepat 3 bagian
        await query.edit_message_text("Data callback tidak valid.")
        return

    action = parts[1]  # "tersedia" atau "tidak"
    try:
        target_chat_id = int(parts[2])  # Mengonversi chat_id menjadi integer
    except ValueError:
        await query.edit_message_text("ID pengguna tidak valid.")
        return

    if target_chat_id not in pending_sinyal_requests:
        await query.edit_message_text("Permintaan sudah diproses atau tidak ditemukan.")
        return

    # Menghapus permintaan yang sedang diproses
    pending_sinyal_requests.pop(target_chat_id)

    if action == "tersedia":
        # Mengirim informasi pembayaran jika tersedia
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
            await context.bot.send_message(target_chat_id, "Maaf sinyal hari ini tidak tersedia.")
            await query.edit_message_text(f"Sinyal trading tidak tersedia untuk user ID {target_chat_id} telah dikonfirmasi.")
        except Exception as e:
            logger.error(f"Error notifying user {target_chat_id} about no signal: {e}")
            await query.edit_message_text("Terjadi kesalahan saat mengirim pesan ke user.")
    else:
        await query.edit_message_text("Aksi tidak dikenali.")
