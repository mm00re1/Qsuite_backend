def parse_time_to_cron(time_str: str) -> str:
    ##Converts a time string in 'HH:MM' format to cron minute and hour fields.
    try:
        hour, minute = map(int, time_str.split(':'))
        return f"{minute} {hour}"
    except ValueError as e:
        logging.error(f"Invalid time format '{time_str}': {e}")
        return None
