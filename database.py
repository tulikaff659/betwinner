import sqlite3
import json
import random
import os
from pathlib import Path
from config import DB_FILE

def get_db_path():
    """Database fayl yo'lini qaytarish (Railway volume)"""
    # Railway volume mavjudligini tekshirish
    if os.path.exists('/data'):
        db_path = '/data/bot_database.db'
        # Backup papkasini yaratish
        os.makedirs('/data/backups', exist_ok=True)
        return db_path
    return DB_FILE

def init_database():
    """Ma'lumotlar bazasini yaratish"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Foydalanuvchilar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            referred_by INTEGER,
            referrals INTEGER DEFAULT 0,
            start_bonus_given INTEGER DEFAULT 0,
            withdraw_code TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Referral statistikasi jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER UNIQUE,
            bonus_given INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referrer_id) REFERENCES users(user_id),
            FOREIGN KEY (referred_id) REFERENCES users(user_id)
        )
    ''')
    
    # Balans o'zgarishlari tarixi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS balance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            old_balance INTEGER,
            new_balance INTEGER,
            amount INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Database created at: {db_path}")

def generate_unique_code(cursor) -> str:
    """Database uchun unique kod yaratish"""
    while True:
        code = f"{random.randint(0, 9999999):07d}"
        cursor.execute("SELECT user_id FROM users WHERE withdraw_code = ?", (code,))
        if not cursor.fetchone():
            return code

async def get_user(user_id: int, username: str = None) -> dict:
    """Foydalanuvchini databasega qo'shish yoki olish"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        withdraw_code = generate_unique_code(cursor)
        
        cursor.execute('''
            INSERT INTO users (user_id, username, balance, withdraw_code)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, 0, withdraw_code))
        conn.commit()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    
    conn.close()
    return dict(user)

def update_balance(user_id: int, amount: int, reason: str = ""):
    """Balansni yangilash va tarixga yozish"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False
            
        old_balance = result[0]
        new_balance = old_balance + amount
        
        cursor.execute('''
            UPDATE users SET balance = ? WHERE user_id = ?
        ''', (new_balance, user_id))
        
        cursor.execute('''
            INSERT INTO balance_history (user_id, old_balance, new_balance, amount, reason)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, old_balance, new_balance, amount, reason))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Balance update error: {e}")
        return False
    finally:
        conn.close()

def get_user_balance(user_id: int) -> int:
    """Foydalanuvchi balansini olish"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_all_users_count() -> dict:
    """Foydalanuvchilar statistikasi"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE start_bonus_given = 1")
    active = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")
    referred = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(balance) FROM users")
    total_balance = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        "total": total,
        "active": active,
        "referred": referred,
        "total_balance": total_balance
    }

def update_referral_bonus(referrer_id: int, referred_id: int) -> bool:
    """Referral bonusini hisoblash va saqlash"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO referrals (referrer_id, referred_id, bonus_given)
            VALUES (?, ?, 1)
        ''', (referrer_id, referred_id))
        
        cursor.execute('''
            UPDATE users SET referrals = referrals + 1
            WHERE user_id = ?
        ''', (referrer_id,))
        
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        conn.rollback()
        print(f"❌ Referral error: {e}")
        return False
    finally:
        conn.close()

def get_all_users():
    """Barcha foydalanuvchilar ID larini olish (broadcast uchun)"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def migrate_from_json():
    """Eski JSON ma'lumotlarni SQLite ga ko'chirish"""
    json_file = "users.json"
    if Path(json_file).exists():
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                old_users = json.load(f)
            
            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            for user_id_str, user_data in old_users.items():
                withdraw_code = user_data.get('withdraw_code')
                if not withdraw_code:
                    withdraw_code = generate_unique_code(cursor)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (user_id, username, balance, referred_by, referrals, start_bonus_given, withdraw_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    int(user_id_str),
                    user_data.get('username', ''),
                    user_data.get('balance', 0),
                    user_data.get('referred_by'),
                    user_data.get('referrals', 0),
                    1 if user_data.get('start_bonus_given', False) else 0,
                    withdraw_code
                ))
            
            conn.commit()
            conn.close()
            print(f"✅ {len(old_users)} users migrated from JSON")
            
            backup_name = f"users_backup_{random.randint(1000, 9999)}.json"
            os.rename(json_file, backup_name)
            print(f"📦 Old JSON file saved as {backup_name}")
            
        except Exception as e:
            print(f"❌ Migration error: {e}")
