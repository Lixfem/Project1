from datetime import date, timedelta

def default_validity_date():
    return date.today() + timedelta(days=30)