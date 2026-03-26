from aiogram.fsm.state import State, StatesGroup


class DailyReportFSM(StatesGroup):
    # Step 1: Listings
    select_listing_countries = State()
    enter_listing_count = State()

    # Step 2: Instructions
    enter_total_instructions = State()
    select_instruction_countries = State()
    enter_instruction_count = State()

    # Confirmation
    confirm_report = State()


class EditReportFSM(StatesGroup):
    select_listing_countries = State()
    enter_listing_count = State()
    enter_total_instructions = State()
    select_instruction_countries = State()
    enter_instruction_count = State()
    confirm_report = State()


class AdminReportFSM(StatesGroup):
    select_period = State()
    enter_start_date = State()
    enter_end_date = State()
    select_employee = State()


class AddUserFSM(StatesGroup):
    enter_telegram_id = State()
    enter_name = State()
