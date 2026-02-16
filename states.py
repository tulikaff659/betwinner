from aiogram.fsm.state import State, StatesGroup

class SignalStates(StatesGroup):
    waiting_for_bet_id = State()
    waiting_for_game_start = State()
    waiting_for_game_continue = State()

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_apk_url = State()
    waiting_for_balance_amount = State()
    waiting_for_remove_apk = State()
