import telebot
from telebot import types
import psycopg2
from psycopg2 import Error
from datetime import datetime, timedelta
import os
from functools import wraps

# region ----- Environment Variables -----

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")  
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")  

# endregion

bot = telebot.TeleBot(BOT_TOKEN) # type: ignore

user_sessions = {}

# region ----- Starting Methods -----

def check_login(chat_id):
    return user_sessions.get(chat_id, False)

def login_required(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if not check_login(message.chat.id):
            bot.send_message(message.chat.id, "Please log in first.")
            ask_for_username(message)
            return
        return func(message, *args, **kwargs)
    return wrapper

def get_db_connection():
    try:
        connection = psycopg2.connect(DB_URI)
        return connection
    except Error as e:
        print(f"Error connecting to database: {e}")
        return None

def create_tables():
    connection = get_db_connection()
    if connection is None:
        return
    try:
        cursor = connection.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gym (
                gym_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name varchar NOT NULL,
                location varchar NOT NULL,
                owner varchar NOT NULL,
                reputation_score integer DEFAULT 75 CHECK (reputation_score >= 0 AND reputation_score <= 100)
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fighter (
                fighter_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name varchar NOT NULL,
                nickname varchar,
                weight_class varchar NOT NULL,
                age integer NOT NULL CHECK (age > 0),
                nationality varchar,
                status varchar DEFAULT 'active' CHECK (status IN ('active', 'retired', 'suspended')),
                gym_id integer REFERENCES gym(gym_id) ON DELETE SET NULL
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trainer (
                trainer_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name varchar NOT NULL,
                specialty varchar NOT NULL,
                gym_id integer REFERENCES gym(gym_id) ON DELETE SET NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fighter_trainer (
                fighter_id integer REFERENCES fighter(fighter_id) ON DELETE CASCADE,
                trainer_id integer REFERENCES trainer(trainer_id) ON DELETE CASCADE,
                start_date date NOT NULL DEFAULT CURRENT_DATE,
                end_date date,
                PRIMARY KEY (fighter_id, trainer_id)
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS match_event (
                match_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                start_date timestamp NOT NULL,
                end_date timestamp,
                location varchar NOT NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                match_id integer REFERENCES match_event(match_id) ON DELETE CASCADE,
                fighter_id integer REFERENCES fighter(fighter_id) ON DELETE CASCADE,
                result varchar CHECK (result IN ('win', 'loss', 'draw', 'no contest')),
                PRIMARY KEY (match_id, fighter_id)
            );
        """)
        
        connection.commit()
        print("Tables created successfully.")
        cursor.close()
    except Error as e:
        print(f"Error creating tables: {e}")
    finally:
        if connection:
            connection.close()

def translate_to_english(text):
    arabic_numbers = '٠١٢٣٤٥٦٧٨٩'
    persian_numbers = '۰١٢٣٤٥٦٧٨٩'
    english_numbers = '0123456789'
    
    translation_table = str.maketrans(persian_numbers + arabic_numbers, english_numbers * 2)
    return text.translate(translation_table)

def login_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    button = types.KeyboardButton('ورود به سیستم')
    markup.add(button)
    return markup

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    button1 = types.KeyboardButton('نمایش مبارزین')
    button2 = types.KeyboardButton('نمایش باشگاه‌ها')
    button3 = types.KeyboardButton('نمایش مربی‌ها')
    button4 = types.KeyboardButton('نمایش رویدادها')
    button5 = types.KeyboardButton('اضافه کردن مبارز')
    button6 = types.KeyboardButton('اضافه کردن باشگاه')
    button7 = types.KeyboardButton('اضافه کردن مربی')
    button8 = types.KeyboardButton('جست‌وجوی مبارز')
    button9 = types.KeyboardButton('جست‌وجوی باشگاه')
    button10 = types.KeyboardButton('جست‌وجوی مربی')
    button11 = types.KeyboardButton('اضافه کردن رویداد')
    button12 = types.KeyboardButton('ویرایش مبارز')
    button13 = types.KeyboardButton('ویرایش باشگاه')
    button14 = types.KeyboardButton('ویرایش مربی')
    button15 = types.KeyboardButton('ویرایش رویداد')
    button16 = types.KeyboardButton('خروج از سیستم')

    markup.add(button1, button2, button3, button4, button5, button6, button7, button8, button9, button10, button11, button12, button13, button14, button15, button16)
    return markup

def search_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    button1 = types.KeyboardButton('جست‌وجو با نام')
    button2 = types.KeyboardButton('بازگشت به منوی اصلی')
    markup.add(button1, button2)
    return markup

@bot.message_handler(commands=['start', 'login'])
def start_command(message):
    chat_id = message.chat.id
    
    if check_login(chat_id):
        send_welcome(message)
        return
    
    welcome_text = """
به ربات مدیریت باشگاه مبارزات خوش آمدید!
لطفا ابتدا وارد شوید.
"""
    bot.send_message(chat_id, welcome_text, reply_markup=login_menu())

@bot.message_handler(func=lambda message: message.text == 'ورود به سیستم')
def ask_for_username(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "نام کاربری خود را وارد کنید:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_username)

def process_username(message):
    chat_id = message.chat.id
    username = message.text.strip()
    
    if 'temp_data' not in user_sessions:
        user_sessions['temp_data'] = {}
    user_sessions['temp_data'][chat_id] = {'username': username}
    
    msg = bot.send_message(chat_id, "رمز عبور را وارد کنید:")
    bot.register_next_step_handler(msg, process_password, username)

def process_password(message, username):
    chat_id = message.chat.id
    password = message.text.strip()
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        user_sessions[chat_id] = True
        bot.send_message(chat_id, "ورود موفقیت‌آمیز بود!")
        send_welcome(message)
    else:
        bot.send_message(chat_id, "نام کاربری یا رمز عبور اشتباه است.")
        ask_for_username(message)

@bot.message_handler(func=lambda message: message.text == 'خروج از سیستم')
@login_required
def logout_command(message):
    chat_id = message.chat.id
    if chat_id in user_sessions:
        del user_sessions[chat_id]
    
    if 'temp_data' in user_sessions and chat_id in user_sessions['temp_data']:
        del user_sessions['temp_data'][chat_id]
    
    bot.send_message(chat_id, "خروج موفقیت‌آمیز بود!", reply_markup=login_menu())

@bot.message_handler(commands=['menu', 'help'])
@login_required
def send_welcome(message):
    chat_id = message.chat.id
    welcome_text = """
به ربات مدیریت باشگاه مبارزات خوش آمدید!
لطفاً یکی از گزینه‌ها را انتخاب کنید.
"""
    bot.send_message(chat_id, welcome_text, reply_markup=main_menu())

# region ----- View Handlers -----

@bot.message_handler(func=lambda message: message.text == 'نمایش مبارزین')
@login_required
def show_fighters(message):
    conn = get_db_connection()
    if conn is None:
        bot.send_message(message.chat.id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT fighter_id, name, nickname, weight_class, age, nationality, status
            FROM fighter
            ORDER BY name
            LIMIT 50
        """)
        fighters = cur.fetchall()
        
        if not fighters:
            bot.send_message(message.chat.id, "هیچ مبارزی در باشگاه ثبت نشده است.")
            return

        response = "لیست مبارزین:\n\n"
        for fighter in fighters:
            response += f"{fighter[1]}\n"
            response += f"شناسه مبارز: {fighter[0]}\n"
            response += f"نام مستعار: {fighter[2] or 'ثبت نشده'}\n"
            response += f"رده وزنی: {fighter[3]}\n"
            response += f"سن: {fighter[4]}\n"
            response += f"ملیت: {fighter[5]}\n"
            response += f"وضعیت: {fighter[6]}\n"
            response += "-" * 30 + "\n"

        bot.send_message(message.chat.id, response, parse_mode='Markdown')
        cur.close()
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در دریافت اطلاعات: {e}")
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'نمایش باشگاه‌ها')
@login_required
def show_gyms(message):
    conn = get_db_connection()
    if conn is None:
        bot.send_message(message.chat.id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT gym_id, name, location, owner, reputation_score
            FROM gym
            ORDER BY name
            LIMIT 50
        """)
        gyms = cur.fetchall()
        
        if not gyms:
            bot.send_message(message.chat.id, "هیچ باشگاهی ثبت نشده است.")
            return
        
        response = "لیست باشگاه‌ها:\n\n"
        for gym in gyms:
            response += f"{gym[1]}\n"
            response += f"شناسه باشگاه: {gym[0]}\n"
            response += f"مکان: {gym[2]}\n"
            response += f"مالک: {gym[3]}\n"
            response += f"امتیاز شهرت: {gym[4]}\n"
            response += "-" * 30 + "\n"
        
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
        cur.close()
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در دریافت اطلاعات: {e}")
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'نمایش مربی‌ها')
@login_required
def show_trainers(message):
    conn = get_db_connection()
    if conn is None:
        bot.send_message(message.chat.id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.trainer_id, t.name as trainer_name, t.specialty, g.name as gym_name
            FROM trainer t
            LEFT JOIN gym g ON t.gym_id = g.gym_id
            ORDER BY t.name
            LIMIT 50
        """)
        trainers = cur.fetchall()
        
        if not trainers:
            bot.send_message(message.chat.id, "هیچ مربی‌ای ثبت نشده است.")
            return

        response = "لیست مربی‌ها:\n\n"
        for trainer in trainers:
            response += f"{trainer[1]}\n"
            response += f"شناسه مربی: {trainer[0]}\n"
            response += f"تخصص: {trainer[2]}\n"
            response += f"باشگاه: {trainer[3] or 'ثبت نشده'}\n"
            response += "-" * 30 + "\n"
        
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
        cur.close()
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در دریافت اطلاعات: {e}")
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'نمایش رویدادها')
@login_required
def show_events(message):
    conn = get_db_connection()
    if conn is None:
        bot.send_message(message.chat.id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT me.match_id, me.start_date, me.location, 
                   STRING_AGG(CONCAT(f.name, ' (', p.result, ')'), ' vs ') as participants
            FROM match_event me
            LEFT JOIN participants p ON me.match_id = p.match_id
            LEFT JOIN fighter f ON p.fighter_id = f.fighter_id
            GROUP BY me.match_id, me.start_date, me.location
            ORDER BY me.start_date DESC
            LIMIT 50
        """)
        events = cur.fetchall()
        
        if not events:
            bot.send_message(message.chat.id, "هیچ رویدادی ثبت نشده است.")
            return

        response = "آخرین رویدادها:\n\n"
        for event in events:
            response += f"🔹 **رویداد #{event[0]}**\n"
            response += f"📅 تاریخ: {event[1].strftime('%Y-%m-%d %H:%M')}\n"
            response += f"📍 مکان: {event[2]}\n"
            response += f"🥊 مبارزین: {event[3]}\n"
            response += "-" * 30 + "\n"
        
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
        cur.close()
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در دریافت اطلاعات: {e}")
    finally:
        if conn:
            conn.close()

# endregion

def get_gym_id_by_name(gym_name):
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT gym_id FROM gym WHERE name = %s;",
            (gym_name,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except Error as e:
        print(f"DB error: {e}")
        return None
    finally:
        cursor.close() # type: ignore
        connection.close()

def cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("لغو عملیات"))
    return markup

@bot.message_handler(func=lambda m: m.text == "لغو عملیات")
def cancel_process(message):
    chat_id = message.chat.id

    bot.clear_step_handler_by_chat_id(chat_id)
    bot.send_message(chat_id, "عملیات لغو شد.", reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == 'اضافه کردن مبارز')
@login_required
def add_fighter_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام مبارز جدید را وارد کنید:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(msg, process_fighter_name)

def process_fighter_name(message):
    chat_id = message.chat.id
    full_name = message.text.strip()

    if full_name == "لغو عملیات":
        cancel_process(message)
        return
    
    if not full_name or len(full_name) < 2:
        msg = bot.send_message(chat_id, "نام وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_gym_name)
        return
    
    msg = bot.send_message(chat_id, "لطفاً نام مستعار مبارز را وارد کنید (اختیاری):")
    bot.register_next_step_handler(msg, process_fighter_nickname, full_name)

def process_fighter_nickname(message, full_name):
    chat_id = message.chat.id
    nickname = message.text.strip() if message.text else None

    if nickname == "لغو عملیات":
        cancel_process(message)
        return

    if nickname == "اختیاری" or nickname == "ندارد" or nickname == "خالی":
        nickname = None

    msg = bot.send_message(chat_id, "لطفاً رده وزنی مبارز را وارد کنید:")
    bot.register_next_step_handler(msg, process_fighter_weight_class, full_name, nickname)

def process_fighter_weight_class(message, full_name, nickname):
    chat_id = message.chat.id
    weight_class = message.text.strip()

    if weight_class == "لغو عملیات":
        cancel_process(message)
        return

    if not weight_class:
        msg = bot.send_message(chat_id, "رده وزنی وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_gym_location, full_name, nickname)
        return

    msg = bot.send_message(chat_id, "لطفاً سن مبارز را وارد کنید:")
    bot.register_next_step_handler(msg, process_fighter_age, full_name, nickname, weight_class)

def process_fighter_age(message, full_name, nickname, weight_class):
    chat_id = message.chat.id
    age = message.text.strip()
    age = translate_to_english(age)

    if age == "لغو عملیات":
        cancel_process(message)
        return

    if not age.isdigit() or int(age) <= 0 or not age:
        msg = bot.send_message(chat_id, "سن وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_gym_owner, full_name, nickname, weight_class)
        return

    msg = bot.send_message(chat_id, "لطفاً ملیت مبارز را وارد کنید:")
    bot.register_next_step_handler(msg, process_fighter_nationality, full_name, nickname, weight_class, age)

def process_fighter_nationality(message, full_name, nickname, weight_class, age):
    chat_id = message.chat.id
    nationality = message.text.strip() if message.text else None

    msg = bot.send_message(chat_id, "لطفاً نام باشگاه مبارز را وارد کنید:")
    bot.register_next_step_handler(msg, process_fighter_gym, full_name, nickname, weight_class, age, nationality)

def process_fighter_gym(message, full_name, nickname, weight_class, age, nationality):
    chat_id = message.chat.id
    gym_name = message.text.strip() if message.text else None

    if not gym_name:
        msg = bot.send_message(chat_id, "نام وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید:")
        reply_markup = cancel_keyboard()
        bot.register_next_step_handler(msg, process_fighter_gym, full_name, nickname, weight_class, age, nationality)
        return
    
    gym_id = get_gym_id_by_name(gym_name)

    if gym_id is None:
        msg = bot.send_message(chat_id, "چنین باشگاهی ثبت نشده است. لطفاً نام باشگاه را مجدداً وارد کنید:")
        reply_markup = cancel_keyboard()
        bot.register_next_step_handler(msg, process_fighter_gym, full_name, nickname, weight_class, age, nationality)
        return
    else:
        conn = get_db_connection()
        if conn is None:
            bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
            return
        
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO fighter (name, nickname, weight_class, age, nationality, gym_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING fighter_id
            """, (full_name, nickname, weight_class, age, nationality, gym_id))

            fighter_id = cur.fetchone()[0] # type: ignore
            conn.commit()

            bot.send_message(chat_id, f"مبارز جدید با موفقیت ثبت شد!\nشناسه مبارز: {fighter_id}", reply_markup=main_menu())
            cur.close()
        except Error as e:
            bot.send_message(chat_id, f"خطا در ثبت مبارز:\n{e}", reply_markup=main_menu())
        finally:
            if conn:
                conn.close()

# ------------------------------ ADD GYM HANDLER ------------------------------

@bot.message_handler(func=lambda message: message.text == 'اضافه کردن باشگاه')
@login_required
def add_gym_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام باشگاه را وارد کنید:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(msg, process_gym_name)

def process_gym_name(message):
    chat_id = message.chat.id
    full_name = message.text.strip()

    if full_name == "لغو عملیات":
        cancel_process(message)
        return
    
    if not full_name or len(full_name) < 2:
        msg = bot.send_message(chat_id, "نام وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_gym_name)
        return

    msg = bot.send_message(chat_id, "لطفاً مکان باشگاه را وارد کنید:")
    bot.register_next_step_handler(msg, process_gym_location, full_name)

def process_gym_location(message, full_name):
    chat_id = message.chat.id
    location = message.text.strip()

    if location == "لغو عملیات":
        cancel_process(message)
        return

    if not location:
        msg = bot.send_message(chat_id, "مکان وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_gym_location, full_name)
        return

    msg = bot.send_message(chat_id, "لطفاً نام صاحب باشگاه را وارد کنید:")
    bot.register_next_step_handler(msg, process_gym_owner, full_name, location)

def process_gym_owner(message, full_name, location):
    chat_id = message.chat.id
    owner = message.text.strip()

    if owner == "لغو عملیات":
        cancel_process(message)
        return
    
    if not owner or len(owner) < 2:
        msg = bot.send_message(chat_id, "نام وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_gym_name)
        return

    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO gym (name, location, owner)
            VALUES (%s, %s, %s)
            RETURNING gym_id
        """, (full_name, location, owner))

        gym_id = cur.fetchone()[0] # type: ignore
        conn.commit()

        bot.send_message(chat_id, f"باشگاه جدید با موفقیت ثبت شد!\nشناسه باشگاه: {gym_id}", reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در ثبت باشگاه:\n{e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'اضافه کردن مربی')
@login_required
def add_trainer_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام مربی را وارد کنید:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(msg, process_trainer_name)

def process_trainer_name(message):
    chat_id = message.chat.id
    full_name = message.text.strip()

    if full_name == "لغو عملیات":
        cancel_process(message)
        return
    
    if not full_name or len(full_name) < 2:
        msg = bot.send_message(chat_id, "نام وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_trainer_name)
        return

    msg = bot.send_message(chat_id, "لطفاً تخصص مربی را وارد کنید:")
    bot.register_next_step_handler(msg, process_trainer_specialty, full_name)

def process_trainer_specialty(message, full_name):
    chat_id = message.chat.id
    specialty = message.text.strip()

    if specialty == "لغو عملیات":
        cancel_process(message)
        return

    if not specialty:
        msg = bot.send_message(chat_id, "تخصص وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_trainer_specialty, full_name)
        return

    msg = bot.send_message(chat_id, "لطفاً نام باشگاه مربی را وارد کنید:")
    bot.register_next_step_handler(msg, process_trainer_gym, full_name, specialty)

def process_trainer_gym(message, full_name, specialty):
    chat_id = message.chat.id
    gym_name = message.text.strip() if message.text else None

    if not gym_name:
        msg = bot.send_message(chat_id, "نام وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید:")
        reply_markup = cancel_keyboard()
        bot.register_next_step_handler(msg, process_trainer_gym, full_name, specialty)
        return
    
    gym_id = get_gym_id_by_name(gym_name)

    if gym_id is None:
        msg = bot.send_message(chat_id, "چنین باشگاهی ثبت نشده است. لطفاً نام باشگاه را مجدداً وارد کنید:")
        reply_markup = cancel_keyboard()
        bot.register_next_step_handler(msg, process_trainer_gym, full_name, specialty)
        return
    else:
        conn = get_db_connection()
        if conn is None:
            bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
            return
        
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO trainer (name, specialty, gym_id)
                VALUES (%s, %s, %s)
                RETURNING trainer_id
            """, (full_name, specialty, gym_id))

            trainer_id = cur.fetchone()[0] # type: ignore
            conn.commit()

            bot.send_message(chat_id, f"مربی جدید با موفقیت ثبت شد!\nشناسه مربی: {trainer_id}", reply_markup=main_menu())
            cur.close()
        except Error as e:
            bot.send_message(chat_id, f"خطا در ثبت مبارز:\n{e}", reply_markup=main_menu())
        finally:
            if conn:
                conn.close()

@bot.message_handler(func=lambda message: message.text == 'جست‌وجوی مبارز')
@login_required
def search_fighter_menu(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام مبارز را برای جست‌وجو وارد کنید:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(msg, process_fighter_search)

def process_fighter_search(message):
    chat_id = message.chat.id
    search_term = message.text.strip()
    
    if search_term == "لغو عملیات":
        cancel_process(message)
        return
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT f.fighter_id, f.name, f.nickname, f.weight_class, f.age, 
                   f.nationality, f.status, g.name as gym_name
            FROM fighter f
            LEFT JOIN gym g ON f.gym_id = g.gym_id
            WHERE f.name ILIKE %s OR f.nickname ILIKE %s
            ORDER BY f.name
        """, (f'%{search_term}%', f'%{search_term}%'))
        
        fighters = cur.fetchall()
        
        if not fighters:
            bot.send_message(chat_id, f"هیچ مبارزی با نام یا نام مستعار '{search_term}' یافت نشد.", reply_markup=main_menu())
            return
        
        response = f"نتایج جست‌وجو برای '{search_term}':\n\n"
        for fighter in fighters:
            response += f"**{fighter[1]}**\n"
            response += f"شناسه مبارز: {fighter[0]}\n"
            response += f"نام مستعار: {fighter[2] or 'ثبت نشده'}\n"
            response += f"رده وزنی: {fighter[3]}\n"
            response += f"سن: {fighter[4]}\n"
            response += f"ملیت: {fighter[5]}\n"
            response += f"وضعیت: {fighter[6]}\n"
            response += f"باشگاه: {fighter[7] or 'ثبت نشده'}\n"
            response += "-" * 30 + "\n"
        
        bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در جست‌وجو: {e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'جست‌وجوی باشگاه')
@login_required
def search_gym_menu(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام باشگاه یا مکان باشگاه یا نام مالک را برای جست‌وجو وارد کنید:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(msg, process_gym_search)

def process_gym_search(message):
    chat_id = message.chat.id
    search_term = message.text.strip()
    
    if search_term == "لغو عملیات":
        cancel_process(message)
        return
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT gym_id, name, location, owner, reputation_score
            FROM gym
            WHERE name ILIKE %s OR location ILIKE %s OR owner ILIKE %s
            ORDER BY name
        """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        
        gyms = cur.fetchall()
        
        if not gyms:
            bot.send_message(chat_id, f"هیچ باشگاهی با این نام یا این مکان یا این مالک '{search_term}' یافت نشد.", reply_markup=main_menu())
            return
        
        response = f"نتایج جست‌وجو برای '{search_term}':\n\n"
        for gym in gyms:
            response += f"**{gym[1]}**\n"
            response += f"شناسه باشگاه: {gym[0]}\n"
            response += f"مکان: {gym[2]}\n"
            response += f"مالک: {gym[3]}\n"
            response += f"امتیاز شهرت: {gym[4]}\n"
            
            cur.execute("""
                SELECT COUNT(*) FROM fighter WHERE gym_id = %s
            """, (gym[0],))
            fighter_count = cur.fetchone()[0] # type: ignore
            
            cur.execute("""
                SELECT COUNT(*) FROM trainer WHERE gym_id = %s
            """, (gym[0],))
            trainer_count = cur.fetchone()[0] # type: ignore
            
            response += f"تعداد مبارزین: {fighter_count}\n"
            response += f"تعداد مربیان: {trainer_count}\n"
            response += "-" * 30 + "\n"
        
        bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در جست‌وجو: {e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'جست‌وجوی مربی')
@login_required
def search_trainer_menu(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام مربی یا نام تخصص را برای جست‌وجو وارد کنید:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(msg, process_trainer_search)

def process_trainer_search(message):
    chat_id = message.chat.id
    search_term = message.text.strip()
    
    if search_term == "لغو عملیات":
        cancel_process(message)
        return
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.trainer_id, t.name, t.specialty, g.name as gym_name
            FROM trainer t
            LEFT JOIN gym g ON t.gym_id = g.gym_id
            WHERE t.name ILIKE %s OR t.specialty ILIKE %s
            ORDER BY t.name
        """, (f'%{search_term}%', f'%{search_term}%'))
        
        trainers = cur.fetchall()
        
        if not trainers:
            bot.send_message(chat_id, f"هیچ مربی‌ای با این نام یا این تخصص '{search_term}' یافت نشد.", reply_markup=main_menu())
            return
        
        response = f"نتایج جست‌وجو برای '{search_term}':\n\n"
        for trainer in trainers:
            response += f"**{trainer[1]}**\n"
            response += f"شناسه مربی: {trainer[0]}\n"
            response += f"تخصص: {trainer[2]}\n"
            response += f"باشگاه: {trainer[3] or 'ثبت نشده'}\n"
            
            cur.execute("""
                SELECT COUNT(*) FROM fighter_trainer WHERE trainer_id = %s
            """, (trainer[0],))
            fighter_count = cur.fetchone()[0] # type: ignore
            
            response += f"تعداد شاگردان: {fighter_count}\n"
            response += "-" * 30 + "\n"
        
        bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در جست‌وجو: {e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

def get_fighter_id_by_name(fighter_name):
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT fighter_id FROM fighter WHERE name = %s;",
            (fighter_name,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except Error as e:
        print(f"DB error: {e}")
        return None
    finally:
        cursor.close() # type: ignore
        connection.close()

@bot.message_handler(func=lambda message: message.text == 'اضافه کردن رویداد')
@login_required
def add_event_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً تاریخ و زمان شروع رویداد را وارد کنید (فرمت: YYYY-MM-DD HH:MM):", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(msg, process_event_start_date)

def process_event_start_date(message):
    chat_id = message.chat.id
    start_date_str = message.text.strip()
    
    if start_date_str == "لغو عملیات":
        cancel_process(message)
        return
    
    try:
        # Parse the date
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M")
        
        msg = bot.send_message(chat_id, "لطفاً مکان رویداد را وارد کنید:")
        bot.register_next_step_handler(msg, process_event_location, start_date)
    except ValueError:
        msg = bot.send_message(chat_id, "فرمت تاریخ اشتباه است. لطفاً مجدداً وارد کنید (فرمت: YYYY-MM-DD HH:MM):")
        bot.register_next_step_handler(msg, process_event_start_date)

def process_event_location(message, start_date):
    chat_id = message.chat.id
    location = message.text.strip()
    
    if location == "لغو عملیات":
        cancel_process(message)
        return
    
    if not location:
        msg = bot.send_message(chat_id, "مکان وارد شده معتبر نیست. لطفاً مجدداً وارد کنید:")
        bot.register_next_step_handler(msg, process_event_location)
        return
    
    msg = bot.send_message(chat_id, "لطفاً نام مبارز اول را وارد کنید:")
    bot.register_next_step_handler(msg, process_event_fighter1, start_date, location)

def process_event_fighter1(message, start_date, location):
    chat_id = message.chat.id
    fighter1_name = message.text.strip()
    
    if fighter1_name == "لغو عملیات":
        cancel_process(message)
        return
    
    fighter1_id = get_fighter_id_by_name(fighter1_name)
    
    if fighter1_id is None:
        msg = bot.send_message(chat_id, "مبارز یافت نشد. لطفاً نام را مجدداً وارد کنید:")
        bot.register_next_step_handler(msg, process_event_fighter1, start_date, location)
        return
    
    msg = bot.send_message(chat_id, "لطفاً نام مبارز دوم را وارد کنید:")
    bot.register_next_step_handler(msg, process_event_fighter2, start_date, location, fighter1_id, fighter1_name)

def process_event_fighter2(message, start_date, location, fighter1_id, fighter1_name):
    chat_id = message.chat.id
    fighter2_name = message.text.strip()
    
    if fighter2_name == "لغو عملیات":
        cancel_process(message)
        return
    
    fighter2_id = get_fighter_id_by_name(fighter2_name)
    
    if fighter2_id is None:
        msg = bot.send_message(chat_id, "مبارز یافت نشد. لطفاً نام را مجدداً وارد کنید:")
        bot.register_next_step_handler(msg, process_event_fighter2, start_date, location, fighter1_id, fighter1_name)
        return
    
    # Check if same fighter
    if fighter2_id == fighter1_id:
        msg = bot.send_message(chat_id, "یک مبارز نمی‌تواند با خودش مبارزه کند! لطفاً مبارز دیگری را وارد کنید:")
        bot.register_next_step_handler(msg, process_event_fighter2, start_date, location, fighter1_id, fighter1_name)
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("برد مبارز اول"), 
               types.KeyboardButton("برد مبارز دوم"),
               types.KeyboardButton("مساوی"),
               types.KeyboardButton("لغو شده"),
               types.KeyboardButton("نامعلوم"),
               types.KeyboardButton("لغو عملیات"))
    
    msg = bot.send_message(chat_id, "نتیجه مبارزه را انتخاب کنید:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_event_result, start_date, location, fighter1_id, fighter1_name, fighter2_id, fighter2_name)

def process_event_result(message, start_date, location, fighter1_id, fighter1_name, fighter2_id, fighter2_name):
    chat_id = message.chat.id
    result_text = message.text.strip()
    
    if result_text == "لغو عملیات":
        cancel_process(message)
        return
    
    result_map = {
        "برد مبارز اول": "win",
        "برد مبارز دوم": "win",
        "مساوی": "draw",
        "لغو شده": "no contest",
        "نامعلوم": None
    }
    
    if result_text not in result_map:
        msg = bot.send_message(chat_id, "نتیجه نامعتبر است. لطفاً از گزینه‌ها انتخاب کنید:")
        bot.register_next_step_handler(msg, process_event_result)
        return
    
    result = result_map[result_text]
        
    if result_text == "برد مبارز اول":
        fighter1_result = "win"
        fighter2_result = "loss"
    elif result_text == "برد مبارز دوم":
        fighter1_result = "loss"
        fighter2_result = "win"
    elif result_text == "مساوی" or result_text == "لغو شده" or result_text == "نامعلوم":
        fighter1_result = result
        fighter2_result = result
    else:
        fighter1_result = None
        fighter2_result = None
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.", reply_markup=main_menu())
        return
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO match_event (start_date, location)
            VALUES (%s, %s)
            RETURNING match_id
        """, (start_date, location))
        
        match_id = cur.fetchone()[0] # type: ignore
        
        cur.execute("""
            INSERT INTO participants (match_id, fighter_id, result)
            VALUES (%s, %s, %s)
        """, (match_id, fighter1_id, fighter1_result))
        
        cur.execute("""
            INSERT INTO participants (match_id, fighter_id, result)
            VALUES (%s, %s, %s)
        """, (match_id, fighter2_id, fighter2_result))
        
        conn.commit()
        
        result_display = ""
        if result_text == "برد مبارز اول":
            result_display = f"{fighter1_name} برنده شد"
        elif result_text == "برد مبارز دوم":
            result_display = f"{fighter2_name} برنده شد"
        else:
            result_display = result_text
        
        response = f"""
رویداد جدید با موفقیت ثبت شد!

**جزئیات رویداد:**
شناسه رویداد: {match_id}
تاریخ: {start_date.strftime('%Y-%m-%d %H:%M')}
مکان: {location}

**مبارزین:**
1. {fighter1_name}
2. {fighter2_name}

**نتیجه:** {result_display}
"""

        bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در ثبت رویداد:\n{e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'بازگشت به منوی اصلی')
@login_required
def back_to_main_menu(message):
    send_welcome(message)

if __name__ == '__main__':
    create_tables()
    print("Running...")

    bot.polling(none_stop=True)