import re
from datetime import date, datetime


def clean_txt(text) -> str | None:
    """Supprime les balises HTML et normalise les espaces."""
    if not text:
        return None
    clean = re.sub(r'<[^>]+>', '', str(text))
    return " ".join(clean.split()).strip()


def normalize_date(date_val) -> date | None:
    """Convertit les dates (YYYY ou YYYY-MM-DD) en objet date Python."""
    if not date_val:
        return None
    try:
        date_str = str(date_val).strip()
        if len(date_str) == 4:
            return datetime.strptime(f"{date_str}-01-01", "%Y-%m-%d").date()
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
