import logging
import os
import img2pdf
from PIL import Image
from pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter

from aiogram import Bot, Dispatcher, executor, types

API_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = ["@Samarqandkvartiralarelonlari", "@Toshkent_kvartira_ijara_elonlari"]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_photos = {}
waiting_pdf_name = {}

# =========================
# OBUNA TEKSHIRISH
# =========================

async def check_subscriptions(user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)

            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False

    return True

async def send_sub_message(message):
    kb = types.InlineKeyboardMarkup(row_width=1)

    for channel in CHANNELS:
        kb.add(
            types.InlineKeyboardButton(
                text=f"📢 {channel}",
                url=f"https://t.me/{channel[1:]}"
            )
        )

    kb.add(
        types.InlineKeyboardButton(
            text="✅ Tekshirish",
            callback_data="check_sub"
        )
    )

    await message.answer(
        "❗ Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling:",
        reply_markup=kb
    )

# =========================
# START
# =========================

@dp.message_handler(commands=["start"])
async def start(message: types.Message):

    if not await check_subscriptions(message.from_user.id):
        return await send_sub_message(message)

    text = """
🔥 PDF TOOLKIT BOT

📌 Imkoniyatlar:

🖼 Rasm → PDF
🖼 Ko‘p rasm → 1 PDF
📄 PDF → Rasm
📦 PDF siqish
✏ PDF nomini o‘zgartirish

📷 Rasm yuboring.
"""

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)

    kb.add("📄 PDF → Rasm")
    kb.add("🗑 Tozalash")

    await message.answer(text, reply_markup=kb)

# =========================
# OBUNA CALLBACK
# =========================

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_callback(callback: types.CallbackQuery):

    if await check_subscriptions(callback.from_user.id):
        await callback.message.answer(
            "✅ Obuna tasdiqlandi!\n\n📷 Endi rasm yuboring."
        )
    else:
        await callback.message.answer(
            "❌ Hali barcha kanallarga obuna bo‘lmadingiz."
        )

# =========================
# RASM QABUL
# =========================

@dp.message_handler(content_types=["photo"])
async def photo_handler(message: types.Message):

    if not await check_subscriptions(message.from_user.id):
        return await send_sub_message(message)

    user_id = message.from_user.id

    photo = message.photo[-1]

    file = await photo.download()

    if user_id not in user_photos:
        user_photos[user_id] = []

    user_photos[user_id].append(file.name)

    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton(
            "📄 PDF qilish",
            callback_data="make_pdf"
        )
    )

    await message.answer(
        f"✅ Rasm qo‘shildi: {len(user_photos[user_id])} ta",
        reply_markup=kb
    )

# =========================
# PDF YASASH
# =========================

@dp.callback_query_handler(lambda c: c.data == "make_pdf")
async def make_pdf(callback: types.CallbackQuery):

    user_id = callback.from_user.id

    if user_id not in user_photos:
        return await callback.message.answer("❌ Rasm topilmadi")

    images = user_photos[user_id]

    pdf_name = f"{user_id}.pdf"

    with open(pdf_name, "wb") as f:
        f.write(img2pdf.convert(images))

    await bot.send_document(
        callback.from_user.id,
        open(pdf_name, "rb"),
        caption="✅ PDF tayyor"
    )

    for img in images:
        if os.path.exists(img):
            os.remove(img)

    os.remove(pdf_name)

    user_photos[user_id] = []

# =========================
# PDF → RASM
# =========================

@dp.message_handler(content_types=["document"])
async def pdf_to_image(message: types.Message):

    if not await check_subscriptions(message.from_user.id):
        return await send_sub_message(message)

    doc = message.document

    if not doc.file_name.endswith(".pdf"):
        return

    file = await doc.download()

    pages = convert_from_path(file.name)

    await message.answer(f"📄 {len(pages)} ta sahifa topildi")

    for i, page in enumerate(pages):

        image_name = f"{message.from_user.id}_{i}.jpg"

        page.save(image_name, "JPEG")

        await bot.send_photo(
            message.from_user.id,
            open(image_name, "rb")
        )

        os.remove(image_name)

    os.remove(file.name)

# =========================
# TOZALASH
# =========================

@dp.message_handler(lambda m: m.text == "🗑 Tozalash")
async def clear_data(message: types.Message):

    user_id = message.from_user.id

    user_photos[user_id] = []

    await message.answer("✅ Barcha vaqtinchalik fayllar tozalandi")

# =========================
# ERROR HANDLER
# =========================

@dp.errors_handler()
async def errors(update, error):
    print(error)
    return True

# =========================
# RUN
# =========================

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
