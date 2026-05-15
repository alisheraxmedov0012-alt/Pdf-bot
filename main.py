import logging
import os
import img2pdf
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter, PdfMerger

from aiogram import Bot, Dispatcher, executor, types

API_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = ["@Samarqandkvartiralarelonlari", "@Toshkent_kvartira_ijara_elonlari"]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Ma'lumotlarni vaqtincha saqlash
user_data = {}

async def check_subscriptions(user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except: return False
    return True

async def send_sub_message(message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for ch in CHANNELS:
        kb.add(types.InlineKeyboardButton(text=f"📢 Obuna bo'lish", url=f"https://t.me/{ch[1:]}"))
    kb.add(types.InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub"))
    await message.answer("❗ Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=kb)

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        return await send_sub_message(message)
    
    welcome_text = """
🛠 **PDF TOOLKIT BOT** — Barcha imkoniyatlar bir yerda!

📥 **Nima yubora olasiz?**
1️⃣ Rasmlar yuboring (PDF qilish uchun)
2️⃣ PDF fayllar yuboring (Birlashtirish yoki tahrirlash uchun)

⚙️ **Asosiy menyu:**
"""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🗑 Tozalash", "📊 Statistika")
    await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")

# --- RASMLARNI QABUL QILISH ---
@dp.message_handler(content_types=["photo"])
async def photo_handler(message: types.Message):
    uid = message.from_user.id
    if uid not in user_data: user_data[uid] = {'photos': [], 'pdfs': []}
    
    photo = message.photo[-1]
    file = await photo.download()
    user_data[uid].setdefault('photos', []).append(file.name)
    
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📄 PDF-ga aylantirish", callback_data="make_pdf"))
    await message.answer(f"📸 Rasm qabul qilindi ({len(user_data[uid]['photos'])} ta)", reply_markup=kb)

# --- PDF FAYLLARNI QABUL QILISH ---
@dp.message_handler(content_types=["document"])
async def doc_handler(message: types.Message):
    uid = message.from_user.id
    if message.document.mime_type != 'application/pdf':
        return await message.answer("⚠️ Faqat PDF fayl yuboring!")

    if uid not in user_data: user_data[uid] = {'photos': [], 'pdfs': []}
    
    file = await message.document.download()
    user_data[uid].setdefault('pdfs', []).append(file.name)
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ Birlashtirish", callback_data="merge_pdf"),
        types.InlineKeyboardButton("🔒 Parol qo'yish", callback_data="set_password"),
        types.InlineKeyboardButton("ℹ️ Ma'lumot", callback_data="pdf_info")
    )
    await message.answer(f"📄 PDF qabul qilindi. Nima qilamiz?", reply_markup=kb)

# --- CALLBACKLAR ---
@dp.callback_query_handler(lambda c: True)
async def callback_all(call: types.CallbackQuery):
    uid = call.from_user.id
    
    if call.data == "check_sub":
        if await check_subscriptions(uid):
            await call.message.answer("✅ Xush kelibsiz! Rasm yoki PDF yuboring.")
        else:
            await call.answer("❌ Obuna topilmadi", show_alert=True)

    elif call.data == "make_pdf":
        if uid in user_data and user_data[uid].get('photos'):
            out = f"res_{uid}.pdf"
            with open(out, "wb") as f: f.write(img2pdf.convert(user_data[uid]['photos']))
            await bot.send_document(uid, open(out, 'rb'), caption="✅ Rasmlardan PDF tayyor!")
            for img in user_data[uid]['photos']: os.remove(img)
            os.remove(out)
            user_data[uid]['photos'] = []
        else: await call.answer("Rasmlar yo'q!")

    elif call.data == "merge_pdf":
        pdfs = user_data.get(uid, {}).get('pdfs', [])
        if len(pdfs) < 2: return await call.answer("Kamida 2 ta PDF kerak!", show_alert=True)
        
        merger = PdfMerger()
        out = f"merged_{uid}.pdf"
        for p in pdfs: merger.append(p)
        merger.write(out)
        merger.close()
        
        await bot.send_document(uid, open(out, 'rb'), caption="✅ PDF-lar birlashtirildi!")
        for p in pdfs: os.remove(p)
        os.remove(out)
        user_data[uid]['pdfs'] = []

    elif call.data == "pdf_info":
        pdf_list = user_data.get(uid, {}).get('pdfs', [])
        if not pdf_list: return await call.answer("Fayl yo'q")
        reader = PdfReader(pdf_list[-1])
        await call.message.answer(f"📊 Oxirgi PDF ma'lumotlari:\nSahifalar: {len(reader.pages)}")

    elif call.data == "set_password":
        await call.message.answer("⚠️ Hozircha standart '1234' paroli o'rnatiladi (Funksiya test rejimida)")
        pdf_list = user_data.get(uid, {}).get('pdfs', [])
        if not pdf_list: return
        reader = PdfReader(pdf_list[-1]); writer = PdfWriter()
        for page in reader.pages: writer.add_page(page)
        writer.encrypt("1234")
        out = f"locked_{uid}.pdf"
        with open(out, "wb") as f: writer.write(f)
        await bot.send_document(uid, open(out, 'rb'), caption="🔒 Parol: 1234")
        os.remove(out)

# --- TOZALASH ---
@dp.message_handler(lambda m: m.text == "🗑 Tozalash")
async def clear(message: types.Message):
    user_data[message.from_user.id] = {'photos': [], 'pdfs': []}
    await message.answer("✅ Navbat tozalandi!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
                                                                                       
