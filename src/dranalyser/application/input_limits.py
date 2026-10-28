"""Validate values before binding them to SQLite's signed integer parameters."""


def database_revision(value):
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise ValueError('Revision must be an integer from 1 to 2147483647.')
    return value
