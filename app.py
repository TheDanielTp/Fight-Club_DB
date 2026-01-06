# region ---------------------------- Imports ----------------------------

import telebot
from telebot import types
import psycopg2
from psycopg2 import Error
from datetime import datetime, timedelta
import os
from functools import wraps
from unidecode import unidecode

# endregion

# region --------------------- Environment Variables ---------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")  
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")  

bot = telebot.TeleBot(BOT_TOKEN) # type: ignore
user_sessions = {}

# endregion

# region ----------------------- Starting Methods -----------------------

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

# endregion

# region ----------------------- Helper Functions -----------------------

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

def get_gym_name_by_id(gym_id):
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT name FROM gym WHERE gym_id = %s;",
            (gym_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except Error as e:
        print(f"DB error: {e}")
        return None
    finally:
        cursor.close() # type: ignore
        connection.close()

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

def get_fighter_by_id(fighter_id):
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT f.*, g.name as gym_name 
            FROM fighter f 
            LEFT JOIN gym g ON f.gym_id = g.gym_id 
            WHERE f.fighter_id = %s
        """, (fighter_id,))
        row = cursor.fetchone()
        if row:
            return {
                'fighter_id': row[0],
                'name': row[1],
                'nickname': row[2],
                'weight_class': row[3],
                'age': row[4],
                'nationality': row[5],
                'status': row[6],
                'gym_id': row[7],
                'gym_name': row[8]
            }
        return None
    except Error as e:
        print(f"DB error: {e}")
        return None
    finally:
        cursor.close() # type: ignore
        connection.close()

def get_gym_by_id(gym_id):
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM gym WHERE gym_id = %s", (gym_id,))
        row = cursor.fetchone()
        if row:
            return {
                'gym_id': row[0],
                'name': row[1],
                'location': row[2],
                'owner': row[3],
                'reputation_score': row[4]
            }
        return None
    except Error as e:
        print(f"DB error: {e}")
        return None
    finally:
        cursor.close() # type: ignore
        connection.close()

def get_trainer_by_id(trainer_id):
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT t.*, g.name as gym_name 
            FROM trainer t 
            LEFT JOIN gym g ON t.gym_id = g.gym_id 
            WHERE t.trainer_id = %s
        """, (trainer_id,))
        row = cursor.fetchone()
        if row:
            return {
                'trainer_id': row[0],
                'name': row[1],
                'specialty': row[2],
                'gym_id': row[3],
                'gym_name': row[4]
            }
        return None
    except Error as e:
        print(f"DB error: {e}")
        return None
    finally:
        cursor.close() # type: ignore
        connection.close()

def get_event_by_id(event_id):
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT me.*, 
                   f1.name as fighter1_name, f2.name as fighter2_name,
                   p1.result as fighter1_result, p2.result as fighter2_result
            FROM match_event me
            JOIN participants p1 ON me.match_id = p1.match_id
            JOIN participants p2 ON me.match_id = p2.match_id
            JOIN fighter f1 ON p1.fighter_id = f1.fighter_id
            JOIN fighter f2 ON p2.fighter_id = f2.fighter_id
            WHERE me.match_id = %s AND p1.fighter_id != p2.fighter_id
            LIMIT 1
        """, (event_id,))
        row = cursor.fetchone()
        if row:
            return {
                'match_id': row[0],
                'start_date': row[1],
                'end_date': row[2],
                'location': row[3],
                'fighter1_name': row[4],
                'fighter2_name': row[5],
                'fighter1_result': row[6],
                'fighter2_result': row[7]
            }
        return None
    except Error as e:
        print(f"DB error: {e}")
        return None
    finally:
        cursor.close() # type: ignore
        connection.close()

#endregion

# region --------------------------- Buttons ----------------------------

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
    button8 = types.KeyboardButton('اضافه کردن رویداد')
    button9 = types.KeyboardButton('جست‌وجوی مبارز')
    button10 = types.KeyboardButton('جست‌وجوی باشگاه')
    button11 = types.KeyboardButton('جست‌وجوی مربی')
    button12 = types.KeyboardButton('ویرایش مبارز')
    button13 = types.KeyboardButton('ویرایش باشگاه')
    button14 = types.KeyboardButton('ویرایش مربی')
    button15 = types.KeyboardButton('ویرایش رویداد')
    button16 = types.KeyboardButton('مدیریت تعلیمات')
    button17 = types.KeyboardButton('خروج از سیستم')

    markup.add(button1, button2, button3, button4, button5, button6, button7, button8, button9, button10, button11, button12, button13, button14, button15, button16, button17)
    return markup

def search_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    button1 = types.KeyboardButton('جست‌وجو با نام')
    button2 = types.KeyboardButton('بازگشت به منوی اصلی')
    markup.add(button1, button2)
    return markup

def cancel_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("لغو عملیات"))
    return markup

def trainer_fighter_management_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    button1 = types.KeyboardButton('اضافه کردن مربی به مبارز')
    button2 = types.KeyboardButton('حذف مربی از مبارز')
    button3 = types.KeyboardButton('مشاهده مربیان یک مبارز')
    button4 = types.KeyboardButton('مشاهده شاگردان یک مربی')
    button5 = types.KeyboardButton('بازگشت به منوی اصلی')
    markup.add(button1, button2, button3, button4, button5)
    return markup

# endregion

# region ------------------- Fighter-Trainer Handlers -------------------

@bot.message_handler(func=lambda message: message.text == 'اضافه کردن مربی به مبارز')
@login_required
def assign_trainer_to_fighter_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً شناسه مبارز را وارد کنید:", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_assign_fighter_id)

def process_assign_fighter_id(message):
    chat_id = message.chat.id
    fighter_id_str = message.text.strip()
    
    if fighter_id_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if not fighter_id_str.isdigit():
        msg = bot.send_message(chat_id, "شناسه نامعتبر است. لطفاً عدد وارد کنید:")
        bot.register_next_step_handler(msg, process_assign_fighter_id)
        return
    
    fighter_id = int(fighter_id_str)
    
    fighter = get_fighter_by_id(fighter_id)
    if not fighter:
        msg = bot.send_message(chat_id, "مبارزی با این شناسه یافت نشد. لطفاً دوباره تلاش کنید:")
        bot.register_next_step_handler(msg, process_assign_fighter_id)
        return
    
    msg = bot.send_message(chat_id, "لطفاً شناسه مربی را وارد کنید:", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_assign_trainer_id, fighter_id, fighter['name'])

def process_assign_trainer_id(message, fighter_id, fighter_name):
    chat_id = message.chat.id
    trainer_id_str = message.text.strip()
    
    if trainer_id_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if not trainer_id_str.isdigit():
        msg = bot.send_message(chat_id, "شناسه نامعتبر است. لطفاً عدد وارد کنید:")
        bot.register_next_step_handler(msg, process_assign_trainer_id, fighter_id, fighter_name)
        return
    
    trainer_id = int(trainer_id_str)
    
    # Check if trainer exists
    trainer = get_trainer_by_id(trainer_id)
    if not trainer:
        msg = bot.send_message(chat_id, "مربی‌ای با این شناسه یافت نشد. لطفاً مجدداً وارد کنید:")
        bot.register_next_step_handler(msg, process_assign_trainer_id, fighter_id, fighter_name)
        return
    
    # Check if this trainer is already assigned to this fighter
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM fighter_trainer 
            WHERE fighter_id = %s AND trainer_id = %s AND end_date IS NULL
        """, (fighter_id, trainer_id))
        
        if cur.fetchone():
            bot.send_message(chat_id, "این مربی قبلاً به این مبارز اختصاص داده شده است.", reply_markup=trainer_fighter_management_menu())
            return
        
        cur.close()
        
        # Ask for start date
        msg = bot.send_message(chat_id, "تاریخ شروع همکاری را وارد کنید (فرمت: YYYY-MM-DD یا 'امروز' برای تاریخ امروز):", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_assign_start_date, fighter_id, fighter_name, trainer_id, trainer['name'])
    except Error as e:
        bot.send_message(chat_id, f"خطا در بررسی اطلاعات: {e}", reply_markup=trainer_fighter_management_menu())
    finally:
        if conn:
            conn.close()

