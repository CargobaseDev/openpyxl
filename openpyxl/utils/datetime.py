from __future__ import division
# Copyright (c) 2010-2021 openpyxl

"""Manage Excel date weirdness."""

# Python stdlib imports
import datetime
from datetime import timedelta, tzinfo
from math import isnan
import re


# constants
MAC_EPOCH = datetime.datetime(1904, 1, 1)
WINDOWS_EPOCH = datetime.datetime(1899, 12, 30)
CALENDAR_WINDOWS_1900 = 2415018.5   # Julian date of WINDOWS_EPOCH
CALENDAR_MAC_1904 = 2416480.5       # Julian date of MAC_EPOCH
SECS_PER_DAY = 86400

EPOCH = datetime.datetime.utcfromtimestamp(0)
ISO_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
ISO_REGEX = re.compile(r'''
(?P<date>(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}))?T?
(?P<time>(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?P<ms>\.\d{1,3})?)?Z?''',
                                       re.VERBOSE)


def to_ISO8601(dt):
    """Convert from a datetime to a timestamp string."""
    return datetime.datetime.strftime(dt, ISO_FORMAT)


def from_ISO8601(formatted_string):
    """Convert from a timestamp string to a datetime object. According to
    18.17.4 in the specification the following ISO 8601 formats are
    supported.

    Dates B.1.1 and B.2.1
    Times B.1.2 and B.2.2
    Datetimes B.1.3 and B.2.3

    There is no concept of timedeltas
    """

    match = ISO_REGEX.match(formatted_string)
    if not match:
        raise ValueError("Invalid datetime value {}".format(formatted_string))

    parts = match.groupdict()
    for key in ["year", "month", "day", "hour", "minute", "second"]:
        if parts[key]:
            parts[key] = int(parts[key])
    if not parts["date"]:
        dt = datetime.time(parts['hour'], parts['minute'], parts['second'])
    elif not parts["time"]:
        dt = datetime.date(parts['year'], parts['month'], parts['day'])
    else:
        dt = datetime.datetime(year=parts['year'], month=parts['month'],
                               day=parts['day'], hour=parts['hour'], minute=parts['minute'],
                               second=parts['second'])
    if parts["ms"]:
        ms = float(parts['ms']) * 1_000_000
        dt += timedelta(microseconds=ms)
    return dt


def to_excel(dt, offset=CALENDAR_WINDOWS_1900):
    if isinstance(dt, datetime.time):
        return time_to_days(dt)
    if isinstance(dt, datetime.timedelta):
        return timedelta_to_days(dt)
    if isnan(dt.year): # Pandas supports Not a Date
        return
    epoch = offset == CALENDAR_WINDOWS_1900 and WINDOWS_EPOCH or MAC_EPOCH
    jul = (datetime.datetime(dt.year, dt.month, dt.day) - epoch).days
    if jul <= 60 and offset == CALENDAR_WINDOWS_1900:
        jul -= 1
    if hasattr(dt, 'time'):
        jul += time_to_days(dt)
    return jul


def from_excel(value, offset=CALENDAR_WINDOWS_1900):
    if value is None:
        return
    day, fraction = divmod(value, 1)
    diff = datetime.timedelta(milliseconds=round(fraction * SECS_PER_DAY * 1000.))
    if 0 <= value < 1 and diff.days == 0:
        return days_to_time(diff)
    if 1 < value < 60 and offset == CALENDAR_WINDOWS_1900:
        day += 1
    epoch = offset == CALENDAR_WINDOWS_1900 and WINDOWS_EPOCH or MAC_EPOCH
    return epoch + datetime.timedelta(days=day) + diff


class GMT(tzinfo):

    def utcoffset(self, dt):
        return timedelta(0)

    def dst(self, dt):
        return timedelta(0)

    def tzname(self,dt):
        return "GMT"

try:
    from datetime import timezone
    UTC = timezone(timedelta(0))
except ImportError:
    # Python 2
    UTC = GMT()


def time_to_days(value):
    """Convert a time value to fractions of day"""
    if value.tzinfo is not None:
        value = value.astimezone(UTC)
    return (
        (value.hour * 3600)
        + (value.minute * 60)
        + value.second
        + value.microsecond / 10**6
        ) / SECS_PER_DAY


def timedelta_to_days(value):
    """Convert a timedelta value to fractions of a day"""
    if not hasattr(value, 'total_seconds'):
        secs = (value.microseconds +
                (value.seconds + value.days * SECS_PER_DAY) * 10**6) / 10**6
    else:
        secs = value.total_seconds()
    return secs / SECS_PER_DAY


def days_to_time(value):
    mins, seconds = divmod(value.seconds, 60)
    hours, mins = divmod(mins, 60)
    return datetime.time(hours, mins, seconds, value.microseconds)
