import sqlite3
import logging
from datetime import datetime
from config import DATABASE_FILE

logging.basicConfig(level=logging.INFO)

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        """Bazadagi jadvallarni yaratish"""
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_date TIMESTAMP,
            balance INTEGER DEFAULT 0,
            referrer_id INTEGER,
            promo_used BOOLEAN DEFAULT FALSE,
            apk_access BOOLEAN DEFAULT FALSE
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            referred_id INTEGER,
            date TIMESTAMP,
            bonus_given BOOLEAN DEFAULT FALSE
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            signal_data TEXT,
            created_at TIMESTAMP
        )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name, referrer_id=None):
        """Yangi foydalanuvchi qo'shish"""
        try:
            self.cursor.execute(
                "INSERT INTO users (user_id, username, first_name, joined_date, referrer_id) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, first_name, datetime.now(), referrer_id)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logging.error(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id):
        """Foydalanuvchi ma'lumotlarini olish"""
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()
    
    def update_balance(self, user_id, amount):
        """Balansni yangilash"""
        self.cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        self.conn.commit()
    
    def use_promo(self, user_id):
        """Promokodni ishlatish"""
        self.cursor.execute(
            "UPDATE users SET promo_used = TRUE, balance = balance + 10, apk_access = TRUE WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()
        
        # Referalga bonus
        self.cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        referrer = self.cursor.fetchone()
        
        if referrer and referrer[0]:
            self.update_balance(referrer[0], 3)
            self.cursor.execute(
                "UPDATE referrals SET bonus_given = TRUE WHERE user_id = ? AND referred_id = ?",
                (referrer[0], user_id)
            )
            self.conn.commit()
    
    def add_referral(self, user_id, referred_id):
        """Referal qo'shish"""
        try:
            self.cursor.execute(
                "INSERT INTO referrals (user_id, referred_id, date) VALUES (?, ?, ?)",
                (user_id, referred_id, datetime.now())
            )
            self.conn.commit()
            return True
        except:
            return False
    
    def get_referrals_count(self, user_id):
        """Referallar sonini olish"""
        self.cursor.execute(
            "SELECT COUNT(*) FROM referrals WHERE user_id = ? AND bonus_given = 1",
            (user_id,)
        )
        return self.cursor.fetchone()[0]
    
    def set_apk_access(self, user_id, access):
        """APK huquqini sozlash"""
        self.cursor.execute(
            "UPDATE users SET apk_access = ? WHERE user_id = ?",
            (access, user_id)
        )
        self.conn.commit()
    
    def get_stats(self):
        """Statistika olish"""
        stats = {}
        
        self.cursor.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT SUM(balance) FROM users")
        stats['total_balance'] = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute("SELECT COUNT(*) FROM referrals")
        stats['total_refs'] = self.cursor.fetchone()[0]
        
        return stats
    
    def close(self):
        """Bazani yopish"""
        self.conn.close()
