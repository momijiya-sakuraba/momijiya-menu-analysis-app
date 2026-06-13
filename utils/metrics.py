from __future__ import annotations

import pandas as pd


def average_price(sales: float, quantity: float) -> float:
    if quantity in (0, None) or pd.isna(quantity):
        return 0.0
    return float(sales) / float(quantity)


def change_amount(current: float, previous: float) -> float:
    return float(current or 0) - float(previous or 0)


def change_rate(current: float, previous: float) -> float | None:
    previous_value = float(previous or 0)
    if previous_value == 0:
        return None
    return (float(current or 0) - previous_value) / previous_value


def format_yen(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        value = 0
    return f"{float(value):,.0f}円"


def format_signed_yen(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        value = 0
    return f"{float(value):+,.0f}円"


def format_number(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        value = 0
    return f"{float(value):,.0f}"


def format_percent(value: float | int | None, missing_label: str = "-") -> str:
    if value is None or pd.isna(value):
        return missing_label
    return f"{float(value) * 100:+.1f}%"


def format_share(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "0.0%"
    return f"{float(value) * 100:.1f}%"


def add_display_formats(dataframe: pd.DataFrame, columns: dict[str, str]) -> pd.DataFrame:
    formatted = dataframe.copy()
    for column, kind in columns.items():
        if column not in formatted.columns:
            continue
        if kind == "yen":
            formatted[column] = formatted[column].map(format_yen)
        elif kind == "signed_yen":
            formatted[column] = formatted[column].map(format_signed_yen)
        elif kind == "number":
            formatted[column] = formatted[column].map(format_number)
        elif kind == "percent":
            formatted[column] = formatted[column].map(format_percent)
        elif kind == "share":
            formatted[column] = formatted[column].map(format_share)
    return formatted
