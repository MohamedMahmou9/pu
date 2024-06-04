import os
import random
from datasets import load_dataset
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeAudioClip, TextClip, CompositeVideoClip, concatenate_videoclips
)
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from PIL import Image, ImageFilter
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# استيراد مجموعة البيانات
dataset = load_dataset("HeshamHaroon/arabic-quotes")

# إعداد مفتاح API وإنشاء العميل
api_key = os.getenv('ELEVENLABS_API_KEY')
client = ElevenLabs(api_key=api_key)

# إعداد بوت تليجرام
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
application = Application.builder().token(TELEGRAM_TOKEN).build()

# مسارات الملفات المؤقتة
image_folder = 'assets/images/'
sound_effect_folder = 'assets/effects/'
output_folder = 'assets/output/'
if not os.path.exists(image_folder):
    os.makedirs(image_folder)
if not os.path.exists(sound_effect_folder):
    os.makedirs(sound_effect_folder)
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# قائمة لتخزين المسارات
user_data = {}

# تحويل النص إلى كلام مع إضافة اسم الكاتب
def text_to_speech(text, author, index):
    full_text = f"{text} - {author}"
    response = client.text_to_speech.convert(
        voice_id="N2lVS1w4EtoT3dr4eOWO",
        text=full_text,
        model_id="eleven_multilingual_v1",
        voice_settings=VoiceSettings(
            stability=0.0,
            similarity_boost=1.0,
            style=0.0,
            use_speaker_boost=False,
            language="arabic"
        ),
        output_format="mp3_22050_32",
    )
    # حفظ الملف الصوتي
    voice_file_name = os.path.join(output_folder, f"voice_{index}.mp3")
    with open(voice_file_name, "wb") as f:
        for chunk in response:
            if chunk:
                f.write(chunk)
    return voice_file_name

# تعديل حجم الصورة وإضافة تأثير الضبابية باستخدام Pillow
def resize_and_blur_image(image_path, width=1280, blur_radius=2, vertical=False):
    with Image.open(image_path) as img:
        if vertical:
            base_height = width
            aspect_ratio = img.width / img.height
            new_width = int(base_height * aspect_ratio)
            resized_image = img.resize((new_width, base_height), Image.Resampling.LANCZOS)
        else:
            aspect_ratio = img.height / img.width
            new_height = int(width * aspect_ratio)
            resized_image = img.resize((width, new_height), Image.Resampling.LANCZOS)
        
        blurred_image = resized_image.filter(ImageFilter.GaussianBlur(blur_radius))
        blurred_image_path = os.path.join(output_folder, "blurred_" + os.path.basename(image_path))
        blurred_image.save(blurred_image_path)
        return blurred_image_path

# إنشاء فيديو لكل حكمة
def create_video_clip(quote, author, image_path, index, vertical):
    voice_file_name = text_to_speech(quote, author, index)
    
    # تعديل حجم الصورة وضبط مسار الصورة الجديدة
    blurred_image_path = resize_and_blur_image(image_path, vertical=vertical)
    
    # حساب مدة الفويس أوفر
    voice_over_audio_clip = AudioFileClip(voice_file_name)
    voice_duration = voice_over_audio_clip.duration
    
    # إنشاء كليب الصورة
    image_clip = ImageClip(blurred_image_path).set_duration(voice_duration)  # مدة الصورة تساوي مدة الفويس أوفر
    
    # إعداد كليب النص
    fontsize = 30 if vertical else 40  # تصغير حجم الخط إذا كان الفيديو عمودي
    text = f"{quote} \n \n {author}"
    text_clip = TextClip(text, fontsize=fontsize, color='white', bg_color='transparent', size=image_clip.size)
    text_clip = text_clip.set_duration(voice_duration).set_position('center')
    
    # إضافة حركة بصرية بسيطة للنص
    text_clip = text_clip.crossfadein(1).crossfadeout(1)
    
    # إضافة الصوت والنص إلى الصورة
    final_clip = CompositeVideoClip([image_clip.set_audio(voice_over_audio_clip), text_clip])
    
    return final_clip

# إنشاء الفيديو النهائي بدمج عدة فيديوهات صغيرة
def create_final_video(quotes, image_paths, sound_effect_path, vertical=False):
    clips = []
    for i, (quote, author) in enumerate(quotes):
        clip = create_video_clip(quote, author, image_paths[i], i, vertical)
        clip = clip.fadein(1).fadeout(1)  # إضافة تأثيرات التلاشي
        clips.append(clip)

    # دمج الفيديوهات مع انتقالات سلسة
    final_video = concatenate_videoclips(clips, method="compose")

    # إضافة المؤثر الصوتي المستمر طوال الفيديو
    sound_effect_audio_clip = AudioFileClip(sound_effect_path).subclip(0, final_video.duration)

    # دمج الصوت النهائي مع الفيديو النهائي
    final_video = final_video.set_audio(CompositeAudioClip([final_video.audio, sound_effect_audio_clip]))

    # تصدير الفيديو إلى مسار محدد
    output_video_path = os.path.join(output_folder, 'output_video.mp4')
    final_video.write_videofile(output_video_path, codec='libx264', fps=24)

    # إغلاق الكليبات لتحرير الموارد
    for clip in clips:
        clip.close()

    sound_effect_audio_clip.close()

    return output_video_path

