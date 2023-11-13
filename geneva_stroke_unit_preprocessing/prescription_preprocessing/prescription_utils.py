import re

import pandas as pd


def remove_pharma_drug_name(x):
    word_list = x.split(' ')
    if ('cp' in x) or ('inject' in x):
        if len(word_list) < 4:
            return word_list[0]
        elif len(word_list) < 6:
            return ' '.join(word_list[:3])
        else:
            return ' '.join(word_list[:3])

    else:
        return x


# filter out instructions with multiple dates
def count_dates_occurrences(s):
    s = s.condition
    pattern = re.compile(r'\b\d{2}\.\d{2}\b')
    matches = pattern.findall(s)

    if len(matches) > 1:
        return True
    else:
        return False


def create_intervals(start_date, end_date, interval, datetime_format='%d.%m.%Y %H:%M'):
    """
    Creates a list of intervals of length interval (in minutes) between start_date and end_date
    :param start_date:
    :param end_date: included if at least half of the last interval is included
    :param interval: time interval in minutes
    :param datetime_format:
    :return:
    """
    intervals = []
    start_date = pd.to_datetime(start_date, format=datetime_format)
    end_date = pd.to_datetime(end_date, format=datetime_format)
    current_date = start_date
    # create an interval for every timestep until end_date (included only if at least half of the interval is included)
    while current_date < end_date - pd.Timedelta(minutes=interval/2):
        intervals.append(current_date)
        current_date = current_date + pd.Timedelta(minutes=interval)
    return pd.Series(intervals)


def get_prescription_end_date(end_date, stop_date, datetime_format='%d.%m.%Y %H:%M'):
    """
    Returns the end date of a prescription, which is the earliest of end_date and stop_date
    :param end_date:
    :param stop_date:
    :param datetime_format:
    :return:
    """
    end_date = pd.to_datetime(end_date, format=datetime_format)
    stop_date = pd.to_datetime(stop_date, format=datetime_format)
    # return whichever is earlier
    if end_date < stop_date:
        return end_date
    else:
        return stop_date