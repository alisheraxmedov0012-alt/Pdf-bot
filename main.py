import os
import logging
import threading
from flask import Flask
import img2pdf
import fitz  # PyMuPDF
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- RENDER UYG'OTUVCHI (WEB SERVER) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Muvaffaqiyatli Ishlamoqda va Uyg'oq!"

def run():
    # Render taqdim etadigan portni oladi yoki 8080 da ishga tushadi
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True  # Asosiy kod to'xtasa, bu ham fonda to'g'ri yopilishi uchun
    t.start()

# --- BOT SOZLAMALARI ---
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8344095954  # Sizning Telegram ID raqamingiz
CHANNELS = ["@Samarqandkvartiralarelonlari", "@Toshkent_kvartira_ijara_elonlari"]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

user_data = {}

# --- ASOSIY REPLY MENU TUGMALARI ---
def get_main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📸 Rasm -> PDF", "➕ PDF-larni birlashtirish")
    kb.add("🖼 PDF -> Rasm (JPG)", "✂️ Sahifani o'chirish (1-sahifa)")
    kb.add("📉 PDF-ni siqish", "✍️ Suv belgisi (Watermark)")
    kb.add("🔒 PDF-ga parol qo'yish", "ℹ️ PDF ma'lumotlari")
    kb.add("🗑 Tozalash", "📊 Statistika")
    return kb

