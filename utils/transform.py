from __future__ import annotations

import pandas as pd
import streamlit as st

from .metrics import average_price, change_amount, change_rate


CACHE_TTL_SECONDS = 21600
STORE_OPTIONS = ["全店", "飯田橋店", "神田店", "東池袋店"]
DELIVERY_KEYWORDS = ["デリバリー", "ubereats", "uber eats", "出前館", "wolt"]


def previous_month(month: str) -> str:
    return (pd.Period(month, freq="M") - 1).strftime("%Y-%m")


def previous_year_month(month: str) -> str:
    return (pd.Period(month, freq="M") - 12).strftime("%Y-%m")


def filter_by_store_month(dataframe: pd.DataFrame, store_name: str, month: str | None) -> pd.DataFrame:
    filtered = dataframe
    if month:
        filtered = filtered[filtered["集計月"] == month]
    if store_name != "全店":
        filtered = filtered[filtered["店舗名"] == store_name]
    return filtered.copy()


def exclude_delivery_rows(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()

    pattern = "|".join(DELIVERY_KEYWORDS)
    product_name = dataframe.get("商品名", pd.Series("", index=dataframe.index)).astype(str).str.lower()
    department_name = dataframe.get("部門名", pd.Series("", index=dataframe.index)).astype(str).str.lower()
    delivery_mask = product_name.str.contains(pattern, na=False) | department_name.str.contains(pattern, na=False)
    return dataframe.loc[~delivery_mask].copy()


def _sum_values(dataframe: pd.DataFrame) -> dict[str, float]:
    return {
        "純売上": float(dataframe["純売上"].sum()) if "純売上" in dataframe else 0,
        "販売数量": float(dataframe["販売数量"].sum()) if "販売数量" in dataframe else 0,
        "取引数": float(dataframe["取引数"].sum()) if "取引数" in dataframe else 0,
    }


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def monthly_summary(departments: pd.DataFrame, selected_month: str) -> tuple[dict[str, float | str | None], pd.DataFrame]:
    current = departments[departments["集計月"] == selected_month].copy()
    prev_month = previous_month(selected_month)
    prev_year = previous_year_month(selected_month)
    prev = departments[departments["集計月"] == prev_month].copy()
    year = departments[departments["集計月"] == prev_year].copy()

    totals = _sum_values(current)
    prev_totals = _sum_values(prev)
    year_totals = _sum_values(year)

    kpis: dict[str, float | str | None] = {
        "集計月": selected_month,
        "純売上": totals["純売上"],
        "販売数量": totals["販売数量"],
        "取引数": totals["取引数"],
        "平均単価": average_price(totals["純売上"], totals["販売数量"]),
        "前月": prev_month,
        "前月純売上": prev_totals["純売上"],
        "前月比": change_rate(totals["純売上"], prev_totals["純売上"]),
        "前年同月": prev_year,
        "前年同月純売上": year_totals["純売上"],
        "前年同月比": change_rate(totals["純売上"], year_totals["純売上"]),
    }

    store_current = _store_month_totals(current, selected_month)
    store_prev = _store_month_totals(prev, prev_month).rename(columns={"純売上": "前月純売上"})
    store_year = _store_month_totals(year, prev_year).rename(columns={"純売上": "前年同月純売上"})

    summary = store_current.merge(store_prev[["店舗名", "前月純売上"]], on="店舗名", how="left")
    summary = summary.merge(store_year[["店舗名", "前年同月純売上"]], on="店舗名", how="left")
    summary[["前月純売上", "前年同月純売上"]] = summary[["前月純売上", "前年同月純売上"]].fillna(0)
    summary["前月比"] = summary.apply(lambda row: change_rate(row["純売上"], row["前月純売上"]), axis=1)
    summary["前年同月比"] = summary.apply(lambda row: change_rate(row["純売上"], row["前年同月純売上"]), axis=1)
    return kpis, summary


def _store_month_totals(dataframe: pd.DataFrame, month: str) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame(columns=["集計月", "店舗名", "純売上", "販売数量", "取引数", "平均単価"])
    grouped = (
        dataframe.groupby("店舗名", as_index=False)[["純売上", "販売数量", "取引数"]]
        .sum()
        .sort_values("純売上", ascending=False)
    )
    grouped.insert(0, "集計月", month)
    grouped["平均単価"] = grouped.apply(lambda row: average_price(row["純売上"], row["販売数量"]), axis=1)
    return grouped


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def department_analysis(departments: pd.DataFrame, store_name: str, selected_month: str) -> pd.DataFrame:
    current = filter_by_store_month(departments, store_name, selected_month)
    prev = filter_by_store_month(departments, store_name, previous_month(selected_month))
    year = filter_by_store_month(departments, store_name, previous_year_month(selected_month))

    grouped = _group_department(current)
    prev_grouped = _group_department(prev).rename(columns={"純売上": "前月純売上"})
    year_grouped = _group_department(year).rename(columns={"純売上": "前年同月純売上"})

    merged = grouped.merge(prev_grouped[["店舗名", "部門名", "前月純売上"]], on=["店舗名", "部門名"], how="left")
    merged = merged.merge(year_grouped[["店舗名", "部門名", "前年同月純売上"]], on=["店舗名", "部門名"], how="left")
    merged[["前月純売上", "前年同月純売上"]] = merged[["前月純売上", "前年同月純売上"]].fillna(0)
    total_sales = merged["純売上"].sum()
    merged["構成比"] = merged["純売上"] / total_sales if total_sales else 0
    merged["前月比"] = merged.apply(lambda row: change_rate(row["純売上"], row["前月純売上"]), axis=1)
    merged["前年同月比"] = merged.apply(lambda row: change_rate(row["純売上"], row["前年同月純売上"]), axis=1)
    merged.insert(0, "集計月", selected_month)
    return merged.sort_values("純売上", ascending=False)


def _group_department(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame(columns=["店舗名", "部門名", "販売数量", "純売上", "取引数"])
    return dataframe.groupby(["店舗名", "部門名"], as_index=False)[["販売数量", "純売上", "取引数"]].sum()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def product_top(
    products: pd.DataFrame,
    store_name: str,
    selected_month: str,
    limit: int,
    sort_by: str,
    exclude_delivery: bool = True,
) -> pd.DataFrame:
    current = filter_by_store_month(products, store_name, selected_month)
    if exclude_delivery:
        current = exclude_delivery_rows(current)
    if current.empty:
        return pd.DataFrame()

    grouped = (
        current.groupby(["店舗名", "商品名", "部門名"], as_index=False)[["販売数量", "純売上", "取引数"]]
        .sum()
    )
    grouped["平均単価"] = grouped.apply(lambda row: average_price(row["純売上"], row["販売数量"]), axis=1)
    total_sales = grouped["純売上"].sum()
    grouped["構成比"] = grouped["純売上"] / total_sales if total_sales else 0
    grouped = grouped.sort_values(sort_by, ascending=False).head(limit).reset_index(drop=True)
    grouped.insert(0, "順位", grouped.index + 1)
    return grouped


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def abc_analysis(products: pd.DataFrame, store_name: str, selected_month: str, exclude_delivery: bool = True) -> pd.DataFrame:
    current = product_top(products, store_name, selected_month, 100000, "純売上", exclude_delivery)
    if current.empty:
        return current
    total_sales = current["純売上"].sum()
    current["構成比"] = current["純売上"] / total_sales if total_sales else 0
    current["累計構成比"] = current["構成比"].cumsum()
    current["ABC区分"] = current["累計構成比"].map(_abc_label)
    return current


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def product_change_ranking(
    products: pd.DataFrame,
    store_name: str,
    selected_month: str,
    compare_month: str,
    exclude_delivery: bool = True,
) -> pd.DataFrame:
    current = _product_totals_for_month(products, store_name, selected_month, exclude_delivery)
    compare = _product_totals_for_month(products, store_name, compare_month, exclude_delivery).rename(
        columns={"純売上": "比較月純売上", "販売数量": "比較月販売数量"}
    )

    merged = current.rename(columns={"純売上": "選択月純売上", "販売数量": "選択月販売数量"}).merge(
        compare[["店舗名", "商品名", "部門名", "比較月純売上", "比較月販売数量"]],
        on=["店舗名", "商品名", "部門名"],
        how="outer",
    )
    if merged.empty:
        return merged

    merged[["選択月純売上", "選択月販売数量", "比較月純売上", "比較月販売数量"]] = merged[
        ["選択月純売上", "選択月販売数量", "比較月純売上", "比較月販売数量"]
    ].fillna(0)
    merged[["店舗名", "商品名", "部門名"]] = merged[["店舗名", "商品名", "部門名"]].fillna("")
    merged["増減額"] = merged.apply(lambda row: change_amount(row["選択月純売上"], row["比較月純売上"]), axis=1)
    merged["増減率"] = merged.apply(lambda row: change_rate(row["選択月純売上"], row["比較月純売上"]), axis=1)
    merged["数量増減"] = merged["選択月販売数量"] - merged["比較月販売数量"]
    merged["状態"] = merged.apply(_change_status, axis=1)
    return merged


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def store_product_comparison(products: pd.DataFrame, selected_month: str, exclude_delivery: bool = True) -> pd.DataFrame:
    current = products[products["集計月"] == selected_month].copy()
    if exclude_delivery:
        current = exclude_delivery_rows(current)
    if current.empty:
        return pd.DataFrame()

    grouped = current.groupby(["商品名", "部門名", "店舗名"], as_index=False)["純売上"].sum()
    pivot = grouped.pivot_table(index=["商品名", "部門名"], columns="店舗名", values="純売上", aggfunc="sum", fill_value=0)
    for store in ["飯田橋店", "神田店", "東池袋店"]:
        if store not in pivot.columns:
            pivot[store] = 0
    pivot = pivot.reset_index()
    pivot["全店純売上"] = pivot[["飯田橋店", "神田店", "東池袋店"]].sum(axis=1)
    store_columns = ["飯田橋店", "神田店", "東池袋店"]
    pivot["最大店舗"] = pivot[store_columns].idxmax(axis=1)
    pivot["最小店舗"] = pivot[store_columns].idxmin(axis=1)
    pivot["最大/最小差額"] = pivot[store_columns].max(axis=1) - pivot[store_columns].min(axis=1)
    pivot["活用メモ"] = pivot.apply(_product_gap_note, axis=1)
    return pivot.sort_values(["最大/最小差額", "全店純売上"], ascending=False)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def store_department_comparison(departments: pd.DataFrame, selected_month: str) -> pd.DataFrame:
    current = departments[departments["集計月"] == selected_month].copy()
    if current.empty:
        return pd.DataFrame()
    grouped = current.groupby(["部門名", "店舗名"], as_index=False)["純売上"].sum()
    pivot = grouped.pivot_table(index="部門名", columns="店舗名", values="純売上", aggfunc="sum", fill_value=0)
    for store in ["飯田橋店", "神田店", "東池袋店"]:
        if store not in pivot.columns:
            pivot[store] = 0
    pivot = pivot.reset_index()
    pivot["全店純売上"] = pivot[["飯田橋店", "神田店", "東池袋店"]].sum(axis=1)
    return pivot.sort_values("全店純売上", ascending=False)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def improvement_candidates(
    products: pd.DataFrame,
    store_name: str,
    selected_month: str,
    exclude_delivery: bool = True,
) -> dict[str, pd.DataFrame]:
    abc = abc_analysis(products, store_name, selected_month, exclude_delivery)
    store_compare = store_product_comparison(products, selected_month, exclude_delivery)
    prev = product_change_ranking(products, store_name, selected_month, previous_month(selected_month), exclude_delivery)

    c_candidates = pd.DataFrame()
    pop_candidates = pd.DataFrame()
    recommend_candidates = pd.DataFrame()

    if not abc.empty:
        c_candidates = abc[(abc["ABC区分"] == "C") & (abc["販売数量"] <= max(5, abc["販売数量"].quantile(0.35)))].copy()
        c_candidates["確認メモ"] = "低販売のC商品。季節品・限定品・コース内訳か確認"

        b_products = abc[abc["ABC区分"] == "B"].copy()
        if not prev.empty:
            growth = prev[["店舗名", "商品名", "部門名", "増減額", "増減率"]]
            b_products = b_products.merge(growth, on=["店舗名", "商品名", "部門名"], how="left")
        pop_candidates = b_products.sort_values(["平均単価", "純売上"], ascending=False).head(20).copy()
        pop_candidates["確認メモ"] = "B商品。おすすめ・POP・声かけで伸ばせるか確認"

    if not store_compare.empty and store_name != "全店":
        selected_store_sales = store_compare[store_name]
        strongest_store_sales = store_compare[["飯田橋店", "神田店", "東池袋店"]].max(axis=1)
        recommend_candidates = store_compare[
            (store_compare["全店純売上"] > store_compare["全店純売上"].quantile(0.5))
            & (selected_store_sales < strongest_store_sales * 0.5)
        ].copy()
        recommend_candidates["確認メモ"] = "他店で強い。おすすめ強化・横展開候補"
        recommend_candidates = recommend_candidates.sort_values("最大/最小差額", ascending=False).head(20)

    return {
        "recommend": recommend_candidates,
        "c_candidates": c_candidates.head(20),
        "pop": pop_candidates.head(20),
    }


def _product_totals_for_month(
    products: pd.DataFrame,
    store_name: str,
    month: str,
    exclude_delivery: bool,
) -> pd.DataFrame:
    current = filter_by_store_month(products, store_name, month)
    if exclude_delivery:
        current = exclude_delivery_rows(current)
    if current.empty:
        return pd.DataFrame(columns=["店舗名", "商品名", "部門名", "販売数量", "純売上", "取引数"])
    return current.groupby(["店舗名", "商品名", "部門名"], as_index=False)[["販売数量", "純売上", "取引数"]].sum()


def _change_status(row: pd.Series) -> str:
    current_sales = float(row["選択月純売上"])
    compare_sales = float(row["比較月純売上"])
    if compare_sales == 0 and current_sales > 0:
        return "新規/復活"
    if compare_sales > 0 and current_sales == 0:
        return "選択月なし"
    if compare_sales == 0 and current_sales == 0:
        return "売上なし"
    return "継続"


def _product_gap_note(row: pd.Series) -> str:
    sales_values = [float(row["飯田橋店"]), float(row["神田店"]), float(row["東池袋店"])]
    total_sales = float(row["全店純売上"])
    if total_sales <= 0:
        return "低販売。整理候補"
    if min(sales_values) > 0 and max(sales_values) / max(min(sales_values), 1) < 2:
        return "全店で強い。定番主力商品"
    if max(sales_values) > total_sales * 0.7:
        return "店舗限定で強い。理由確認"
    if max(sales_values) >= 50000 and min(sales_values) <= max(sales_values) * 0.3:
        return "他店で強い。おすすめ強化候補"
    return "店舗差あり。展開方法を確認"


def _abc_label(cumulative_share: float) -> str:
    if cumulative_share <= 0.7:
        return "A"
    if cumulative_share <= 0.9:
        return "B"
    return "C"