def process_assign_start_date(message, fighter_id, fighter_name, trainer_id, trainer_name):
    chat_id = message.chat.id
    start_date_str = message.text.strip()
    
    if start_date_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if start_date_str.lower() in ['امروز', 'today']:
        start_date = datetime.now().date()
    else:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            msg = bot.send_message(chat_id, "فرمت تاریخ اشتباه است. لطفاً مجدداً وارد کنید (فرمت: YYYY-MM-DD):")
            bot.register_next_step_handler(msg, process_assign_start_date, fighter_id, fighter_name, trainer_id, trainer_name)
            return
    
    # Save to database
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fighter_trainer (fighter_id, trainer_id, start_date)
            VALUES (%s, %s, %s)
        """, (fighter_id, trainer_id, start_date))
        
        conn.commit()
        
        response = f"""
✅ مربی با موفقیت به مبارز اختصاص داده شد:

👤 مبارز: {fighter_name}
🏷️ مربی: {trainer_name}
📅 تاریخ شروع: {start_date}
        """
        
        bot.send_message(chat_id, response, reply_markup=trainer_fighter_management_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در ثبت اطلاعات: {e}", reply_markup=trainer_fighter_management_menu())
    finally:
        if conn:
            conn.close()

# Method 2: Remove a trainer from a fighter
@bot.message_handler(func=lambda message: message.text == 'حذف مربی از مبارز')
@login_required
def remove_trainer_from_fighter_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً شناسه مبارز را وارد کنید:", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_remove_fighter_id)

def process_remove_fighter_id(message):
    chat_id = message.chat.id
    fighter_id_str = message.text.strip()
    
    if fighter_id_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if not fighter_id_str.isdigit():
        msg = bot.send_message(chat_id, "شناسه نامعتبر است. لطفاً عدد وارد کنید:")
        bot.register_next_step_handler(msg, process_remove_fighter_id)
        return
    
    fighter_id = int(fighter_id_str)
    
    # Get fighter's current trainers
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT ft.trainer_id, t.name as trainer_name, ft.start_date
            FROM fighter_trainer ft
            JOIN trainer t ON ft.trainer_id = t.trainer_id
            WHERE ft.fighter_id = %s AND ft.end_date IS NULL
            ORDER BY t.name
        """, (fighter_id,))
        
        trainers = cur.fetchall()
        
        if not trainers:
            bot.send_message(chat_id, "این مبارز در حال حاضر مربی فعال ندارد.", reply_markup=trainer_fighter_management_menu())
            return
        
        # Store trainers in a dictionary for selection
        trainer_dict = {}
        response = "مربیان فعال این مبارز:\n\n"
        
        for i, trainer in enumerate(trainers):
            trainer_id, trainer_name, start_date = trainer
            trainer_dict[str(i+1)] = {'trainer_id': trainer_id, 'trainer_name': trainer_name}
            response += f"{i+1}. {trainer_name} (از {start_date})\n"
        
        response += "\nشماره مربی را برای حذف انتخاب کنید:"
        
        # Create keyboard with trainer numbers
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        for i in range(len(trainers)):
            markup.add(types.KeyboardButton(str(i+1)))
        markup.add(types.KeyboardButton("لغو عملیات"))
        
        msg = bot.send_message(chat_id, response, reply_markup=markup)
        bot.register_next_step_handler(msg, process_select_trainer_to_remove, fighter_id, trainer_dict)
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در دریافت اطلاعات: {e}", reply_markup=trainer_fighter_management_menu())
    finally:
        if conn:
            conn.close()

def process_select_trainer_to_remove(message, fighter_id, trainer_dict):
    chat_id = message.chat.id
    choice = message.text.strip()
    
    if choice == "لغو عملیات":
        cancel_process(message)
        return
    
    if choice not in trainer_dict:
        msg = bot.send_message(chat_id, "انتخاب نامعتبر است. لطفاً مجدداً انتخاب کنید:")
        bot.register_next_step_handler(msg, process_select_trainer_to_remove, fighter_id, trainer_dict)
        return
    
    selected_trainer = trainer_dict[choice]
    
    # Ask for end date
    msg = bot.send_message(chat_id, "تاریخ پایان همکاری را وارد کنید (فرمت: YYYY-MM-DD یا 'امروز' برای تاریخ امروز):", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_remove_end_date, fighter_id, selected_trainer['trainer_id'], selected_trainer['trainer_name'])

def process_remove_end_date(message, fighter_id, trainer_id, trainer_name):
    chat_id = message.chat.id
    end_date_str = message.text.strip()
    
    if end_date_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if end_date_str.lower() in ['امروز', 'today']:
        end_date = datetime.now().date()
    else:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            msg = bot.send_message(chat_id, "فرمت تاریخ اشتباه است. لطفاً مجدداً وارد کنید (فرمت: YYYY-MM-DD):")
            bot.register_next_step_handler(msg, process_remove_end_date, fighter_id, trainer_id, trainer_name)
            return
    
    # Update database
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE fighter_trainer 
            SET end_date = %s 
            WHERE fighter_id = %s AND trainer_id = %s AND end_date IS NULL
        """, (end_date, fighter_id, trainer_id))
        
        conn.commit()
        
        response = f"""
✅ مربی با موفقیت از مبارز حذف شد:

