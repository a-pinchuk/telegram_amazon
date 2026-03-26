from aiogram.fsm.state import State, StatesGroup


class DailyReportFSM(StatesGroup):
    # Step 1a: Processed listings
    select_processed_countries = State()
    enter_processed_count = State()

    # Step 1b: Published listings
    select_published_countries = State()
    enter_published_count = State()

    # Step 1c: Blocked listings
    select_blocked_countries = State()
    enter_blocked_count = State()
    enter_block_reason = State()

    # Step 2: Instructions
    enter_total_instructions = State()
    select_instruction_countries = State()
    enter_instruction_count = State()

    # Confirmation
    confirm_report = State()


class EditReportFSM(StatesGroup):
    select_processed_countries = State()
    enter_processed_count = State()
    select_published_countries = State()
    enter_published_count = State()
    select_blocked_countries = State()
    enter_blocked_count = State()
    enter_block_reason = State()
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
