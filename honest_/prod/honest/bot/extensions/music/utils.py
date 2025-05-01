from typing import Union


def pluralize(text: str, count: int) -> str:
    """
    Pluralize a string based on the count.

    Args:
        text (str): The string to pluralize.
        count (int): The count to determine if the string should be pluralized.

    Returns:
        str: The pluralized string.
    """
    return text + ("s" if count != 1 else "")


def format_duration(time_input: Union[int, float], is_milliseconds: bool = True) -> str:
    """
    Convert a given duration (in seconds or milliseconds) into a formatted duration string.

    Args:
        time_input (Union[int, float]): The total duration, either in seconds or milliseconds.
        is_milliseconds (bool): Specifies if the input is in milliseconds (default is True).

    Returns:
        str: The formatted duration in hours, minutes, seconds, and milliseconds.
    """
    if is_milliseconds:
        total_seconds = time_input / 1000
    else:
        total_seconds = time_input

    seconds = int(total_seconds)

    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"