👤 مبارز: {fighter_id}
🏷️ مربی: {trainer_name}
📅 تاریخ پایان: {end_date}
        """
        
        bot.send_message(chat_id, response, reply_markup=trainer_fighter_management_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در به‌روزرسانی اطلاعات: {e}", reply_markup=trainer_fighter_management_menu())
    finally:
        if conn:
            conn.close()

# Method 3: See all trainers of a fighter
@bot.message_handler(func=lambda message: message.text == 'مشاهده مربیان یک مبارز')
@login_required
def view_fighter_trainers_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً شناسه مبارز را وارد کنید:", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_view_fighter_trainers)

def process_view_fighter_trainers(message):
    chat_id = message.chat.id
    fighter_id_str = message.text.strip()
    
    if fighter_id_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if not fighter_id_str.isdigit():
        msg = bot.send_message(chat_id, "شناسه نامعتبر است. لطفاً عدد وارد کنید:")
        bot.register_next_step_handler(msg, process_view_fighter_trainers)
        return
    
    fighter_id = int(fighter_id_str)
    
    # Get fighter info
    fighter = get_fighter_by_id(fighter_id)
    if not fighter:
        bot.send_message(chat_id, "مبارزی با این شناسه یافت نشد.", reply_markup=trainer_fighter_management_menu())
        return
    
    # Get trainers
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.trainer_id, t.name as trainer_name, t.specialty,
                   ft.start_date, ft.end_date,
                   CASE 
                     WHEN ft.end_date IS NULL THEN 'فعال'
                     ELSE 'پایان یافته'
                   END as status
            FROM fighter_trainer ft
            JOIN trainer t ON ft.trainer_id = t.trainer_id
            WHERE ft.fighter_id = %s
            ORDER BY ft.end_date IS NULL DESC, ft.start_date DESC
        """, (fighter_id,))
        
        trainers = cur.fetchall()
        
        if not trainers:
            response = f"""
مبارز: {fighter['name']}
شناسه: {fighter_id}

⚠️ این مبارز در حال حاضر مربی ندارد.
            """
        else:
            response = f"""
مبارز: {fighter['name']}
شناسه: {fighter_id}

مربیان:
{"="*30}
            """
            
            active_count = 0
            inactive_count = 0
            
            for trainer in trainers:
                trainer_id, trainer_name, specialty, start_date, end_date, status = trainer
                
                response += f"\n🏷️ {trainer_name}"
                response += f"\n📌 تخصص: {specialty}"
                response += f"\n📅 شروع: {start_date}"
                
                if end_date:
                    response += f"\n📅 پایان: {end_date}"
                    response += f"\n📊 وضعیت: پایان یافته"
                    inactive_count += 1
                else:
                    response += f"\n📅 پایان: -"
                    response += f"\n📊 وضعیت: فعال"
                    active_count += 1
                
                response += f"\n🔗 شناسه مربی: {trainer_id}"
                response += f"\n{"-"*20}\n"
            
            response += f"""
آمار:
✅ مربیان فعال: {active_count}
❌ مربیان گذشته: {inactive_count}
            """
        
        bot.send_message(chat_id, response, reply_markup=trainer_fighter_management_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در دریافت اطلاعات: {e}", reply_markup=trainer_fighter_management_menu())
    finally:
        if conn:
            conn.close()

# Method 4: See all fighters of a trainer
@bot.message_handler(func=lambda message: message.text == 'مشاهده شاگردان یک مربی')
@login_required
def view_trainer_fighters_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً شناسه مربی را وارد کنید:", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_view_trainer_fighters)

def process_view_trainer_fighters(message):
    chat_id = message.chat.id
    trainer_id_str = message.text.strip()
    
    if trainer_id_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if not trainer_id_str.isdigit():
        msg = bot.send_message(chat_id, "شناسه نامعتبر است. لطفاً عدد وارد کنید:")
        bot.register_next_step_handler(msg, process_view_trainer_fighters)
        return
    
    trainer_id = int(trainer_id_str)
    
    # Get trainer info
    trainer = get_trainer_by_id(trainer_id)
    if not trainer:
        bot.send_message(chat_id, "مربی‌ای با این شناسه یافت نشد.", reply_markup=trainer_fighter_management_menu())
        return
    
    # Get fighters
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT f.fighter_id, f.name as fighter_name, f.weight_class,
                   f.status as fighter_status, ft.start_date, ft.end_date,
                   CASE 
                     WHEN ft.end_date IS NULL THEN 'فعال'
                     ELSE 'پایان یافته'
                   END as training_status
            FROM fighter_trainer ft
            JOIN fighter f ON ft.fighter_id = f.fighter_id
            WHERE ft.trainer_id = %s
            ORDER BY ft.end_date IS NULL DESC, ft.start_date DESC
        """, (trainer_id,))
        
        fighters = cur.fetchall()
        
        if not fighters:
            response = f"""
مربی: {trainer['name']}
تخصص: {trainer['specialty']}
شناسه: {trainer_id}

⚠️ این مربی در حال حاضر شاگردی ندارد.
            """
        else:
            response = f"""
مربی: {trainer['name']}
تخصص: {trainer['specialty']}
شناسه: {trainer_id}

شاگردان:
{"="*30}
            """
            
            active_count = 0
            inactive_count = 0
            
            for fighter in fighters:
                fighter_id, fighter_name, weight_class, fighter_status, start_date, end_date, training_status = fighter
                
                response += f"\n👤 {fighter_name}"
                response += f"\n⚖️ رده وزنی: {weight_class}"
                response += f"\n📊 وضعیت مبارز: {fighter_status}"
                response += f"\n📅 شروع: {start_date}"
                
                if end_date:
                    response += f"\n📅 پایان: {end_date}"
                    response += f"\n📊 وضعیت آموزش: پایان یافته"
                    inactive_count += 1
                else:
                    response += f"\n📅 پایان: -"
                    response += f"\n📊 وضعیت آموزش: فعال"
                    active_count += 1
                
                response += f"\n🔗 شناسه مبارز: {fighter_id}"
                response += f"\n{"-"*20}\n"
            
            response += f"""
آمار:
شاگردان فعال: {active_count}
شاگردان گذشته: {inactive_count}
            """
        
        bot.send_message(chat_id, response, reply_markup=trainer_fighter_management_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در دریافت اطلاعات: {e}", reply_markup=trainer_fighter_management_menu())
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == 'مدیریت تعلیمات')
@login_required
def manage_trainer_fighters_menu(message):
    chat_id = message.chat.id
    welcome_text = """
مدیریت شاگردان مربی
لطفاً یکی از گزینه‌ها را انتخاب کنید:
"""
    bot.send_message(chat_id, welcome_text, reply_markup=trainer_fighter_management_menu())

# region ------------------------ Start Handlers ------------------------

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

@bot.message_handler(func=lambda m: m.text == "لغو عملیات")
def cancel_process(message):
    chat_id = message.chat.id

    bot.clear_step_handler_by_chat_id(chat_id)
    bot.send_message(chat_id, "عملیات لغو شد.", reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == 'بازگشت به منوی اصلی')
@login_required
def back_to_main_menu(message):
    send_welcome(message)

# endregion

# region ----------------------- Display Handlers -----------------------

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
            SELECT f.fighter_id, f.name, f.nickname, f.weight_class, f.age, 
                   f.nationality, f.status, g.name as gym_name
            FROM fighter f
            LEFT JOIN gym g ON f.gym_id = g.gym_id
            ORDER BY f.name
            LIMIT 50
        """)
        fighters = cur.fetchall()
        
        if not fighters:
            bot.send_message(message.chat.id, "هیچ مبارزی در باشگاه ثبت نشده است.")
            return
        
        status_dict = {'active': 'فعال', 'retired': 'بازنشسته', 'suspended': 'تعلیق شده'}

        response = "لیست مبارزین:\n\n"
        for fighter in fighters:
            response += f"{fighter[1]}\n"
            response += f"شناسه مبارز: {fighter[0]}\n"
            response += f"نام مستعار: {fighter[2] or 'ثبت نشده'}\n"
            response += f"رده وزنی: {fighter[3]}\n"
            response += f"سن: {fighter[4]}\n"
            response += f"ملیت: {fighter[5]}\n"
            response += f"وضعیت: {status_dict.get(fighter[6], 'نامشخص')}\n"
            response += f"باشگاه: {fighter[7] or 'ثبت نشده'}\n"
            response += "-" * 40 + "\n"

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
            response += "-" * 40 + "\n"
        
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

            cur.execute("""
                SELECT COUNT(*) FROM fighter_trainer WHERE trainer_id = %s
            """, (trainer[0],))
            fighter_count = cur.fetchone()[0] # type: ignore
            
            response += f"تعداد شاگردان: {fighter_count}\n"
            response += "-" * 40 + "\n"
        
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
            SELECT me.match_id, me.start_date, me.end_date,me.location,f1.name as fighter1_name,f2.name as fighter2_name,p1.result as fighter1_result,p2.result as fighter2_result
            FROM match_event me
            JOIN participants p1 ON me.match_id = p1.match_id
            JOIN participants p2 ON me.match_id = p2.match_id
            JOIN fighter f1 ON p1.fighter_id = f1.fighter_id
            JOIN fighter f2 ON p2.fighter_id = f2.fighter_id
            WHERE p1.fighter_id < p2.fighter_id
            ORDER BY me.start_date DESC
            LIMIT 50
        """)
        events = cur.fetchall()
        
        if not events:
            bot.send_message(message.chat.id, "هیچ رویدادی ثبت نشده است.")
            return

        response = "آخرین رویدادها:\n\n"
        for event in events:
            match_id, start_date, end_date, location, fighter1_name, fighter2_name, fighter1_result, fighter2_result = event
            
            if fighter1_result == 'win':
                result_text = f"پیروزی {fighter1_name}"
            elif fighter2_result == 'win':
                result_text = f"پیروزی {fighter2_name}"
            elif fighter1_result == 'draw':
                result_text = "تساوی"
            elif fighter1_result == 'no contest':
                result_text = "نامعلوم"
            else:
                result_text = "ثبت نشده"
            
            response += f"رویداد {match_id}\n"
            response += f"تاریخ: {start_date.strftime('%Y-%m-%d')}\n"
            response += f"ساعت شروع: {start_date.strftime('%H:%M')}\n"
            
            if end_date:
                response += f"ساعت پایان: {end_date.strftime('%H:%M')}\n"
            else:
                response += f"ساعت پایان: ثبت نشده\n"
            
            response += f"مکان: {location}\n"
            response += f"مبارزین: {fighter1_name} و {fighter2_name}\n"
            response += f"نتیجه: {result_text}\n"
            response += "-" * 40 + "\n"
        
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
        cur.close()
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در دریافت اطلاعات: {e}")
    finally:
        if conn:
            conn.close()

# endregion

# region ------------------------- Add Handlers -------------------------

# region ----------- Add Fighter Handler -----------

@bot.message_handler(func=lambda message: message.text == 'اضافه کردن مبارز')
@login_required
def add_fighter_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام مبارز جدید را وارد کنید:", reply_markup=cancel_menu())
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
    age_str = message.text.strip()
    age = int(age_str)

    if age == "لغو عملیات":
        cancel_process(message)
        return

    if not age_str.isdigit() or age <= 0 or not age:
        msg = bot.send_message(chat_id, "سن وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_gym_owner, full_name, nickname, weight_class)
        return
    
    if age < 18:
        msg = bot.send_message(chat_id, "سن مبارز باید حداقل 18 سال باشد.")
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
        reply_markup = cancel_menu()
        bot.register_next_step_handler(msg, process_fighter_gym, full_name, nickname, weight_class, age, nationality)
        return
    
    gym_id = get_gym_id_by_name(gym_name)

    if gym_id is None:
        msg = bot.send_message(chat_id, "چنین باشگاهی ثبت نشده است. لطفاً نام باشگاه را مجدداً وارد کنید:")
        reply_markup = cancel_menu()
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

# endregion

# region ------------- Add Gym Handler -------------

@bot.message_handler(func=lambda message: message.text == 'اضافه کردن باشگاه')
@login_required
def add_gym_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام باشگاه را وارد کنید:", reply_markup=cancel_menu())
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

# endregion

# region ----------- Add Trainer Handler -----------

@bot.message_handler(func=lambda message: message.text == 'اضافه کردن مربی')
@login_required
def add_trainer_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام مربی را وارد کنید:", reply_markup=cancel_menu())
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
        reply_markup = cancel_menu()
        bot.register_next_step_handler(msg, process_trainer_gym, full_name, specialty)
        return
    
    gym_id = get_gym_id_by_name(gym_name)

    if gym_id is None:
        msg = bot.send_message(chat_id, "چنین باشگاهی ثبت نشده است. لطفاً نام باشگاه را مجدداً وارد کنید:")
        reply_markup = cancel_menu()
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
            bot.send_message(chat_id, f"خطا در ثبت مربی:\n{e}", reply_markup=main_menu())
        finally:
            if conn:
                conn.close()

# endregion

# region ------------ Add Event Handler ------------

@bot.message_handler(func=lambda message: message.text == 'اضافه کردن رویداد')
@login_required
def add_event_command(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً تاریخ و زمان شروع رویداد را وارد کنید (فرمت: YYYY-MM-DD HH:MM):", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_event_start_date)

def process_event_start_date(message):
    chat_id = message.chat.id
    start_date_str = message.text.strip()
    
    if start_date_str == "لغو عملیات":
        cancel_process(message)
        return
    
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M")
        
        msg = bot.send_message(chat_id, "لطفاً تاریخ و زمان پایان رویداد را وارد کنید (فرمت: YYYY-MM-DD HH:MM):", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_event_end_date, start_date)
    except ValueError:
        msg = bot.send_message(chat_id, "فرمت تاریخ اشتباه است. لطفاً مجدداً وارد کنید (فرمت: YYYY-MM-DD HH:MM):")
        bot.register_next_step_handler(msg, process_event_start_date)
    
def process_event_end_date(message, start_date):
    chat_id = message.chat.id
    end_date_str = message.text.strip()
    
    if end_date_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if end_date_str in ["نامعلوم", "نامشخص", "ندارد", "خالی"]:
        end_date = None
        msg = bot.send_message(chat_id, "لطفاً مکان رویداد را وارد کنید:")
        bot.register_next_step_handler(msg, process_event_location, start_date, end_date)
        return
    
    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M")
        
        if end_date <= start_date:
            msg = bot.send_message(chat_id, "تاریخ پایان باید بعد از تاریخ شروع باشد. لطفاً مجدداً وارد کنید (فرمت: YYYY-MM-DD HH:MM):")
            bot.register_next_step_handler(msg, process_event_end_date, start_date)
            return
        
        msg = bot.send_message(chat_id, "لطفاً مکان رویداد را وارد کنید:")
        bot.register_next_step_handler(msg, process_event_location, start_date, end_date)
    except ValueError:
        msg = bot.send_message(chat_id, "فرمت تاریخ اشتباه است. لطفاً مجدداً وارد کنید (فرمت: YYYY-MM-DD HH:MM):")
        bot.register_next_step_handler(msg, process_event_end_date, start_date)

def process_event_location(message, start_date, end_date):
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
    bot.register_next_step_handler(msg, process_event_fighter1, start_date, end_date, location)

def process_event_fighter1(message, start_date, end_date, location):
    chat_id = message.chat.id
    fighter1_name = message.text.strip()
    
    if fighter1_name == "لغو عملیات":
        cancel_process(message)
        return
    
    fighter1_id = get_fighter_id_by_name(fighter1_name)
    
    if fighter1_id is None:
        msg = bot.send_message(chat_id, "مبارز یافت نشد. لطفاً نام را مجدداً وارد کنید:")
        bot.register_next_step_handler(msg, process_event_fighter1, start_date, end_date, location)
        return
    
    msg = bot.send_message(chat_id, "لطفاً نام مبارز دوم را وارد کنید:")
    bot.register_next_step_handler(msg, process_event_fighter2, start_date, end_date, location, fighter1_id, fighter1_name)

def process_event_fighter2(message, start_date, end_date, location, fighter1_id, fighter1_name):
    chat_id = message.chat.id
    fighter2_name = message.text.strip()
    
    if fighter2_name == "لغو عملیات":
        cancel_process(message)
        return
    
    fighter2_id = get_fighter_id_by_name(fighter2_name)
    
    if fighter2_id is None:
        msg = bot.send_message(chat_id, "مبارز یافت نشد. لطفاً نام را مجدداً وارد کنید:")
        bot.register_next_step_handler(msg, process_event_fighter2, start_date, end_date, location, fighter1_id, fighter1_name)
        return
    
    if fighter2_id == fighter1_id:
        msg = bot.send_message(chat_id, "یک مبارز نمی‌تواند با خودش مبارزه کند! لطفاً مبارز دیگری را وارد کنید:")
        bot.register_next_step_handler(msg, process_event_fighter2, start_date, end_date, location, fighter1_id, fighter1_name)
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("برد مبارز اول"), 
               types.KeyboardButton("برد مبارز دوم"),
               types.KeyboardButton("مساوی"),
               types.KeyboardButton("لغو شده"),
               types.KeyboardButton("نامعلوم"),
               types.KeyboardButton("لغو عملیات"))
    
    msg = bot.send_message(chat_id, "نتیجه مبارزه را انتخاب کنید:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_event_result, start_date, end_date, location, fighter1_id, fighter1_name, fighter2_id, fighter2_name)

def process_event_result(message, start_date, end_date, location, fighter1_id, fighter1_name, fighter2_id, fighter2_name):
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
            INSERT INTO match_event (start_date, end_date, location)
            VALUES (%s, %s, %s)
            RETURNING match_id
        """, (start_date, end_date, location))
        
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

