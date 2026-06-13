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
