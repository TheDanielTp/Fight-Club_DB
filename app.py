import telebot
from telebot import types
import psycopg2
from psycopg2 import Error
from datetime import datetime, timedelta
import os
from functools import wraps

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")  
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")  

bot = telebot.TeleBot(BOT_TOKEN) # type: ignore

user_sessions = {}

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
    button4 = types.KeyboardButton('اضافه کردن مبارز')
    button5 = types.KeyboardButton('اضافه کردن باشگاه')
    button6 = types.KeyboardButton('اضافه کردن مربی')
    button7 = types.KeyboardButton('جست‌وجوی مبارز')
    button8 = types.KeyboardButton('جست‌وجوی باشگاه')
    button9 = types.KeyboardButton('جست‌وجوی مربی')
    button10 = types.KeyboardButton('اضافه کردن رویداد')
    button11 = types.KeyboardButton('خروج از سیستم')

    markup.add(button1, button2, button3, button4, button5, button6, button7, button8, button9, button10, button11)
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
        """)
        fighters = cur.fetchall()
        
        if not fighters:
            bot.send_message(message.chat.id, "هیچ مبارزی در باشگاه ثبت نشده است.")
            return

        response = "لیست مبارزین:\n\n"
        for fighter in fighters:
            response += f"{fighter[1]}\n"
            response += f"شناسه مبارز: {fighter[0]}\n"
            response += f"لقب: {fighter[2] or 'ثبت نشده'}\n"
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
        cursor.close()
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
def add_member_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام مبارز جدید را وارد کنید:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(msg, process_fighter_name)

def process_fighter_name(message):
    chat_id = message.chat.id
    full_name = message.text.strip()

    if full_name == "لغو عملیات":
        cancel_process(message)
        return
    
    if not full_name or len(full_name) < 3:
        msg = bot.send_message(chat_id, "نام وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_fighter_name)
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
        bot.register_next_step_handler(msg, process_fighter_weight_class, full_name, nickname)
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
        bot.register_next_step_handler(msg, process_fighter_age, full_name, nickname, weight_class)
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

            fighter_id = cur.fetchone()[0]
            conn.commit()

            bot.send_message(chat_id, f"مبارز جدید با موفقیت ثبت شد!\nشناسه مبارز: {fighter_id}", reply_markup=main_menu())
            cur.close()
        except Error as e:
            bot.send_message(chat_id, f"خطا در ثبت مبارز:\n{e}", reply_markup=main_menu())
        finally:
            if conn:
                conn.close()

@bot.message_handler(func=lambda message: message.text == 'اضافه کردن کتاب')
@login_required
def add_book_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً عنوان کتاب را وارد کنید:")
    bot.register_next_step_handler(msg, process_book_title)

def process_book_title(message):
    chat_id = message.chat.id
    title = message.text.strip()
    
    if not title or len(title) < 2:
        bot.send_message(chat_id, "عنوان وارد شده معتبر نیست.")
        return
    
    msg = bot.send_message(chat_id, "لطفاً نام نویسنده را وارد کنید:")
    bot.register_next_step_handler(msg, process_book_author, title)

def process_book_author(message, title):
    chat_id = message.chat.id
    author = message.text.strip()
    
    if not author or len(author) < 2:
        bot.send_message(chat_id, "نام نویسنده معتبر نیست.")
        return
    
    msg = bot.send_message(chat_id, "لطفاً تعداد نسخه‌های کتاب را وارد کنید (پیش‌فرض: 1):")
    bot.register_next_step_handler(msg, process_book_copies, title, author)

def process_book_copies(message, title, author):
    chat_id = message.chat.id
    copies_text = message.text.strip()
    
    try:
        copies = int(copies_text) if copies_text else 1
        if copies < 1:
            copies = 1
    except:
        copies = 1
    
    msg = bot.send_message(chat_id, "لطفاً سال انتشار کتاب را وارد کنید (اختیاری):")
    bot.register_next_step_handler(msg, process_book_year, title, author, copies)

def process_book_year(message, title, author, copies):
    chat_id = message.chat.id
    year_text = message.text.strip()
    year = int(year_text) if year_text and year_text.isdigit() else None
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO books (title, author, total_copies, available_copies, publication_year)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (title, author, copies, copies, year))
        
        book_id = cur.fetchone()[0]
        conn.commit()
        
        bot.send_message(chat_id, f"کتاب جدید با موفقیت ثبت شد!\nکد کتاب: {book_id}")
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در ثبت کتاب: {e}")
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'امانت دادن کتاب')
@login_required
def borrow_book_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً کد کتاب را وارد کنید:")
    bot.register_next_step_handler(msg, process_borrow_book_id)

def process_borrow_book_id(message):
    chat_id = message.chat.id
    book_id = message.text.strip()
    
    if not book_id.isdigit():
        bot.send_message(chat_id, "کد کتاب باید عدد باشد.")
        return
    
    msg = bot.send_message(chat_id, "لطفاً کد عضو را وارد کنید:")
    bot.register_next_step_handler(msg, process_borrow_member_id, int(book_id))

def process_borrow_member_id(message, book_id):
    chat_id = message.chat.id
    member_id = message.text.strip()
    
    if not member_id.isdigit():
        bot.send_message(chat_id, "کد عضو باید عدد باشد.")
        return
    
    msg = bot.send_message(chat_id, "برای چند روز امانت داده شود؟ (پیش‌فرض: 14 روز)")
    bot.register_next_step_handler(msg, process_borrow_days, book_id, int(member_id))

def process_borrow_days(message, book_id, member_id):
    chat_id = message.chat.id
    days_text = message.text.strip()
    
    try:
        days = int(days_text) if days_text else 14
        if days < 1:
            days = 14
    except:
        days = 14
    
    due_date = datetime.now() + timedelta(days=days)
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT available_copies, title FROM books WHERE id = %s", (book_id,))
        book_info = cur.fetchone()
        
        if not book_info:
            bot.send_message(chat_id, "کتابی با این کد یافت نشد.")
            return
        
        if book_info[0] < 1:
            bot.send_message(chat_id, f"کتاب '{book_info[1]}' در حال حاضر موجود نیست.")
            return
        
        cur.execute("SELECT full_name FROM members WHERE id = %s AND is_active = TRUE", (member_id,))
        member_info = cur.fetchone()
        
        if not member_info:
            bot.send_message(chat_id, "عضوی با این کد یافت نشد یا غیرفعال است.")
            return
        
        cur.execute("""
            INSERT INTO borrowings (book_id, member_id, due_date)
            VALUES (%s, %s, %s)
        """, (book_id, member_id, due_date))
        
        cur.execute("""
            UPDATE books 
            SET available_copies = available_copies - 1 
            WHERE id = %s
        """, (book_id,))
        
        conn.commit()
        
        due_date_str = due_date.strftime('%Y-%m-%d')
        bot.send_message(chat_id, f"کتاب '{book_info[1]}' به '{member_info[0]}' امانت داده شد.\nموعد بازگشت: {due_date_str}")
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در ثبت امانت: {e}")
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'پس گرفتن کتاب')
@login_required
def return_book_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً کد کتاب را وارد کنید:")
    bot.register_next_step_handler(msg, process_return_book)

def process_return_book(message):
    chat_id = message.chat.id
    book_id = message.text.strip()
    
    if not book_id.isdigit():
        bot.send_message(chat_id, "کد کتاب باید عدد باشد.")
        return
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT b.id, bk.title, m.full_name 
            FROM borrowings b
            JOIN books bk ON b.book_id = bk.id
            JOIN members m ON b.member_id = m.id
            WHERE b.book_id = %s AND b.is_returned = FALSE
            ORDER BY b.borrow_date DESC LIMIT 1
        """, (int(book_id),))
        
        borrowing = cur.fetchone()
        
        if not borrowing:
            bot.send_message(chat_id, "هیچ امانت فعالی برای این کتاب یافت نشد.")
            return
        
        cur.execute("""
            UPDATE borrowings 
            SET is_returned = TRUE, return_date = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (borrowing[0],))
        
        cur.execute("""
            UPDATE books 
            SET available_copies = available_copies + 1 
            WHERE id = %s
        """, (int(book_id),))
        
        conn.commit()
        
        bot.send_message(chat_id, f"کتاب '{borrowing[1]}' از '{borrowing[2]}' پس گرفته شد.")
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در پس گرفتن کتاب: {e}")
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'جستجوی کتاب')
@login_required
def search_book_menu(message):
    bot.send_message(message.chat.id, "لطفاً نوع جستجو را انتخاب کنید:", 
                     reply_markup=search_menu())

@bot.message_handler(func=lambda message: message.text == 'جستجو با عنوان')
@login_required
def search_by_title_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً بخشی از عنوان کتاب را وارد کنید:")
    bot.register_next_step_handler(msg, search_by_title)

def search_by_title(message):
    chat_id = message.chat.id
    keyword = f"%{message.text.strip()}%"
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, author, available_copies 
            FROM books 
            WHERE title ILIKE %s 
            ORDER BY title
        """, (keyword,))
        
        books = cur.fetchall()
        
        if not books:
            bot.send_message(chat_id, "کتابی با این عنوان یافت نشد.")
            return
        
        response = f"نتایج جستجو برای '{message.text.strip()}':\n\n"
        for book in books:
            status = "موجود" if book[3] > 0 else "امانت"
            response += f"{book[1]}\n"
            response += f"نویسنده: {book[2]}\n"
            response += f"وضعیت: {status}\n"
            response += f"کد کتاب: {book[0]}\n"
            response += "-" * 30 + "\n"
        
        bot.send_message(chat_id, response, parse_mode='Markdown')
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در جستجو: {e}")
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'جستجو با نویسنده')
@login_required
def search_by_author_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام نویسنده را وارد کنید:")
    bot.register_next_step_handler(msg, search_by_author)

