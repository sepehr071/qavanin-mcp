"""Text helpers shared by the tool modules."""

import html
import re

_TAG = re.compile(r"<[^>]*>")
_YEH_KAF = str.maketrans({"ي": "ی", "ك": "ک"})  # the site stores Arabic letters; users type Persian ones
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def fa(s: str) -> str:
    """Arabic ي/ك to Persian ی/ک."""
    return s.translate(_YEH_KAF)


def ascii_digits(s: str) -> str:
    return s.translate(_DIGITS)


def plain(fragment: str) -> str:
    """HTML fragment to plain text: <br> becomes a newline, tags go, entities decode, spaces collapse."""
    s = html.unescape(_TAG.sub("", re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)))
    s = re.sub(r"[ \t\r\f\v ]+", " ", s)
    return fa("\n".join(line.strip() for line in s.split("\n")).strip())


def one_line(fragment: str) -> str:
    return re.sub(r"\s+", " ", plain(fragment)).strip()
