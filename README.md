# BetWinner Telegram Bot

Telegram bot for BetWinner promotions, daily coupons and referral system.

## Features
- 🎰 Daily betting coupons
- 💰 Referral system (2500 UZS per referral)
- 🎁 Start bonus (15000 UZS)
- 💸 Withdraw system with unique codes
- 📊 Admin panel with statistics
- 📨 Broadcast messages to all users

## Deploy on Railway

### 1. Fork this repository

### 2. Create Railway project
- Go to [Railway.app](https://railway.app)
- Click "New Project" → "Deploy from GitHub repo"
- Select your forked repository

### 3. Set environment variables
- `BOT_TOKEN`: Your Telegram bot token
- `ADMIN_ID`: Your Telegram user ID (6935090105)
- `BOT_USERNAME`: Bot username (without @)
- `WITHDRAW_SITE_URL`: Withdrawal website URL

### 4. Add volume
- Create volume named `bot-data`
- Mount path: `/data`

### 5. Deploy
Railway will automatically deploy your bot.

## Admin Commands
- `/admin` - Open admin panel

## Database
SQLite database is stored in volume and persists between deployments.
