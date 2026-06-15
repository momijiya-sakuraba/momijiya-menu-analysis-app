from __future__ import annotations

import pandas as pd
import streamlit as st


def department_sales_bar(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("表示できる部門データがありません。")
        return
    chart_data = dataframe.groupby("部門名", as_index=True)["純売上"].sum().sort_values(ascending=False)
    st.bar_chart(chart_data)


def department_share_bar(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("表示できる構成比データがありません。")
        return
    chart_data = dataframe.groupby("部門名", as_index=True)["構成比"].sum().sort_values(ascending=True)
    st.bar_chart(chart_data)


def product_top_bar(dataframe: pd.DataFrame, value_column: str) -> None:
    if dataframe.empty:
        st.info("表示できる商品データがありません。")
        return
    chart_data = dataframe.set_index("商品名")[value_column].sort_values(ascending=True)
    st.bar_chart(chart_data)


def pie_chart(dataframe: pd.DataFrame, label_column: str, value_column: str, title: str = "") -> None:
    if dataframe.empty or label_column not in dataframe or value_column not in dataframe:
        st.info("表示できる構成比データがありません。")
        return

    chart_data = dataframe[[label_column, value_column]].copy()
    chart_data[value_column] = pd.to_numeric(chart_data[value_column], errors="coerce").fillna(0)
    chart_data = chart_data[chart_data[value_column] > 0]
    if chart_data.empty:
        st.info("表示できる構成比データがありません。")
        return

    spec = {
        "mark": {"type": "arc", "innerRadius": 45, "stroke": "#111827"},
        "encoding": {
            "theta": {"field": value_column, "type": "quantitative"},
            "color": {
                "field": label_column,
                "type": "nominal",
                "legend": {"orient": "bottom", "columns": 2},
            },
            "tooltip": [
                {"field": label_column, "type": "nominal", "title": label_column},
                {"field": value_column, "type": "quantitative", "title": value_column, "format": ",.0f"},
            ],
        },
        "view": {"stroke": None},
        "height": 260,
    }
    if title:
        spec["title"] = title
    st.vega_lite_chart(chart_data, spec, use_container_width=True)


def top_share_pie(dataframe: pd.DataFrame, label_column: str, value_column: str, limit: int = 8, title: str = "") -> None:
    if dataframe.empty or label_column not in dataframe or value_column not in dataframe:
        st.info("表示できる構成比データがありません。")
        return

    chart_data = dataframe[[label_column, value_column]].copy()
    chart_data[value_column] = pd.to_numeric(chart_data[value_column], errors="coerce").fillna(0)
    chart_data = chart_data[chart_data[value_column] > 0].sort_values(value_column, ascending=False)
    if chart_data.empty:
        st.info("表示できる構成比データがありません。")
        return

    top = chart_data.head(limit).copy()
    other_value = chart_data.iloc[limit:][value_column].sum()
    if other_value > 0:
        top = pd.concat(
            [top, pd.DataFrame([{label_column: "その他", value_column: other_value}])],
            ignore_index=True,
        )
    pie_chart(top, label_column, value_column, title)
