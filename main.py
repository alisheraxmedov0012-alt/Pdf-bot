 import logging
import os
import img2pdf
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from flask import Flask
from threading import Thread

# --- RENDER UYG'OTUVCHI (WEB SERVER) ---
app = Flask('')
@app.route('/')
def home(): return "Bot Ishlamoqda!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- BOT SOZLAMALARI ---
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8344095954  # O'zingizning Telegram ID'ingizni yozing
CHANNELS = ["@Samarqandkvartiralarelonlari", "@Toshkent_kvartira_ijara_elonlari"]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

user_data = {}

# --- MAJBURIY OBUNA TEKSHIRISH ---
async def check_subscriptions(user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except: return False
    return True

# --- START KOMANDASI ---
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        kb = types.InlineKeyboardMarkup(row_width=1)
        for ch in CHANNELS:
            kb.add(types.InlineKeyboardButton(text=f"📢 Obuna bo'lish", url=f"https://t.me/{ch[1:]}"))
        kb.add(types.InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub"))
        return await message.answer("❗ Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=kb)
    
    welcome = """
🚀 **PRO PDF TOOLKIT BOT**

📸 **Rasm yuboring** -> PDF qilish uchun
📄 **PDF yuboring** -> Birlashtirish yoki Tahrirlash

🛠 **Mavjud funksiyalar:**
• Bir nechta rasmni 1 ta PDF qilish
• PDF-larni birlashtirish (Merge)
• PDF ma'lumotlarini ko'rish
• PDF-ga parol qo'yish (1234)
• Navbatni tozalash
"""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("🗑 Tozalash", "📊 Statistika")
    await message.answer(welcome, reply_markup=kb, parse_mode="Markdown")

# --- ADMIN UCHUN STATISTIKA ---
@dp.message_handler(text="📊 Statistika")
async def stat(message: types.Message):
    await message.answer(f"🤖 Bot hozircha aktiv rejimda ishlamoqda.")

# --- RASMLARNI QABUL QILISH ---
@dp.message_handler(content_types=["photo"])
async def photo_handler(message: types.Message):
    uid = message.from_user.id
    if uid not in user_data: user_data[uid] = {'photos': [], 'pdfs': []}
    
    file = await message.photo[-1].download()
    user_data[uid]['photos'].append(file.name)
    
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📄 PDF-ga aylantirish", callback_data="make_pdf"))
    await message.answer(f"📸 Rasm qo'shildi ({len(user_data[uid]['photos'])} ta)", reply_markup=kb)

# --- PDF FAYLLARNI QABUL QILISH ---
@dp.message_handler(content_types=["document"])
async def doc_handler(message: types.Message):
    if message.document.mime_type != 'application/pdf':
        return await message.answer("⚠️ Iltimos, faqat PDF yuboring!")
    
    uid = message.from_user.id
    if uid not in user_data: user_data[uid] = {'photos': [], 'pdfs': []}
    
    file = await message.document.download()
    user_data[uid]['pdfs'].append(file.name)
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Birlashtirish", callback_data="merge_pdf"),
        types.InlineKeyboardButton("🔒 Parol (1234)", callback_data="lock_pdf"),
        types.InlineKeyboardButton("ℹ️ Info", callback_data="pdf_info")
    )
    await message.answer("📄 PDF qabul qilindi. Nima qilamiz?", reply_markup=kb)

# --- CALLBACKLAR (TUGMALAR) ---
@dp.callback_query_handler(lambda c: True)
async def process_callbacks(call: types.CallbackQuery):
    uid = call.from_user.id
    
    if call.data == "check_sub":
        if await check_subscriptions(uid):
            await call.message.answer("✅ Rasm yoki PDF yuboring!")
        else:
            await call.answer("❌ Obuna bo'lmadingiz!", show_alert=True)

    elif call.data == "make_pdf":
        photos = user_data.get(uid, {}).get('photos', [])
        if not photos: return await call.answer("Rasmlar yo'q!")
        
        await call.message.answer("⏳ PDF tayyorlanmoqda...")
        out = f"pdf_{uid}.pdf"
        with open(out, "wb") as f: f.write(img2pdf.convert(photos))
        await bot.send_document(uid, open(out, 'rb'), caption="✅ Rasmlardan PDF tayyorlandi!")
        for img in photos: os.remove(img)
        os.remove(out)
        user_data[uid]['photos'] = []

    elif call.data == "merge_pdf":
        pdfs = user_data.get(uid, {}).get('pdfs', [])
        if len(pdfs) < 2: return await call.answer("Kamida 2 ta PDF yuboring!", show_alert=True)
        
        merger = PdfMerger()
        out = f"merged_{uid}.pdf"
        for p in pdfs: merger.append(p)
        merger.write(out); merger.close()
        await bot.send_document(uid, open(out, 'rb'), caption="✅ PDF-lar birlashtirildi!")
        for p in pdfs: os.remove(p)
        os.remove(out)
        user_data[uid]['pdfs'] = []

    elif call.data == "lock_pdf":
        pdfs = user_data.get(uid, {}).get('pdfs', [])
        if not pdfs: return await call.answer("Fayl yo'q!")
        
        reader = PdfReader(pdfs[-1]); writer = PdfWriter()
        for page in reader.pages: writer.add_page(page)
        writer.encrypt("1234")
        out = f"protected_{uid}.pdf"
        with open(out, "wb") as f: writer.write(f)
        await bot.send_document(uid, open(out, 'rb'), caption="🔒 Fayl parollangan: 1234")
        os.remove(out); os.remove(pdfs[-1]); user_data[uid]['pdfs'] = []

    elif call.data == "pdf_info":
        pdfs = user_data.get(uid, {}).get('pdfs', [])
        if not pdfs: return await call.answer("Fayl yo'q!")
        reader = PdfReader(pdfs[-1])
        await call.message.answer(f"ℹ️ PDF Ma'lumoti:\n📄 Sahifalar: {len(reader.pages)}")

# --- TOZALASH ---
@dp.message_handler(text="🗑 Tozalash")
async def clear_data(message: types.Message):
    user_data[message.from_user.id] = {'photos': [], 'pdfs': []}
    await message.answer("✅ Barcha navbatlar tozalandi!")

# --- RUN ---
if __name__ == "__main__":
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
        