# endregion

# endregion

# region ------------------------ Search Handlers -----------------------

# region ---------- Search Fighter Handler ---------

@bot.message_handler(func=lambda message: message.text == 'جست‌وجوی مبارز')
@login_required
def search_fighter_menu(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام مبارز را برای جست‌وجو وارد کنید:", reply_markup=cancel_menu())
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
        
        status_dict = {'active': 'فعال', 'retired': 'بازنشسته', 'suspended': 'تعلیق شده'}
        
        response = f"نتایج جست‌وجو برای '{search_term}':\n\n"
        for fighter in fighters:
            response += f"**{fighter[1]}**\n"
            response += f"شناسه مبارز: {fighter[0]}\n"
            response += f"نام مستعار: {fighter[2] or 'ثبت نشده'}\n"
            response += f"رده وزنی: {fighter[3]}\n"
            response += f"سن: {fighter[4]}\n"
            response += f"ملیت: {fighter[5]}\n"
            response += f"وضعیت: {status_dict.get(fighter[6], 'نامشخص')}\n"
            response += f"باشگاه: {fighter[7] or 'ثبت نشده'}\n"
            response += "-" * 40 + "\n"
        
        bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در جست‌وجو: {e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

# endregion

# region ------------ Search Gym Handler -----------

@bot.message_handler(func=lambda message: message.text == 'جست‌وجوی باشگاه')
@login_required
def search_gym_menu(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام باشگاه یا مکان باشگاه یا نام مالک را برای جست‌وجو وارد کنید:", reply_markup=cancel_menu())
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
            response += "-" * 40 + "\n"
        
        bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در جست‌وجو: {e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

# endregion

# region ---------- Search Trainer Handler ---------

@bot.message_handler(func=lambda message: message.text == 'جست‌وجوی مربی')
@login_required
def search_trainer_menu(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً نام مربی یا نام تخصص را برای جست‌وجو وارد کنید:", reply_markup=cancel_menu())
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
            response += "-" * 40 + "\n"
        
        bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در جست‌وجو: {e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

# endregion

# endregion

# region ----------------------- Editing Handlers -----------------------

# region ---------- Edit Fighter Handler -----------

@bot.message_handler(func=lambda message: message.text == 'ویرایش مبارز')
@login_required
def edit_fighter_menu(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً شناسه مبارز را برای ویرایش وارد کنید:", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_edit_fighter_id)

def process_edit_fighter_id(message):
    chat_id = message.chat.id
    fighter_id_str = message.text.strip()
    
    if fighter_id_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if not fighter_id_str.isdigit():
        msg = bot.send_message(chat_id, "شناسه نامعتبر است. لطفاً عدد وارد کنید:")
        bot.register_next_step_handler(msg, process_edit_fighter_id)
        return
    
    fighter_id = int(fighter_id_str)
    fighter = get_fighter_by_id(fighter_id)
    
    if not fighter:
        bot.send_message(chat_id, "مبارزی با این شناسه یافت نشد.", reply_markup=main_menu())
        return
    
    response = f"""
اطلاعات فعلی مبارز {fighter_id}:
نام: {fighter['name']}
نام مستعار: {fighter['nickname'] or 'ثبت نشده'}
رده وزنی: {fighter['weight_class']}
سن: {fighter['age']}
ملیت: {fighter['nationality'] or 'ثبت نشده'}
وضعیت: {fighter['status']}
باشگاه: {fighter['gym_name'] or 'ثبت نشده'}

لطفاً فیلدی که می‌خواهید ویرایش کنید را انتخاب کنید:
"""

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.add(types.KeyboardButton("نام"),
               types.KeyboardButton("نام مستعار"),
               types.KeyboardButton("رده وزنی"),
               types.KeyboardButton("سن"),
               types.KeyboardButton("ملیت"),
               types.KeyboardButton("وضعیت"),
               types.KeyboardButton("باشگاه"),
               types.KeyboardButton("لغو عملیات"))
    
    msg = bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, process_edit_fighter_field, fighter_id)

def process_edit_fighter_field(message, fighter_id):
    chat_id = message.chat.id
    field = message.text.strip()
    
    if field == "لغو عملیات":
        cancel_process(message)
        return
    
    field_mapping = {
        "نام": "name",
        "نام مستعار": "nickname",
        "رده وزنی": "weight_class",
        "سن": "age",
        "ملیت": "nationality",
        "وضعیت": "status",
        "باشگاه": "gym_id"
    }
    
    if field not in field_mapping:
        bot.send_message(chat_id, "فیلد وارد شده نامعتبر است. لطفاً از گزینه‌ها انتخاب کنید.", reply_markup=main_menu())
        return
    
    field_name = field_mapping[field]
    
    if field == "وضعیت":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        markup.add(types.KeyboardButton("active"),
                   types.KeyboardButton("retired"),
                   types.KeyboardButton("suspended"),
                   types.KeyboardButton("لغو عملیات"))
        msg = bot.send_message(chat_id, "لطفاً وضعیت جدید را انتخاب کنید (active, retired, suspended):", reply_markup=markup)
        bot.register_next_step_handler(msg, process_edit_fighter_value, fighter_id, field_name)
    elif field == "باشگاه":
        msg = bot.send_message(chat_id, "لطفاً نام باشگاه جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_fighter_value, fighter_id, field_name)
    elif field == "سن":
        msg = bot.send_message(chat_id, "لطفاً سن جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_fighter_value, fighter_id, field_name)
    elif field == "نام مستعار":
        msg = bot.send_message(chat_id, "لطفاً نام مستعار جدید را وارد کنید (یا 'خالی' برای حذف نام مستعار):", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_fighter_value, fighter_id, field_name)
    elif field == "ملیت":
        msg = bot.send_message(chat_id, "لطفاً ملیت جدید را وارد کنید (یا 'خالی' برای حذف ملیت):", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_fighter_value, fighter_id, field_name)
    elif field == "رده وزنی":
        msg = bot.send_message(chat_id, "لطفاً رده وزنی جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_fighter_value, fighter_id, field_name)
    elif field == "نام":
        msg = bot.send_message(chat_id, "لطفاً نام جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_fighter_value, fighter_id, field_name)
    else:
        msg = bot.send_message(chat_id, f"لطفاً مقدار جدید برای فیلد '{field}' را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_fighter_value, fighter_id, field_name)

def process_edit_fighter_value(message, fighter_id, field_name):
    chat_id = message.chat.id
    new_value = message.text.strip()
    
    if new_value == "لغو عملیات":
        cancel_process(message)
        return
    
    if field_name == "gym_id":
        gym_id = get_gym_id_by_name(new_value)
        if gym_id is None:
            msg = bot.send_message(chat_id, "چنین باشگاهی یافت نشد. لطفاً مجدداً وارد کنید:")
            bot.register_next_step_handler(msg, process_edit_fighter_value, fighter_id, field_name)
            return
        new_value = gym_id
    elif field_name == "nickname" and new_value in ["خالی", "ندارد", "حذف"]:
        new_value = None
    elif field_name == "nationality" and new_value in ["خالی", "ندارد", "حذف"]:
        new_value = None

    confirm_update_fighter(message, fighter_id, field_name, new_value)

def confirm_update_fighter(message, fighter_id, field_name, new_value):
    chat_id = message.chat.id
    
    response = f"""
آیا از اعمال تغییر مطمئن هستید؟
    """
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("بله، ویرایش کن"),
               types.KeyboardButton("خیر، لغو کن"))
    
    msg = bot.send_message(chat_id, response, reply_markup=markup)
    bot.register_next_step_handler(msg, process_fighter_update_confirmation, fighter_id, field_name, new_value)

def process_fighter_update_confirmation(message, fighter_id, field_name, new_value):
    chat_id = message.chat.id
    confirmation = message.text.strip()
    
    if confirmation in ["خیر، لغو کن", "لغو عملیات"]:
        bot.send_message(chat_id, "ویرایش لغو شد.", reply_markup=main_menu())
        return
    
    if confirmation != "بله، ویرایش کن":
        bot.send_message(chat_id, "دستور نامعتبر.", reply_markup=main_menu())
        return
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.", reply_markup=main_menu())
        return
    
    try:
        cur = conn.cursor()
        
        if field_name == "age":
            new_value = int(new_value)
        
        cur.execute(f"""
            UPDATE fighter 
            SET {field_name} = %s 
            WHERE fighter_id = %s
        """, (new_value, fighter_id))
        
        conn.commit()
        
        bot.send_message(chat_id, "اطلاعات مبارز با موفقیت ویرایش شد.", reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در ویرایش: {e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

# endregion

# region ------------ Edit Gym Handler -------------

@bot.message_handler(func=lambda message: message.text == 'ویرایش باشگاه')
@login_required
def edit_gym_menu(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً شناسه باشگاه را برای ویرایش وارد کنید:", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_edit_gym_id)

def process_edit_gym_id(message):
    chat_id = message.chat.id
    gym_id_str = message.text.strip()
    
    if gym_id_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if not gym_id_str.isdigit():
        msg = bot.send_message(chat_id, "شناسه نامعتبر است. لطفاً عدد وارد کنید:")
        bot.register_next_step_handler(msg, process_edit_gym_id)
        return
    
    gym_id = int(gym_id_str)
    gym = get_gym_by_id(gym_id)
    
    if not gym:
        bot.send_message(chat_id, "باشگاهی با این شناسه یافت نشد.", reply_markup=main_menu())
        return
    
    response = f"""
اطلاعات فعلی باشگاه {gym_id}:
نام: {gym['name']}
مکان: {gym['location']}
مالک: {gym['owner']}
امتیاز شهرت: {gym['reputation_score']}

لطفاً فیلدی که می‌خواهید ویرایش کنید را انتخاب کنید:
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("نام"),
               types.KeyboardButton("مکان"),
               types.KeyboardButton("مالک"),
               types.KeyboardButton("امتیاز شهرت"),
               types.KeyboardButton("لغو عملیات"))
    
    msg = bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, process_edit_gym_field, gym_id)

def process_edit_gym_field(message, gym_id):
    chat_id = message.chat.id
    field = message.text.strip()
    
    if field == "لغو عملیات":
        cancel_process(message)
        return
    
    field_mapping = {
        "نام": "name",
        "مکان": "location",
        "مالک": "owner",
        "امتیاز شهرت": "reputation_score"
    }
    
    if field not in field_mapping:
        bot.send_message(chat_id, "فیلد نامعتبر است.", reply_markup=main_menu())
        return
    
    field_name = field_mapping[field]
    
    if field_name == 'reputation_score':
        msg = bot.send_message(chat_id, "لطفاً امتیاز شهرت جدید را وارد کنید (۰ تا ۱۰۰):", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_gym_value, gym_id, field_name)
    elif field == "نام":
        msg = bot.send_message(chat_id, "لطفاً نام جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_gym_value, gym_id, field_name)
    elif field == "مکان":
        msg = bot.send_message(chat_id, "لطفاً مکان جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_gym_value, gym_id, field_name)
    elif field == "مالک":
        msg = bot.send_message(chat_id, "لطفاً نام مالک جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_gym_value, gym_id, field_name)
    else:
        msg = bot.send_message(chat_id, f"لطفاً مقدار جدید برای '{field}' وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_gym_value, gym_id, field_name)

def process_edit_gym_value(message, gym_id, field_name):
    chat_id = message.chat.id
    new_value = message.text.strip()
    
    if new_value == "لغو عملیات":
        cancel_process(message)
        return
    
    if field_name == 'reputation_score':
        if not new_value.isdigit():
            msg = bot.send_message(chat_id, "امتیاز باید عدد بین ۰ تا ۱۰۰ باشد. لطفاً مجدداً وارد کنید:")
            bot.register_next_step_handler(msg, process_edit_gym_value, gym_id, field_name)
            return
        
        score = int(new_value)
        if score < 0 or score > 100:
            msg = bot.send_message(chat_id, "امتیاز باید بین ۰ تا ۱۰۰ باشد. لطفاً مجدداً وارد کنید:")
            bot.register_next_step_handler(msg, process_edit_gym_value, gym_id, field_name)
            return
    
    response = f"""
آیا از اعمال تغییر مطمئن هستید؟
    """
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("بله، ویرایش کن"),
               types.KeyboardButton("خیر، لغو کن"))
    
    msg = bot.send_message(chat_id, response, reply_markup=markup)
    bot.register_next_step_handler(msg, process_gym_update_confirmation, gym_id, field_name, new_value)

def process_gym_update_confirmation(message, gym_id, field_name, new_value):
    chat_id = message.chat.id
    confirmation = message.text.strip()
    
    if confirmation in ["خیر، لغو کن", "لغو عملیات"]:
        bot.send_message(chat_id, "ویرایش لغو شد.", reply_markup=main_menu())
        return
    
    if confirmation != "بله، ویرایش کن":
        bot.send_message(chat_id, "دستور نامعتبر.", reply_markup=main_menu())
        return
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.", reply_markup=main_menu())
        return
    
    try:
        cur = conn.cursor()
        
        if field_name == 'reputation_score':
            new_value = int(new_value)
        
        cur.execute(f"""
            UPDATE gym 
            SET {field_name} = %s 
            WHERE gym_id = %s
        """, (new_value, gym_id))
        
        conn.commit()
        
        bot.send_message(chat_id, "اطلاعات باشگاه با موفقیت ویرایش شد.", reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در ویرایش: {e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

# endregion

# region ---------- Edit Trainer Handler -----------

@bot.message_handler(func=lambda message: message.text == 'ویرایش مربی')
@login_required
def edit_trainer_menu(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً شناسه مربی را برای ویرایش وارد کنید:", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_edit_trainer_id)

def process_edit_trainer_id(message):
    chat_id = message.chat.id
    trainer_id_str = message.text.strip()
    
    if trainer_id_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if not trainer_id_str.isdigit():
        msg = bot.send_message(chat_id, "شناسه نامعتبر است. لطفاً عدد وارد کنید:")
        bot.register_next_step_handler(msg, process_edit_trainer_id)
        return
    
    trainer_id = int(trainer_id_str)
    trainer = get_trainer_by_id(trainer_id)
    
    if not trainer:
        bot.send_message(chat_id, "مربی‌ای با این شناسه یافت نشد.", reply_markup=main_menu())
        return
    
    response = f"""
اطلاعات فعلی مربی {trainer_id}:
نام: {trainer['name']}
تخصص: {trainer['specialty']}
باشگاه: {trainer['gym_name'] or 'ثبت نشده'}

لطفاً فیلدی که می‌خواهید ویرایش کنید را انتخاب کنید:
    """
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("نام"),
               types.KeyboardButton("تخصص"),
               types.KeyboardButton("باشگاه"),
               types.KeyboardButton("لغو عملیات"))
    
    msg = bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, process_edit_trainer_field, trainer_id)

def process_edit_trainer_field(message, trainer_id):
    chat_id = message.chat.id
    field = message.text.strip()
    
    if field == "لغو عملیات":
        cancel_process(message)
        return
    
    field_mapping = {
        "نام": "name",
        "تخصص": "specialty",
        "باشگاه": "gym_id"
    }
    
    if field not in field_mapping:
        bot.send_message(chat_id, "فیلد نامعتبر است. لطفاً از گزینه‌ها انتخاب کنید.", reply_markup=main_menu())
        return
    
    field_name = field_mapping[field]
    
    if field == "باشگاه":
        msg = bot.send_message(chat_id, "لطفاً نام باشگاه جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_trainer_value, trainer_id, field_name)
    elif field == "تخصص":
        msg = bot.send_message(chat_id, "لطفاً تخصص جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_trainer_value, trainer_id, field_name)
    elif field == "نام":
        msg = bot.send_message(chat_id, "لطفاً نام جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_trainer_value, trainer_id, field_name)
    else:
        msg = bot.send_message(chat_id, f"لطفاً مقدار جدید برای '{field}' وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_trainer_value, trainer_id, field_name)

def process_edit_trainer_value(message, trainer_id, field_name):
    chat_id = message.chat.id
    new_value = message.text.strip()
    
    if new_value == "لغو عملیات":
        cancel_process(message)
        return
    
    if field_name == "gym_id":
        gym_id = get_gym_id_by_name(new_value)
        if gym_id is None:
            msg = bot.send_message(chat_id, "چنین باشگاهی یافت نشد. لطفاً مجدداً وارد کنید:")
            bot.register_next_step_handler(msg, process_edit_trainer_value, trainer_id, field_name)
            return
        new_value = gym_id
    
    if field_name == "name" and len(new_value) <= 1:
        msg = bot.send_message(chat_id, "نام وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
        bot.register_next_step_handler(msg, process_edit_trainer_value, trainer_id, field_name)
        return
    
    confirm_update_trainer(message, trainer_id, field_name, new_value)

def confirm_update_trainer(message, trainer_id, field_name, new_value):
    chat_id = message.chat.id
    
    response = f"""
آیا از اعمال تغییر مطمئن هستید؟
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("بله، ویرایش کن"),
               types.KeyboardButton("خیر، لغو کن"),
               types.KeyboardButton("لغو عملیات"))
    
    msg = bot.send_message(chat_id, response, reply_markup=markup)
    bot.register_next_step_handler(msg, process_trainer_update_confirmation, trainer_id, field_name, new_value)

def process_trainer_update_confirmation(message, trainer_id, field_name, new_value):
    chat_id = message.chat.id
    confirmation = message.text.strip()
    
    if confirmation in ["خیر، لغو کن", "لغو عملیات"]:
        bot.send_message(chat_id, "ویرایش لغو شد.", reply_markup=main_menu())
        return
    
    if confirmation != "بله، ویرایش کن":
        bot.send_message(chat_id, "دستور نامعتبر.", reply_markup=main_menu())
        return
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.", reply_markup=main_menu())
        return
    
    try:
        cur = conn.cursor()
        
        cur.execute(f"""
            UPDATE trainer 
            SET {field_name} = %s 
            WHERE trainer_id = %s
        """, (new_value, trainer_id))
        
        conn.commit()
        
        bot.send_message(chat_id, "اطلاعات مربی با موفقیت ویرایش شد.", reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در ویرایش: {e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

# endregion

# region ----------- Edit Event Handler ------------

@bot.message_handler(func=lambda message: message.text == 'ویرایش رویداد')
@login_required
def edit_event_menu(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "لطفاً شناسه رویداد را برای ویرایش وارد کنید:", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_edit_event_id)

def process_edit_event_id(message):
    chat_id = message.chat.id
    event_id_str = message.text.strip()
    
    if event_id_str == "لغو عملیات":
        cancel_process(message)
        return
    
    if not event_id_str.isdigit():
        msg = bot.send_message(chat_id, "شناسه نامعتبر است. لطفاً عدد وارد کنید:")
        bot.register_next_step_handler(msg, process_edit_event_id)
        return
    
    event_id = int(event_id_str)
    event = get_event_by_id(event_id)
    
    if not event:
        bot.send_message(chat_id, "رویدادی با این شناسه یافت نشد.", reply_markup=main_menu())
        return
    
    response = f"""
اطلاعات فعلی رویداد {event_id}:
تاریخ: {event['start_date'].strftime('%Y-%m-%d %H:%M')}
مکان: {event['location']}
مبارزین: {event['fighter1_name']} vs {event['fighter2_name']}
نتیجه: {event['fighter1_name']} ({event['fighter1_result']}) - {event['fighter2_name']} ({event['fighter2_result']})

لطفاً فیلدی که می‌خواهید ویرایش کنید را انتخاب کنید:
    """
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("تاریخ شروع"),
               types.KeyboardButton("تاریخ پایان"),
               types.KeyboardButton("مکان"),
               types.KeyboardButton("نتیجه"),
               types.KeyboardButton("لغو عملیات"))
    
    msg = bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, process_edit_event_field, event_id)

def process_edit_event_field(message, event_id):
    chat_id = message.chat.id
    field = message.text.strip()
    
    if field == "لغو عملیات":
        cancel_process(message)
        return
    
    field_mapping = {
        "تاریخ شروع": "start_date",
        "تاریخ پایان": "end_date",
        "مکان": "location",
        "نتیجه": "result"
    }

    if field not in field_mapping:
        bot.send_message(chat_id, "فیلد نامعتبر است.", reply_markup=main_menu())
        return
    
    field_name = field_mapping[field]
    
    if field == "تاریخ شروع":
        msg = bot.send_message(chat_id, "لطفاً تاریخ و زمان جدید را وارد کنید (فرمت: YYYY-MM-DD HH:MM):", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_event_start_date, event_id, field_name)
    elif field == "تاریخ پایان":
        msg = bot.send_message(chat_id, "لطفاً تاریخ و زمان جدید را وارد کنید (فرمت: YYYY-MM-DD HH:MM):", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_event_end_date, event_id, field_name)
    elif field == "مکان":
        msg = bot.send_message(chat_id, "لطفاً نام مکان جدید را وارد کنید:", reply_markup=cancel_menu())
        bot.register_next_step_handler(msg, process_edit_event_location, event_id, field_name)
    elif field == "نتیجه":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(types.KeyboardButton("برد مبارز اول"),
                   types.KeyboardButton("برد مبارز دوم"),
                   types.KeyboardButton("مساوی"),
                   types.KeyboardButton("لغو شده"),
                   types.KeyboardButton("لغو عملیات"))
        
        msg = bot.send_message(chat_id, "نتیجه جدید را انتخاب کنید:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_edit_event_result, event_id, field_name)
    else:
        bot.send_message(chat_id, "فیلد نامعتبر است.", reply_markup=main_menu())

def process_edit_event_start_date(message, event_id, field_name):
    chat_id = message.chat.id
    new_date_str = message.text.strip()
    
    if new_date_str == "لغو عملیات":
        cancel_process(message)
        return
    
    try:
        new_date = datetime.strptime(new_date_str, "%Y-%m-%d %H:%M")
        confirm_update_event(message, event_id, field_name, new_date)
    except ValueError:
        msg = bot.send_message(chat_id, "فرمت تاریخ اشتباه است. لطفاً مجدداً وارد کنید (فرمت: YYYY-MM-DD HH:MM):")
        bot.register_next_step_handler(msg, process_edit_event_start_date, event_id, field_name)

def process_edit_event_end_date(message, event_id, field_name):
    chat_id = message.chat.id
    new_date_str = message.text.strip()
    
    if new_date_str == "لغو عملیات":
        cancel_process(message)
        return
    
    try:
        new_date = datetime.strptime(new_date_str, "%Y-%m-%d %H:%M")
        
        confirm_update_event(message, event_id, field_name, new_date)
    except ValueError:
        msg = bot.send_message(chat_id, "فرمت تاریخ اشتباه است. لطفاً مجدداً وارد کنید (فرمت: YYYY-MM-DD HH:MM):")
        bot.register_next_step_handler(msg, process_edit_event_end_date, event_id, field_name)

def process_edit_event_location(message, event_id, field_name):
    chat_id = message.chat.id
    new_location = message.text.strip()
    
    if new_location == "لغو عملیات":
        cancel_process(message)
        return
    
    if not new_location:
        msg = bot.send_message(chat_id, "مکان وارد شده معتبر نیست. لطفاً مجدداً وارد کنید:")
        bot.register_next_step_handler(msg, process_edit_event_location)
        return
    
    confirm_update_event(message, event_id, field_name, new_location)

def process_edit_event_result(message, event_id, field_name):
    chat_id = message.chat.id
    result_text = message.text.strip()
    
    if result_text == "لغو عملیات":
        cancel_process(message)
        return
    
    result_map = {
        "برد مبارز اول": "win",
        "برد مبارز دوم": "win",
        "مساوی": "draw",
        "لغو شده": "no contest"
    }
    
    if result_text not in result_map:
        msg = bot.send_message(chat_id, "نتیجه نامعتبر است. لطفاً از گزینه‌ها انتخاب کنید:")
        bot.register_next_step_handler(msg, process_edit_event_result)
        return
        
    confirm_update_event(message, event_id, field_name, result_text)

def confirm_update_event(message, event_id, field_name, new_value):
    chat_id = message.chat.id
    
    response = f"""
آیا از اعمال تغییر مطمئن هستید؟
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("بله، ویرایش کن"),
               types.KeyboardButton("خیر، لغو کن"))
    
    msg = bot.send_message(chat_id, response, reply_markup=markup)
    bot.register_next_step_handler(msg, process_event_update_confirmation, event_id, field_name, new_value)

def process_event_update_confirmation(message, event_id, field_name, new_value):
    chat_id = message.chat.id
    confirmation = message.text.strip()
    
    if confirmation in ["خیر، لغو کن", "لغو عملیات"]:
        bot.send_message(chat_id, "ویرایش لغو شد.", reply_markup=main_menu())
        return
    
    if confirmation != "بله، ویرایش کن":
        bot.send_message(chat_id, "دستور نامعتبر.", reply_markup=main_menu())
        return
    
    # Update in database
    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.", reply_markup=main_menu())
        return
    
    try:
        cur = conn.cursor()
        
        if field_name in ['start_date', "end_date", 'location']:
            cur.execute(f"""
                UPDATE match_event 
                SET {field_name} = %s 
                WHERE match_id = %s
            """, (new_value, event_id))
            
        elif field_name == 'result':
            result_map = {
                "برد مبارز اول": "win",
                "برد مبارز دوم": "win",
                "مساوی": "draw",
                "لغو شده": "no contest"
            }

            result = result_map[new_value]
            result_text = new_value
            
            event = get_event_by_id(event_id)
            
            if result_text == "برد مبارز اول":
                fighter1_result = "win"
                fighter2_result = "loss"
            elif result_text == "برد مبارز دوم":
                fighter1_result = "loss"
                fighter2_result = "win"
            else:
                fighter1_result = result
                fighter2_result = result
            
            fighter1_id = get_fighter_id_by_name(event['fighter1_name']) # type: ignore
            fighter2_id = get_fighter_id_by_name(event['fighter2_name']) # type: ignore
            
            cur.execute("""
                UPDATE participants 
                SET result = %s 
                WHERE match_id = %s AND fighter_id = %s
            """, (fighter1_result, event_id, fighter1_id))
            
            cur.execute("""
                UPDATE participants 
                SET result = %s 
                WHERE match_id = %s AND fighter_id = %s
            """, (fighter2_result, event_id, fighter2_id))
        
        conn.commit()
        
        bot.send_message(chat_id, "اطلاعات رویداد با موفقیت ویرایش شد.", reply_markup=main_menu())
        cur.close()
    except Error as e:
        bot.send_message(chat_id, f"خطا در ویرایش: {e}", reply_markup=main_menu())
    finally:
        if conn:
            conn.close()

# endregion

# endregion

if __name__ == '__main__':
    create_tables()
    print("Running...")

    bot.polling(none_stop=True)