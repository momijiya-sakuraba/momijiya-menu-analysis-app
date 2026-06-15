from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.charts import department_sales_bar, department_share_bar, pie_chart, product_top_bar, top_share_pie
from utils.metrics import (
    add_display_formats,
    format_number,
    format_percent,
    format_share,
    format_signed_yen,
    format_yen,
)
from utils.sheets import get_filter_options, get_spreadsheet_id, load_sales_data
from utils.transform import (
    STORE_OPTIONS,
    abc_analysis,
    course_analysis,
    department_analysis,
    exclude_delivery_rows,
    food_drink_mix,
    improvement_candidates,
    lunch_analysis,
    monthly_summary,
    product_top,
    product_quantity_with_course,
    product_change_ranking,
    previous_month,
    previous_year_month,
    store_department_comparison,
    store_product_comparison,
)


st.set_page_config(page_title="商品・部門分析アプリ", page_icon="M", layout="wide")


def main() -> None:
    st.title("商品・部門分析アプリ")
    st.caption("もみじ屋専用。商品別売上・部門別売上だけを読み込む軽量分析アプリです。")

    with st.sidebar:
        st.header("条件")
        if st.button("キャッシュクリア", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("キャッシュをクリアしました。画面を再読み込みしてください。")

    try:
        spreadsheet_id = get_spreadsheet_id()
        sales_data = load_sales_data(spreadsheet_id)
        options = get_filter_options(sales_data.products, sales_data.departments)
    except Exception as exc:
        st.error("Google Sheetsの読み込みに失敗しました。認証情報、共有設定、シート名を確認してください。")
        st.warning(
            "ローカル実行では `.streamlit/secrets.toml` が必要です。"
            "サービスアカウントの `client_email` に対象スプレッドシートの閲覧権限も付与してください。"
        )
        with st.expander("詳細"):
            st.exception(exc)
        st.stop()

    if not options["months"]:
        st.error("集計月が見つかりません。商品別売上・部門別売上のデータを確認してください。")
        st.stop()

    latest_month = options["months"][-1]
    custom_compare_month = options["months"][max(0, len(options["months"]) - 2)]
    with st.sidebar:
        store_name = st.selectbox("店舗選択", STORE_OPTIONS, index=0)
        month = st.selectbox("月選択", options["months"], index=options["months"].index(latest_month))
        compare_mode = st.radio("比較対象月", ["前月", "前年同月", "任意の月"], index=0)
        if compare_mode == "任意の月":
            custom_compare_month = st.selectbox("任意の比較月", options["months"], index=max(0, len(options["months"]) - 2))
        display_limit = st.selectbox("表示件数", [10, 20, 50, 100], index=1)
        exclude_delivery = st.checkbox("商品分析からデリバリー売上を除外", value=True)

    last_updated = _latest_updated_at(sales_data.products, sales_data.departments)
    st.info(
        f"最新月: {latest_month} / 選択月: {month} / データ更新日時: {last_updated} / "
        "初期表示では重い全商品一覧を表示しません。"
    )

    kpis, store_summary = monthly_summary(sales_data.departments, month)
    _show_kpis(kpis)

    analysis = st.radio(
        "分析タブ",
        ["概要", "月次サマリー", "部門分析", "商品TOP分析", "コース分析", "ランチ分析", "ABC分析", "前月比・前年比ランキング", "店舗間比較", "改善候補"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if analysis == "概要":
        show_overview(sales_data.products, sales_data.departments, store_name, month, exclude_delivery)
    elif analysis == "月次サマリー":
        show_monthly_summary(store_summary)
    elif analysis == "部門分析":
        show_department_analysis(sales_data.departments, store_name, month)
    elif analysis == "商品TOP分析":
        show_product_top(sales_data.products, store_name, month, display_limit, exclude_delivery)
    elif analysis == "コース分析":
        show_course_analysis(sales_data.products, store_name, month, display_limit, exclude_delivery)
    elif analysis == "ランチ分析":
        show_lunch_analysis(sales_data.products, store_name, month, display_limit, exclude_delivery)
    elif analysis == "ABC分析":
        show_abc_analysis(sales_data.products, store_name, month, display_limit, exclude_delivery)
    elif analysis == "前月比・前年比ランキング":
        show_change_rankings(
            sales_data.products,
            store_name,
            month,
            display_limit,
            exclude_delivery,
            compare_mode,
            custom_compare_month,
        )
    elif analysis == "店舗間比較":
        show_store_comparison(sales_data.products, sales_data.departments, month, display_limit, exclude_delivery)
    elif analysis == "改善候補":
        show_improvement_candidates(sales_data.products, store_name, month, display_limit, exclude_delivery)

    st.caption(
        "注意: 商品名・商品コード・部門名の変更があると別商品/別部門として扱われる場合があります。"
        "原価が空欄または0の場合、粗利関連は参考値です。"
    )


def _show_kpis(kpis: dict[str, float | str | None]) -> None:
    columns = st.columns(5)
    columns[0].metric("純売上", format_yen(kpis["純売上"]))
    columns[1].metric("販売数量", format_number(kpis["販売数量"]))
    columns[2].metric("取引数", format_number(kpis["取引数"]))
    columns[3].metric("平均単価", format_yen(kpis["平均単価"]))
    columns[4].metric("前月比", format_percent(kpis["前月比"]))

    sub_columns = st.columns(2)
    sub_columns[0].caption(f"前月 {kpis['前月']}: {format_yen(kpis['前月純売上'])}")
    sub_columns[1].caption(
        f"前年同月 {kpis['前年同月']}: {format_yen(kpis['前年同月純売上'])} / {format_percent(kpis['前年同月比'])}"
    )


def show_overview(products: pd.DataFrame, departments: pd.DataFrame, store_name: str, month: str, exclude_delivery: bool) -> None:
    st.subheader("概要")
    st.caption("まず部門の大きな変化を見てから、商品TOPで具体的な商品を確認します。")

    scoped_products = products[products["集計月"] == month].copy()
    scoped_departments = departments[departments["集計月"] == month].copy()
    if store_name != "全店":
        scoped_products = scoped_products[scoped_products["店舗名"] == store_name]
        scoped_departments = scoped_departments[scoped_departments["店舗名"] == store_name]

    product_rows_before = len(scoped_products)
    scoped_products_for_analysis = exclude_delivery_rows(scoped_products) if exclude_delivery else scoped_products
    product_rows_after = len(scoped_products_for_analysis)
    department_count = scoped_departments["部門名"].nunique() if not scoped_departments.empty else 0

    cols = st.columns(4)
    cols[0].metric("商品行数", format_number(product_rows_after))
    cols[1].metric("除外した行数", format_number(product_rows_before - product_rows_after))
    cols[2].metric("部門数", format_number(department_count))
    cols[3].metric("商品分析", "デリバリー除外" if exclude_delivery else "デリバリー含む")

    st.markdown("#### 今月の注目ポイント")
    _show_decision_dashboard(products, departments, store_name, month, exclude_delivery)

    st.markdown("#### 今日見る順番")
    st.write("1. 概要で今月の注目ポイントを確認")
    st.write("2. 部門分析でフード/ドリンク比と部門構成を見る")
    st.write("3. 商品TOP分析で主力商品とコース込み販売点数を確認")
    st.write("4. コース分析・ランチ分析で、宴会/ランチの中身を確認")
    st.write("5. 改善候補でおすすめ強化・整理確認・POP候補を決める")

    st.markdown("#### この画面の前提")
    st.write("月次サマリーと部門分析は売上全体を見るため、デリバリーも含めます。")
    st.write("商品TOP分析とABC分析は商品判断をしやすくするため、初期設定でデリバリーを除外します。")


def show_monthly_summary(store_summary: pd.DataFrame) -> None:
    st.subheader("月次サマリー")
    st.caption("店舗別の状況確認です。商品別集計と差がある場合は、部門別売上を月次総額の基準にします。")
    if store_summary.empty:
        st.warning("選択月の部門別売上がありません。")
        return
    display = add_display_formats(
        store_summary,
        {
            "純売上": "yen",
            "販売数量": "number",
            "取引数": "number",
            "平均単価": "yen",
            "前月純売上": "yen",
            "前月比": "percent",
            "前年同月純売上": "yen",
            "前年同月比": "percent",
        },
    )
    st.dataframe(display, use_container_width=True, hide_index=True)


def _show_decision_dashboard(products: pd.DataFrame, departments: pd.DataFrame, store_name: str, month: str, exclude_delivery: bool) -> None:
    mix = food_drink_mix(departments, store_name, month)["mix"]
    lunch = lunch_analysis(products, store_name, month, exclude_delivery)
    course = course_analysis(products, store_name, month, exclude_delivery)
    top_sales = product_top(products, store_name, month, 5, "純売上", exclude_delivery)
    quantity = product_quantity_with_course(products, store_name, month, 5, exclude_delivery)

    drink_share = 0.0
    food_share = 0.0
    if not mix.empty:
        total_sales = float(mix["合計純売上"].sum())
        if total_sales:
            drink_share = float(mix["ドリンク"].sum()) / total_sales
            food_share = float(mix["フード"].sum()) / total_sales

    lunch_sales = float(lunch["summary"]["純売上"].sum()) if not lunch["summary"].empty else 0.0
    course_qty = float(course["summary"]["販売数量"].sum()) if not course["summary"].empty else 0.0
    top_item = top_sales.iloc[0]["商品名"] if not top_sales.empty else "-"
    quantity_item = quantity.iloc[0]["商品名"] if not quantity.empty else "-"

    cols = st.columns(5)
    cols[0].metric("フード比率", format_share(food_share))
    cols[1].metric("ドリンク比率", format_share(drink_share))
    cols[2].metric("ランチ売上", format_yen(lunch_sales))
    cols[3].metric("コース販売数", format_number(course_qty))
    cols[4].metric("数量主力", str(quantity_item))

    st.markdown("##### 自動コメント")
    for message in _decision_messages(store_name, drink_share, lunch_sales, course_qty, top_item, quantity_item):
        st.write(f"- {message}")


def _decision_messages(
    store_name: str,
    drink_share: float,
    lunch_sales: float,
    course_qty: float,
    top_item: str,
    quantity_item: str,
) -> list[str]:
    messages = []
    if store_name == "神田店":
        if drink_share < 0.25:
            messages.append("神田店は夜飲み・ビール・会社利用を伸ばしたい店舗です。ドリンク比率が低めなら、夜の声かけとおすすめ導線を確認してください。")
        messages.append("ボトルとアイスは神田店のみ販売として見ます。店舗限定の強みか、集計ノイズかを確認してください。")
    elif store_name == "東池袋店":
        messages.append("東池袋店は新店の成長管理が主目的です。飯田橋・神田で強い商品との差を店舗間比較で確認してください。")
        if drink_share < 0.20:
            messages.append("飲み利用への拡張余地があります。ドリンク比率とコース販売数をセットで確認してください。")
    elif store_name == "飯田橋店":
        messages.append("飯田橋店は既存客・宴会・コース・安定運用を確認します。定番主力の欠品と品質低下に注意してください。")
    else:
        messages.append("全店では、店舗ごとの差が大きい商品を横展開候補として確認してください。")

    if lunch_sales > 0:
        messages.append("ランチ売上があります。通常商品TOPとは分けて、ランチ内構成比と大盛り率を確認してください。")
    if course_qty > 0:
        messages.append("コース販売があります。単品販売数だけでなく、コース内販売点数を含めた仕込み量を確認してください。")
    if top_item != "-":
        messages.append(f"純売上TOPは「{top_item}」です。欠品・品質低下を防ぐ主力商品として確認してください。")
    if quantity_item != "-" and quantity_item != top_item:
        messages.append(f"販売点数では「{quantity_item}」が目立ちます。売上TOPと違う場合は、仕込み量・オペレーション負荷を確認してください。")
    return messages


def show_department_analysis(departments: pd.DataFrame, store_name: str, month: str) -> None:
    st.subheader("部門分析")
    st.caption(_store_hint(store_name))
    department = department_analysis(departments, store_name, month)
    if department.empty:
        st.warning("選択条件の部門データがありません。")
        return

    mix_data = food_drink_mix(departments, store_name, month)
    st.markdown("#### フード/ドリンク比")
    st.caption("まず店舗ごとのフード売上とドリンク売上の比率を確認します。ボトルとアイスは神田店のみ販売の商品として、商品分析側で注意表示します。")
    if not mix_data["mix"].empty:
        st.caption("全店合算ではなく、店舗ごとの円グラフで確認します。")
        _show_food_drink_store_pies(mix_data["mix"])
        mix_display = add_display_formats(
            mix_data["mix"],
            {
                "フード": "yen",
                "ドリンク": "yen",
                "合計純売上": "yen",
                "フード比率": "share",
                "ドリンク比率": "share",
            },
        )
        st.dataframe(mix_display, use_container_width=True, hide_index=True)
    if not mix_data["details"].empty:
        with st.expander("フード内・ドリンク内の部門構成を見る", expanded=False):
            detail_display = add_display_formats(
                mix_data["details"],
                {"純売上": "yen", "分類内構成比": "share"},
            )
            st.dataframe(detail_display, use_container_width=True, hide_index=True)

    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.markdown("#### 部門別純売上")
        department_sales_bar(department)
    with chart_cols[1]:
        st.markdown("#### 部門別構成比")
        _show_department_store_pies(department)
        department_share_bar(department)

    st.markdown("#### 確認ポイント")
    top_department = department.iloc[0]
    st.write(
        f"売上最大の部門は **{top_department['部門名']}** で、"
        f"構成比は **{format_share(top_department['構成比'])}** です。"
    )

    display = add_display_formats(
        department[
            [
                "集計月",
                "店舗名",
                "部門名",
                "販売数量",
                "純売上",
                "構成比",
                "前月純売上",
                "前月比",
                "前年同月純売上",
                "前年同月比",
            ]
        ],
        {
            "販売数量": "number",
            "純売上": "yen",
            "構成比": "share",
            "前月純売上": "yen",
            "前月比": "percent",
            "前年同月純売上": "yen",
            "前年同月比": "percent",
        },
    )
    st.dataframe(display, use_container_width=True, hide_index=True)


def show_product_top(products: pd.DataFrame, store_name: str, month: str, limit: int, exclude_delivery: bool) -> None:
    st.subheader("商品TOP分析")
    delivery_note = "デリバリー売上は除外しています。" if exclude_delivery else "デリバリー売上も含めています。"
    st.caption(f"全商品一覧は初期表示せず、売上・数量・平均単価のTOPだけを表示します。売上TOPと平均単価TOPはランチ商品・コース内訳を除外します。{delivery_note}")

    scoped = products[products["集計月"] == month].copy()
    if store_name != "全店":
        scoped = scoped[scoped["店舗名"] == store_name]
    analysis_scope = exclude_delivery_rows(scoped) if exclude_delivery else scoped

    cols = st.columns(3)
    cols[0].metric("分析対象商品行", format_number(len(analysis_scope)))
    cols[1].metric("除外した行", format_number(len(scoped) - len(analysis_scope)))
    cols[2].metric("表示件数", format_number(limit))

    top_tabs = st.tabs(["純売上TOP", "販売数量TOP", "平均単価TOP"])
    specs = [("純売上", "純売上"), ("販売数量", "販売数量"), ("平均単価", "平均単価")]
    for tab, (label, sort_by) in zip(top_tabs, specs):
        with tab:
            if sort_by == "販売数量":
                top = product_quantity_with_course(products, store_name, month, limit, exclude_delivery)
                if top.empty:
                    st.warning("選択条件の商品データがありません。")
                    continue
                first = top.iloc[0]
                st.write(
                    f"1位: **{first['商品名']}** / 全体販売数量: **{format_number(first['全体販売数量'])}** "
                    f"(単品 {format_number(first['単品販売数量'])} / コース内 {format_number(first['コース内販売数量'])})"
                )
                st.caption("販売数量は、通常の単品販売数に、コース内訳として確認できる数量と、コース本体から確実に推定できる基本セット品を加算しています。")
                top_share_pie(top, "商品名", "全体販売数量", limit=8, title="販売数量構成比")
                st.dataframe(_format_product_quantity_with_course(top), use_container_width=True, hide_index=True)
                continue

            top = product_top(products, store_name, month, limit, sort_by, exclude_delivery)
            if top.empty:
                st.warning("選択条件の商品データがありません。")
                continue
            first = top.iloc[0]
            st.write(f"1位: **{first['商品名']}** / {label}: **{_format_top_value(first[sort_by], sort_by)}**")
            if sort_by == "純売上":
                top_share_pie(top, "商品名", "純売上", limit=8, title="売上構成比")
            product_top_bar(top, sort_by)
            st.dataframe(_format_product_top(top), use_container_width=True, hide_index=True)

    with st.expander("確認用: 選択条件の商品データ先頭20件", expanded=False):
        preview = analysis_scope.head(20)
        st.dataframe(preview, use_container_width=True, hide_index=True)


def show_course_analysis(products: pd.DataFrame, store_name: str, month: str, limit: int, exclude_delivery: bool) -> None:
    st.subheader("コース分析")
    st.caption(
        "コース本体の販売数と、コース内で販売された商品点数を分けて確認します。"
        "「コース料理」はおつまみコースとして扱います。"
    )
    st.info("おつまみコース・オコノミコースの基本5品はコース数量から加算します。3名以上時の「がんす」「鉄MIX」は月次集計だけでは判定できないため、自動加算していません。")

    course = course_analysis(products, store_name, month, exclude_delivery)
    summary = course["summary"]
    components = course["components"]

    if summary.empty and components.empty:
        st.warning("選択条件のコースデータがありません。")
        return

    if not summary.empty:
        st.markdown("#### コース本体")
        top_share_pie(summary, "コース区分", "純売上", limit=6, title="コース売上構成比")
        summary_display = add_display_formats(
            summary,
            {"販売数量": "number", "純売上": "yen", "取引数": "number", "平均単価": "yen"},
        )
        st.dataframe(summary_display, use_container_width=True, hide_index=True)

    if not components.empty:
        st.markdown("#### コース内で販売された商品点数")
        top_share_pie(components, "商品名", "コース内販売数量", limit=8, title="コース内販売点数構成比")
        component_columns = [
            "順位",
            "店舗名",
            "商品名",
            "部門名",
            "コース内販売数量",
            "単品販売数量",
            "全体販売数量",
            "商品分類メモ",
        ]
        component_display = add_display_formats(
            components[[column for column in component_columns if column in components.columns]].head(limit),
            {"コース内販売数量": "number", "単品販売数量": "number", "全体販売数量": "number"},
        )
        st.dataframe(component_display, use_container_width=True, hide_index=True)


def show_lunch_analysis(products: pd.DataFrame, store_name: str, month: str, limit: int, exclude_delivery: bool) -> None:
    st.subheader("ランチ分析")
    st.caption("【ランチ】系の商品だけを抜き出し、ランチ内で何が売れているかを確認します。通常商品TOPやABCからはランチ商品を外しています。")
    st.info("ランチ時間帯に売れた通常商品やドリンクは、商品名だけでは判定できないためこの表には含めていません。まずは【ランチ】系商品の構成比を優先して確認します。")

    lunch = lunch_analysis(products, store_name, month, exclude_delivery)
    summary = lunch["summary"]
    items = lunch["items"]

    if summary.empty and items.empty:
        st.warning("選択条件のランチデータがありません。")
        return

    if not summary.empty:
        st.markdown("#### ランチ売上サマリー")
        summary_display = add_display_formats(
            summary,
            {"販売数量": "number", "純売上": "yen", "取引数": "number", "平均単価": "yen"},
        )
        st.dataframe(summary_display, use_container_width=True, hide_index=True)

    if not items.empty:
        st.markdown("#### ランチ内構成比")
        top_share_pie(items, "ランチ商品名", "純売上", limit=8, title="ランチ内売上構成比")
        item_columns = [
            "店舗名",
            "ランチ商品名",
            "販売数量",
            "純売上",
            "ランチ内構成比",
            "平均単価",
            "大盛り数量",
            "TO数量",
            "取引数",
        ]
        item_display = add_display_formats(
            items[[column for column in item_columns if column in items.columns]].head(limit),
            {
                "販売数量": "number",
                "純売上": "yen",
                "ランチ内構成比": "share",
                "平均単価": "yen",
                "大盛り数量": "number",
                "TO数量": "number",
                "取引数": "number",
            },
        )
        st.dataframe(item_display, use_container_width=True, hide_index=True)


def show_abc_analysis(products: pd.DataFrame, store_name: str, month: str, limit: int, exclude_delivery: bool) -> None:
    st.subheader("ABC分析")
    delivery_note = "商品判断をしやすくするため、デリバリー売上は除外しています。" if exclude_delivery else "デリバリー売上も含めています。"
    st.caption(
        "A商品は欠品・品質低下を防ぐ最重要商品、B商品はおすすめ強化候補、"
        f"C商品は整理・統合・名称変更・価格見直しの確認候補です。{delivery_note}"
    )
    abc = abc_analysis(products, store_name, month, exclude_delivery)
    if abc.empty:
        st.warning("選択条件の商品データがありません。")
        return

    summary = abc.groupby("ABC区分", as_index=False).agg(商品数=("商品名", "count"), 純売上=("純売上", "sum"))
    total = summary["純売上"].sum()
    summary["構成比"] = summary["純売上"] / total if total else 0
    pie_chart(summary, "ABC区分", "純売上", "ABC売上構成比")
    st.dataframe(
        add_display_formats(summary, {"純売上": "yen", "構成比": "share"}),
        use_container_width=True,
        hide_index=True,
    )
    columns = ["ABC区分", "順位", "店舗名", "商品名", "部門名", "販売数量", "純売上", "構成比", "累計構成比", "平均単価"]
    display = add_display_formats(
        abc[columns].head(limit),
        {"販売数量": "number", "純売上": "yen", "構成比": "share", "累計構成比": "share", "平均単価": "yen"},
    )
    st.dataframe(display, use_container_width=True, hide_index=True)


def show_change_rankings(
    products: pd.DataFrame,
    store_name: str,
    month: str,
    limit: int,
    exclude_delivery: bool,
    compare_mode: str,
    custom_compare_month: str,
) -> None:
    st.subheader("前月比・前年比ランキング")
    delivery_note = "デリバリー売上は除外しています。" if exclude_delivery else "デリバリー売上も含めています。"
    st.caption(f"伸びた商品、落ちた商品、新規/復活商品を確認します。{delivery_note}")

    prev_month = previous_month(month)
    prev_year = previous_year_month(month)
    selected_compare_month = custom_compare_month
    if compare_mode == "前月":
        selected_compare_month = prev_month
    elif compare_mode == "前年同月":
        selected_compare_month = prev_year

    month_rank = product_change_ranking(products, store_name, month, prev_month, exclude_delivery)
    year_rank = product_change_ranking(products, store_name, month, prev_year, exclude_delivery)
    selected_rank = product_change_ranking(products, store_name, month, selected_compare_month, exclude_delivery)

    st.write(f"選択月 **{month}** と、サイドバーの比較対象 **{selected_compare_month}** を比較できます。")

    tabs = st.tabs(["選択比較 伸びた", "選択比較 落ちた", "前月比 伸びた", "前月比 落ちた", "前年比 伸びた", "前年比 落ちた", "新規/復活"])
    with tabs[0]:
        _show_change_table(selected_rank.sort_values("増減額", ascending=False).head(limit), f"{selected_compare_month} 比で伸びた商品")
    with tabs[1]:
        _show_change_table(selected_rank.sort_values("増減額", ascending=True).head(limit), f"{selected_compare_month} 比で落ちた商品")
    with tabs[2]:
        _show_change_table(month_rank.sort_values("増減額", ascending=False).head(limit), "前月比で伸びた商品")
    with tabs[3]:
        _show_change_table(month_rank.sort_values("増減額", ascending=True).head(limit), "前月比で落ちた商品")
    with tabs[4]:
        _show_change_table(year_rank.sort_values("増減額", ascending=False).head(limit), "前年同月比で伸びた商品")
    with tabs[5]:
        _show_change_table(year_rank.sort_values("増減額", ascending=True).head(limit), "前年同月比で落ちた商品")
    with tabs[6]:
        new_items = month_rank[month_rank["状態"] == "新規/復活"].sort_values("選択月純売上", ascending=False).head(limit)
        _show_change_table(new_items, "前月になく、選択月に売上がある商品")


def show_store_comparison(
    products: pd.DataFrame,
    departments: pd.DataFrame,
    month: str,
    limit: int,
    exclude_delivery: bool,
) -> None:
    st.subheader("店舗間比較")
    delivery_note = "商品比較ではデリバリー売上を除外しています。" if exclude_delivery else "商品比較ではデリバリー売上も含めています。"
    st.caption(f"他店舗では売れているのに、自店舗では弱い商品を見つけます。{delivery_note}")

    product_compare = store_product_comparison(products, month, exclude_delivery)
    department_compare = store_department_comparison(departments, month)

    tabs = st.tabs(["商品別 店舗間比較", "部門別 店舗間比較", "ギャップ大 商品TOP"])
    with tabs[0]:
        _show_store_product_table(product_compare.head(limit))
    with tabs[1]:
        _show_store_department_table(department_compare.head(limit))
    with tabs[2]:
        gap = product_compare.sort_values(["最大/最小差額", "全店純売上"], ascending=False).head(limit)
        _show_store_product_table(gap)


def show_improvement_candidates(products: pd.DataFrame, store_name: str, month: str, limit: int, exclude_delivery: bool) -> None:
    st.subheader("改善候補")
    st.caption("自動で廃止とは判断しません。店長会議で確認するための候補として表示します。")
    st.info(
        "確認の優先順位: 1. 他店で強いのに自店で弱い商品、2. B商品で伸ばせそうなPOP候補、"
        "3. C商品でも季節・店舗限定・コース内訳ではない整理確認候補。"
    )
    if store_name == "全店":
        st.info("おすすめ強化候補は店舗別の弱い商品を見るため、店舗を1つ選ぶとより使いやすくなります。")

    candidates = improvement_candidates(products, store_name, month, exclude_delivery)
    tabs = st.tabs(["おすすめ強化候補", "整理確認候補", "POP候補"])
    with tabs[0]:
        _show_store_product_table(candidates["recommend"].head(limit))
    with tabs[1]:
        c_columns = ["ABC区分", "順位", "店舗名", "商品名", "部門名", "販売数量", "純売上", "構成比", "累計構成比", "平均単価", "確認メモ"]
        _show_candidate_table(candidates["c_candidates"], c_columns)
    with tabs[2]:
        pop_columns = ["ABC区分", "順位", "店舗名", "商品名", "部門名", "販売数量", "純売上", "平均単価", "確認メモ"]
        _show_candidate_table(candidates["pop"], pop_columns)


def _show_change_table(dataframe: pd.DataFrame, title: str) -> None:
    st.markdown(f"#### {title}")
    if dataframe.empty:
        st.info("該当する商品がありません。")
        return
    columns = [
        "店舗名",
        "商品名",
        "部門名",
        "選択月純売上",
        "比較月純売上",
        "増減額",
        "増減率",
        "状態",
        "選択月販売数量",
        "比較月販売数量",
        "数量増減",
    ]
    display = dataframe[columns].copy()
    display["増減率"] = display.apply(
        lambda row: row["状態"] if pd.isna(row["増減率"]) else format_percent(row["増減率"]),
        axis=1,
    )
    display = add_display_formats(
        display,
        {
            "選択月純売上": "yen",
            "比較月純売上": "yen",
            "増減額": "signed_yen",
            "選択月販売数量": "number",
            "比較月販売数量": "number",
            "数量増減": "number",
        },
    )
    st.dataframe(display, use_container_width=True, hide_index=True)


def _food_drink_chart_data(mix: pd.DataFrame) -> pd.DataFrame:
    if mix.empty:
        return pd.DataFrame(columns=["分類", "純売上"])
    return pd.DataFrame(
        [
            {"分類": "フード", "純売上": float(mix["フード"].sum())},
            {"分類": "ドリンク", "純売上": float(mix["ドリンク"].sum())},
        ]
    )


def _show_food_drink_store_pies(mix: pd.DataFrame) -> None:
    if mix.empty:
        return
    stores = mix["店舗名"].dropna().astype(str).tolist()
    columns = st.columns(min(3, max(1, len(stores))))
    for index, (_, row) in enumerate(mix.iterrows()):
        chart_data = pd.DataFrame(
            [
                {"分類": "フード", "純売上": float(row.get("フード", 0) or 0)},
                {"分類": "ドリンク", "純売上": float(row.get("ドリンク", 0) or 0)},
            ]
        )
        with columns[index % len(columns)]:
            pie_chart(chart_data, "分類", "純売上", f"{row['店舗名']}")
            st.caption(
                f"フード {format_share(row.get('フード比率', 0))} / "
                f"ドリンク {format_share(row.get('ドリンク比率', 0))}"
            )


def _show_department_store_pies(department: pd.DataFrame) -> None:
    if department.empty:
        return
    grouped = department.groupby(["店舗名", "部門名"], as_index=False)["純売上"].sum()
    stores = grouped["店舗名"].dropna().astype(str).unique().tolist()
    columns = st.columns(min(3, max(1, len(stores))))
    for index, store in enumerate(stores):
        store_data = grouped[grouped["店舗名"] == store].sort_values("純売上", ascending=False)
        with columns[index % len(columns)]:
            top_share_pie(store_data, "部門名", "純売上", limit=8, title=f"{store}")


def _show_store_product_table(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("該当する商品がありません。")
        return
    columns = [
        "商品名",
        "部門名",
        "飯田橋店",
        "神田店",
        "東池袋店",
        "全店純売上",
        "最大店舗",
        "最小店舗",
        "最大/最小差額",
        "活用メモ",
    ]
    display = dataframe[columns].rename(
        columns={
            "飯田橋店": "飯田橋店 純売上",
            "神田店": "神田店 純売上",
            "東池袋店": "東池袋店 純売上",
        }
    )
    display = add_display_formats(
        display,
        {
            "飯田橋店 純売上": "yen",
            "神田店 純売上": "yen",
            "東池袋店 純売上": "yen",
            "全店純売上": "yen",
            "最大/最小差額": "yen",
        },
    )
    st.dataframe(display, use_container_width=True, hide_index=True)


def _show_store_department_table(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("該当する部門がありません。")
        return
    display = dataframe.rename(
        columns={
            "飯田橋店": "飯田橋店 純売上",
            "神田店": "神田店 純売上",
            "東池袋店": "東池袋店 純売上",
        }
    )
    display = add_display_formats(
        display,
        {
            "飯田橋店 純売上": "yen",
            "神田店 純売上": "yen",
            "東池袋店 純売上": "yen",
            "全店純売上": "yen",
        },
    )
    st.dataframe(display, use_container_width=True, hide_index=True)


def _show_candidate_table(dataframe: pd.DataFrame, columns: list[str]) -> None:
    if dataframe.empty:
        st.info("該当する候補がありません。")
        return
    available_columns = [column for column in columns if column in dataframe.columns]
    display = add_display_formats(
        dataframe[available_columns],
        {
            "販売数量": "number",
            "純売上": "yen",
            "構成比": "share",
            "累計構成比": "share",
            "平均単価": "yen",
            "増減額": "signed_yen",
            "増減率": "percent",
        },
    )
    st.dataframe(display, use_container_width=True, hide_index=True)


def _format_product_quantity_with_course(dataframe: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "順位",
        "店舗名",
        "商品名",
        "部門名",
        "単品販売数量",
        "コース内販売数量",
        "全体販売数量",
        "純売上",
        "平均単価",
        "数量構成比",
        "取引数",
        "商品分類メモ",
    ]
    available_columns = [column for column in columns if column in dataframe.columns]
    return add_display_formats(
        dataframe[available_columns],
        {
            "単品販売数量": "number",
            "コース内販売数量": "number",
            "全体販売数量": "number",
            "純売上": "yen",
            "平均単価": "yen",
            "数量構成比": "share",
            "取引数": "number",
        },
    )


def _format_product_top(dataframe: pd.DataFrame) -> pd.DataFrame:
    columns = ["順位", "店舗名", "商品名", "部門名", "販売数量", "純売上", "平均単価", "構成比", "取引数"]
    return add_display_formats(
        dataframe[columns],
        {
            "販売数量": "number",
            "純売上": "yen",
            "平均単価": "yen",
            "構成比": "share",
            "取引数": "number",
        },
    )


def _format_top_value(value: float, column_name: str) -> str:
    if column_name in {"純売上", "平均単価"}:
        return format_yen(value)
    return format_number(value)


def _latest_updated_at(products: pd.DataFrame, departments: pd.DataFrame) -> str:
    values = []
    for dataframe in (products, departments):
        if "最終集計日時" in dataframe.columns and not dataframe.empty:
            values.extend(dataframe["最終集計日時"].dropna().astype(str).tolist())
    values = [value for value in values if value and value.lower() != "nan"]
    return max(values) if values else "不明"


def _store_hint(store_name: str) -> str:
    hints = {
        "飯田橋店": "飯田橋店は既存客・宴会・コース・デリバリー・安定運用のバランスを確認します。",
        "神田店": "神田店はランチ、夜飲み、会社利用、ビール、鉄板焼、コースの伸びを確認します。",
        "東池袋店": "東池袋店は新店の成長管理、宴会・飲み利用への拡張、飯田橋・神田で強い商品の横展開を確認します。",
        "全店": "全店では店舗別の違いを見ながら、定番主力と横展開候補を確認します。",
    }
    return hints.get(store_name, "")


if __name__ == "__main__":
    main()