# --- MAJBURIY OBUNA TEKSHIRISH ---
async def check_subscriptions(user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

# --- START KOMANDASI ---
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        kb = types.InlineKeyboardMarkup(row_width=1)
        for ch in CHANNELS:
            kb.add(types.InlineKeyboardButton(text="📢 Obuna bo'lish", url=f"https://t.me/{ch[1:]}"))
        kb.add(types.InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub"))
        return await message.answer("❗ Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=kb)
    
    welcome = (
        "🚀 **PRO PDF TOOLKIT BOTGA XUSH KELIBSIZ!**\n\n"
        "Barcha funksiyalar pastki menyuda tayyor turibdi. "
        "Ishni boshlash uchun botga rasm yoki PDF fayl yuboring!"
    )
    await message.answer(welcome, reply_markup=get_main_keyboard(), parse_mode="Markdown")

# --- ADMIN UCHUN STATISTIKA ---
@dp.message_handler(text="📊 Statistika")
async def stat(message: types.Message):
    await message.answer("🤖 Bot hozircha aktiv rejimda ishlamoqda.")

# --- TOZALASH ---
@dp.message_handler(text="🗑 Tozalash")
async def clear_data(message: types.Message):
    uid = message.from_user.id
    if uid in user_data:
        for img in user_data[uid].get('photos', []):
            if os.path.exists(img): os.remove(img)
        for pdf in user_data[uid].get('pdfs', []):
            if os.path.exists(pdf): os.remove(pdf)
    user_data[uid] = {'photos': [], 'pdfs': []}
    await message.answer("✅ Barcha navbatlar va yuklangan fayllar tozalandi!", reply_markup=get_main_keyboard())

# --- MATNLI TUGMALAR LOGIKASI ---

@dp.message_handler(text="📸 Rasm -> PDF")
async def menu_make_pdf(message: types.Message):
    uid = message.from_user.id
    photos = user_data.get(uid, {}).get('photos', [])
    if not photos:
        return await message.answer("⚠️ Avval botga bir nechta rasm yuboring!")
    
    await message.answer("⏳ Rasmlar PDF formatga o'tkazilmoqda...")
    out = f"pdf_{uid}.pdf"
    try:
        with open(out, "wb") as f:
            f.write(img2pdf.convert(photos))
        await bot.send_document(uid, open(out, 'rb'), caption="✅ Rasmlaringizdan PDF tayyorlandi!")
        for img in photos:
            if os.path.exists(img): os.remove(img)
        if os.path.exists(out): os.remove(out)
        user_data[uid]['photos'] = []
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@dp.message_handler(text="➕ PDF-larni birlashtirish")
async def menu_merge_pdf(message: types.Message):
    uid = message.from_user.id
    pdfs = user_data.get(uid, {}).get('pdfs', [])
    if len(pdfs) < 2:
        return await message.answer("⚠️ Birlashtirish uchun kamida 2 ta PDF fayl yuboring!")
    
    await message.answer("⏳ PDF fayllar birlashtirilmoqda...")
    merger = PdfMerger()
    out = f"merged_{uid}.pdf"
    try:
        for p in pdfs:
            merger.append(p)
        merger.write(out)
        merger.close()
        await bot.send_document(uid, open(out, 'rb'), caption="✅ PDF fayllar birlashtirildi!")
        for p in pdfs:
            if os.path.exists(p): os.remove(p)
        if os.path.exists(out): os.remove(out)
        user_data[uid]['pdfs'] = []
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@dp.message_handler(text="🖼 PDF -> Rasm (JPG)")
async def menu_pdf_to_jpg(message: types.Message):
    uid = message.from_user.id
    pdfs = user_data.get(uid, {}).get('pdfs', [])
    if not pdfs:
        return await message.answer("⚠️ Avval botga PDF fayl yuboring!")
    
    await message.answer("⏳ PDF sahifalari rasmga aylantirilmoqda...")
    try:
        doc = fitz.open(pdfs[-1])
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap()
            img_path = f"page_{uid}_{page_num}.png"
            pix.save(img_path)
            await bot.send_photo(uid, open(img_path, 'rb'), caption=f"📄 {page_num+1}-sahifa")
            if os.path.exists(img_path): os.remove(img_path)
        doc.close()
        if os.path.exists(pdfs[-1]): os.remove(pdfs[-1])
        user_data[uid]['pdfs'] = []
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@dp.message_handler(text="✂️ Sahifani o'chirish (1-sahifa)")
async def menu_delete_page(message: types.Message):
    uid = message.from_user.id
    pdfs = user_data.get(uid, {}).get('pdfs', [])
    if not pdfs:
        return await message.answer("⚠️ Avval botga PDF fayl yuboring!")
    
    await message.answer("⏳ PDF-dan 1-sahifa olib tashlanmoqda...")
    try:
        reader = PdfReader(pdfs[-1])
        writer = PdfWriter()
        if len(reader.pages) <= 1:
            return await message.answer("⚠️ Fayl faqat 1 sahifadan iborat, uni o'chirib bo'lmaydi!")
        
        for i in range(1, len(reader.pages)):
            writer.add_page(reader.pages[i])
            
        out = f"deleted_{uid}.pdf"
        with open(out, "wb") as f:
            writer.write(f)
        await bot.send_document(uid, open(out, 'rb'), caption="✂️ PDF-ning birinchi sahifasi o'chirildi!")
        if os.path.exists(out): os.remove(out)
        if os.path.exists(pdfs[-1]): os.remove(pdfs[-1])
        user_data[uid]['pdfs'] = []
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@dp.message_handler(text="📉 PDF-ni siqish")
async def menu_compress_pdf(message: types.Message):
    uid = message.from_user.id
    pdfs = user_data.get(uid, {}).get('pdfs', [])
    if not pdfs:
        return await message.answer("⚠️ Avval botga PDF fayl yuboring!")
    
    await message.answer("⏳ PDF hajmi kichraytirilmoqda (Siqilmoqda)...")
    try:
        reader = PdfReader(pdfs[-1])
        writer = PdfWriter()
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
        
        out = f"compressed_{uid}.pdf"
        with open(out, "wb") as f:
            writer.write(f)
        await bot.send_document(uid, open(out, 'rb'), caption="📉 PDF fayl muvaffaqiyatli siqildi!")
        if os.path.exists(out): os.remove(out)
        if os.path.exists(pdfs[-1]): os.remove(pdfs[-1])
        user_data[uid]['pdfs'] = []
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@dp.message_handler(text="✍️ Suv belgisi (Watermark)")
async def menu_watermark_pdf(message: types.Message):
    uid = message.from_user.id
    pdfs = user_data.get(uid, {}).get('pdfs', [])
    if not pdfs:
        return await message.answer("⚠️ Avval botga PDF fayl yuboring!")
    
    await message.answer("⏳ PDF-ga `@Pdfuzmaster_bot` suv belgisi qo'yilmoqda...")
    try:
        doc = fitz.open(pdfs[-1])
        for page in doc:
            page.insert_text(fitz.Point(100, 300), "@Pdfuzmaster_bot", fontsize=50, color=(0.8, 0.8, 0.8), rotate=45)
        
        out = f"watermark_{uid}.pdf"
        doc.save(out)
        doc.close()
        await bot.send_document(uid, open(out, 'rb'), caption="✍️ PDF faylga mualliflik suv belgisi joylandi!")
        if os.path.exists(out): os.remove(out)
        if os.path.exists(pdfs[-1]): os.remove(pdfs[-1])
        user_data[uid]['pdfs'] = []
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@dp.message_handler(text="🔒 PDF-ga parol qo'yish")
async def menu_lock_pdf(message: types.Message):
    uid = message.from_user.id
    pdfs = user_data.get(uid, {}).get('pdfs', [])
    if not pdfs:
        return await message.answer("⚠️ Avval botga PDF fayl yuboring!")
    
    await message.answer("⏳ PDF fayl parollanmoqda...")
    try:
        reader = PdfReader(pdfs[-1])
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt("1234")
        out = f"protected_{uid}.pdf"
        with open(out, "wb") as f:
            writer.write(f)
        await bot.send_document(uid, open(out, 'rb'), caption="🔒 Fayl parollangan!\n🔑 Parol: 1234")
        if os.path.exists(out): os.remove(out)
        if os.path.exists(pdfs[-1]): os.remove(pdfs[-1])
        user_data[uid]['pdfs'] = []
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@dp.message_handler(text="ℹ️ PDF ma'lumotlari")
async def menu_pdf_info(message: types.Message):
    uid = message.from_user.id
    pdfs = user_data.get(uid, {}).get('pdfs', [])
    if not pdfs:
        return await message.answer("⚠️ Avval botga PDF fayl yuboring!")
    try:
        reader = PdfReader(pdfs[-1])
        await message.answer(f"ℹ️ **PDF Fayl Ma'lumotlari:**\n\n📄 Jami sahifalar soni: {len(reader.pages)} ta")
    except Exception as e:
        await message.answer("❌ PDF faylni o'qishda xatolik.")

# --- RASMLARNI QABUL QILISH ---
@dp.message_handler(content_types=["photo"])
async def photo_handler(message: types.Message):
    uid = message.from_user.id
    if uid not in user_data:
        user_data[uid] = {'photos': [], 'pdfs': []}
    
    file = await message.photo[-1].download()
    user_data[uid].setdefault('photos', []).append(file.name)
    await message.answer(f"📸 Rasm yuklandi ({len(user_data[uid]['photos'])} ta).\nPDF qilish uchun **'📸 Rasm -> PDF'** tugmasini bosing.")

# --- PDF FAYLLARNI QABUL QILISH ---
@dp.message_handler(content_types=["document"])
async def doc_handler(message: types.Message):
    if message.document.mime_type != 'application/pdf':
        return await message.answer("⚠️ Iltimos, faqat PDF formatdagi fayl yuboring!")
    
    uid = message.from_user.id
    if uid not in user_data:
        user_data[uid] = {'photos': [], 'pdfs': []}
    
    file = await message.document.download()
    user_data[uid].setdefault('pdfs', []).append(file.name)
    await message.answer(f"📄 PDF yuklandi ({len(user_data[uid]['pdfs'])} ta).\nEndi pastdagi funksiya tugmalaridan birini tanlang.")

# --- CALLBACK (OBUNA TEKSHIRISH TUGMASI) ---
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_callback(call: types.CallbackQuery):
    uid = call.from_user.id
    if await check_subscriptions(uid):
        await call.message.answer("✅ Obuna tasdiqlandi. Rasm yoki PDF yuborishingiz mumkin:", reply_markup=get_main_keyboard())
        await call.answer()
    else:
        await call.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz.", show_alert=True)

# --- LOYIHANI ISHGA TUSHIRISH (To'g'rilangan qismi) ---
if __name__ == "__main__":
    # 1. Birinchi bo'lib Flask veb-serverini alohida tizmda fonda yoqamiz
    keep_alive()
    
    # 2. Keyin esa aiogram botni asosiy tizimda ishga tushiramiz
    print("Bot va Web Server muvaffaqiyatli ishga tushirildi...")
    executor.start_polling(dp, skip_updates=True)
            