# وظيفة التعامل مع الأوامر
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        'مرحباً! لاختيار نوع الفيديو، استخدم الأمر /set_orientation [عمودي/أفقي]. \n'
        'ثم استخدم الأمر /send_images لإرسال الصور. \n'
        'وبعدها استخدم الأمر /send_audio لإرسال المقطع الصوتي. \n'
        'أخيرًا، استخدم الأمر /create_video لإنشاء الفيديو.'
    )

# وظيفة تحديد نوع الفيديو
async def set_orientation(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"image_paths": [], "sound_effect_path": None, "video_orientation": 'horizontal'}
    
    if context.args:
        option = context.args[0].strip().lower()
        if option == "عمودي":
            user_data[user_id]["video_orientation"] = 'vertical'
            await update.message.reply_text("تم تحديد نوع الفيديو: عمودي.")
        elif option == "أفقي":
            user_data[user_id]["video_orientation"] = 'horizontal'
            await update.message.reply_text("تم تحديد نوع الفيديو: أفقي.")
        else:
            await update.message.reply_text("خيار غير صحيح. يرجى اختيار 'عمودي' أو 'أفقي'.")
    else:
        await update.message.reply_text("يرجى تحديد نوع الفيديو: عمودي أو أفقي.")

# وظيفة طلب إرسال الصور
async def send_images(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("يرجى إرسال الصور (jpg, jpeg, png).")

# وظيفة التعامل مع استلام الصور
async def handle_images(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"image_paths": [], "sound_effect_path": None, "video_orientation": 'horizontal'}
    
    media_files = update.message.photo[-1]
    file_id = media_files.file_id
    file = await context.bot.get_file(file_id)

    # حفظ الصور
    image_path = os.path.join(image_folder, f'{user_id}_{file_id}.jpg')
    await file.download_to_drive(image_path)
    user_data[user_id]["image_paths"].append(image_path)
    await update.message.reply_text(f"تم استلام الصورة: {file_id}")

# وظيفة طلب إرسال المقطع الصوتي
async def send_audio(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("يرجى إرسال المقطع الصوتي (mp3).")

# وظيفة التعامل مع استلام المقطع الصوتي
async def handle_audio(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"image_paths": [], "sound_effect_path": None, "video_orientation": 'horizontal'}
    
    media_files = update.message.audio or update.message.voice
    file_id = media_files.file_id
    file = await context.bot.get_file(file_id)

    # حفظ المقطع الصوتي
    sound_effect_path = os.path.join(sound_effect_folder, f'{user_id}_{file_id}.mp3')
    await file.download_to_drive(sound_effect_path)
    user_data[user_id]["sound_effect_path"] = sound_effect_path
    await update.message.reply_text(f"تم استلام المقطع الصوتي: {file_id}")

# وظيفة إنشاء الفيديو
async def create_video(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        await update.message.reply_text("لم يتم استلام أي بيانات. يرجى إرسال الصور والمقطع الصوتي أولاً.")
        return
    
    image_paths = user_data[user_id]["image_paths"]
    sound_effect_path = user_data[user_id]["sound_effect_path"]
    video_orientation = user_data[user_id]["video_orientation"]

    if not image_paths:
        await update.message.reply_text("لم يتم استلام أي صور. يرجى إرسال الصور أولاً باستخدام الأمر /send_images.")
        return
    if not sound_effect_path:
        await update.message.reply_text("لم يتم استلام أي مقطع صوتي. يرجى إرسال المقطع الصوتي باستخدام الأمر /send_audio.")
        return

    await update.message.reply_text("الفيديو تحت الإنشاء، يرجى الانتظار...")
    try:
        # اختيار عدد الحكم بناءً على عدد الصور المستلمة
        quotes_count = len(image_paths)
        random_indices = random.sample(range(len(dataset["train"])), quotes_count)
        quotes = [(dataset["train"][i]["quote"], dataset["train"][i]["author"]) for i in random_indices]

        # تحديد ما إذا كان الفيديو عمودي
        vertical = video_orientation == 'vertical'

        # إنشاء الفيديو
        output_video_path = create_final_video(quotes, image_paths, sound_effect_path, vertical=vertical)

        # إرسال الفيديو الناتج
        with open(output_video_path, 'rb') as video_file:
            await context.bot.send_video(chat_id=update.effective_chat.id, video=video_file)
        await update.message.reply_text("تم إنشاء الفيديو بنجاح!")

        # مسح الملفات المؤقتة
        for image_path in image_paths:
            os.remove(image_path)
        os.remove(sound_effect_path)
        os.remove(output_video_path)

        # إعادة تعيين القوائم للمرة القادمة
        user_data[user_id] = {"image_paths": [], "sound_effect_path": None, "video_orientation": 'horizontal'}
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء إنشاء الفيديو: {e}")

# إضافة الهاندلرز (معالجات الأحداث) إلى الموزع
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("set_orientation", set_orientation))
application.add_handler(CommandHandler("send_images", send_images))
application.add_handler(MessageHandler(filters.PHOTO, handle_images))
application.add_handler(CommandHandler("send_audio", send_audio))
application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
application.add_handler(CommandHandler("create_video", create_video))

# بدء تشغيل البوت
application.run_polling()