def search_by_author(message):
    chat_id = message.chat.id
    keyword = f"%{message.text.strip()}%"
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, author, available_copies 
            FROM books 
            WHERE author ILIKE %s 
            ORDER BY title
        """, (keyword,))
        
        books = cur.fetchall()
        
        if not books:
            bot.send_message(chat_id, "کتابی از این نویسنده یافت نشد.")
            return
        
        response = f"نتایج جستجو برای نویسنده '{message.text.strip()}':\n\n"
        for book in books:
            status = "موجود" if book[3] > 0 else "امانت"
            response += f"{book[1]}\n"
            response += f"نویسنده: {book[2]}\n"
            response += f"وضعیت: {status}\n"
            response += f"کد کتاب: {book[0]}\n"
            response += "-" * 30 + "\n"
        
        bot.send_message(chat_id, response, parse_mode='Markdown')
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در جستجو: {e}")
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'وضعیت کتاب‌های امانت‌رفته')
@login_required
def show_borrowed_books(message):
    conn = get_db_connection()
    if conn is None:
        bot.send_message(message.chat.id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                b.title,
                bk.author,
                m.full_name,
                br.borrow_date,
                br.due_date,
                CASE 
                    WHEN br.due_date < CURRENT_DATE THEN 'معوقه'
                    ELSE 'در امانت'
                END as status
            FROM borrowings br
            JOIN books b ON br.book_id = b.id
            JOIN members m ON br.member_id = m.id
            JOIN books bk ON br.book_id = bk.id
            WHERE br.is_returned = FALSE
            ORDER BY br.due_date
        """)
        
        borrowed = cur.fetchall()
        
        if not borrowed:
            bot.send_message(message.chat.id, "هیچ کتابی در حال حاضر امانت نیست.")
            return
        
        response = "کتاب‌های در حال امانت:\n\n"
        for item in borrowed:
            borrow_date = item[3].strftime('%Y-%m-%d')
            due_date = item[4].strftime('%Y-%m-%d')
            response += f"{item[0]}\n"
            response += f"نویسنده: {item[1]}\n"
            response += f"امانت گیرنده: {item[2]}\n"
            response += f"تاریخ امانت: {borrow_date}\n"
            response += f"موعد بازگشت: {due_date}\n"
            response += f"وضعیت: {item[5]}\n"
            response += "-" * 30 + "\n"
        
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
        cur.close()
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در دریافت اطلاعات: {e}")
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