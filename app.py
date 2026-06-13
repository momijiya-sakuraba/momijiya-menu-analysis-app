from __future__ import annotations

import hmac

import pandas as pd
import streamlit as st

from utils.charts import department_sales_bar, department_share_bar, product_top_bar
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
    department_analysis,
    exclude_delivery_rows,
    improvement_candidates,
    monthly_summary,
    product_top,
    product_change_ranking,
    previous_month,
    previous_year_month,
    store_department_comparison,
    store_product_comparison,
)


st.set_page_config(page_title="商品・部門分析アプリ", page_icon="M", layout="wide")


def main() -> None:
    if not require_login():
        st.stop()

    st.title("商品・部門分析アプリ")
    st.caption("もみじ屋専用。商品別売上・部門別売上だけを読み込む軽量分析アプリです。")

    with st.sidebar:
        st.header("条件")
        if st.button("ログアウト", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()
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
        ["概要", "月次サマリー", "部門分析", "商品TOP分析", "ABC分析", "前月比・前年比ランキング", "店舗間比較", "改善候補"],
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


def require_login() -> bool:
    if st.session_state.get("authenticated"):
        return True

    password_candidates = _auth_passwords()
    if not password_candidates:
        st.title("商品・部門分析アプリ")
        st.error("アプリ用パスワードが未設定です。`.streamlit/secrets.toml` の [auth] を設定してください。")
        return False

    st.title("商品・部門分析アプリ")
    st.subheader("ログイン")
    st.caption("許可された人だけが使用できます。管理者から共有されたパスワードを入力してください。")

    entered_password = st.text_input("パスワード", type="password")
    if st.button("ログイン", type="primary"):
        if any(hmac.compare_digest(entered_password, password) for password in password_candidates):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    return False


def _auth_passwords() -> list[str]:
    try:
        auth_config = st.secrets.get("auth", {})
    except Exception:
        return []

    passwords: list[str] = []
    single_password = auth_config.get("app_password") or auth_config.get("password")
    if single_password:
        passwords.append(str(single_password))

    configured_passwords = auth_config.get("allowed_passwords", [])
    if isinstance(configured_passwords, str):
        passwords.append(configured_passwords)
    else:
        passwords.extend(str(password) for password in configured_passwords if password)

    return [password for password in passwords if password]


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

    st.markdown("#### 今日見る順番")
    st.write("1. 月次サマリーで店舗別の総額を確認")
    st.write("2. 部門分析で売上構成と前月比を見る")
    st.write("3. 商品TOP分析で主力商品を確認")
    st.write("4. ABC分析で守る商品・伸ばす商品・確認候補を分ける")

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


def show_department_analysis(departments: pd.DataFrame, store_name: str, month: str) -> None:
    st.subheader("部門分析")
    st.caption(_store_hint(store_name))
    department = department_analysis(departments, store_name, month)
    if department.empty:
        st.warning("選択条件の部門データがありません。")
        return

    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.markdown("#### 部門別純売上")
        department_sales_bar(department)
    with chart_cols[1]:
        st.markdown("#### 部門別構成比")
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
    st.caption(f"全商品一覧は初期表示せず、売上・数量・平均単価のTOPだけを表示します。{delivery_note}")

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
            top = product_top(products, store_name, month, limit, sort_by, exclude_delivery)
            if top.empty:
                st.warning("選択条件の商品データがありません。")
                continue
            first = top.iloc[0]
            st.write(f"1位: **{first['商品名']}** / {label}: **{_format_top_value(first[sort_by], sort_by)}**")
            product_top_bar(top, sort_by)
            st.dataframe(_format_product_top(top), use_container_width=True, hide_index=True)

    with st.expander("確認用: 選択条件の商品データ先頭20件", expanded=False):
        preview = analysis_scope.head(20)
        st.dataframe(preview, use_container_width=True, hide_index=True)


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
