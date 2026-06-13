from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials


SPREADSHEET_ID = "1bBsJxUtDSTk7Qkfn_Q2tKKVo-0AL_aFCkivalZTtGWc"
PRODUCT_SHEET_NAME = "商品別売上"
DEPARTMENT_SHEET_NAME = "部門別売上"
CACHE_TTL_SECONDS = 21600

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

NUMERIC_COLUMNS = [
    "販売数量",
    "値引前売上",
    "単品値引",
    "値引後売上",
    "小計値引按分",
    "ポイント値引按分",
    "クーポン値引按分",
    "バンドル値引按分",
    "純売上",
    "内税按分",
    "外税按分",
    "税抜純売上",
    "原価",
    "粗利",
    "取引数",
]

PRODUCT_REQUIRED_COLUMNS = [
    "集計月",
    "店舗ID",
    "店舗名",
    "商品ID",
    "商品コード",
    "商品名",
    "部門ID",
    "部門名",
    "販売数量",
    "純売上",
    "最終集計日時",
]

DEPARTMENT_REQUIRED_COLUMNS = [
    "集計月",
    "店舗ID",
    "店舗名",
    "部門ID",
    "部門名",
    "販売数量",
    "純売上",
    "最終集計日時",
]


@dataclass(frozen=True)
class SalesData:
    products: pd.DataFrame
    departments: pd.DataFrame
    loaded_at: datetime


def get_spreadsheet_id() -> str:
    try:
        configured_id = st.secrets.get("app", {}).get("spreadsheet_id")
    except Exception:
        configured_id = None
    return str(configured_id or os.getenv("GOOGLE_SPREADSHEET_ID") or SPREADSHEET_ID)


def _credentials_from_secrets() -> Credentials:
    account_info = None
    try:
        account_info = st.secrets["google_service_account"]
    except Exception:
        pass

    if not account_info:
        try:
            account_info = st.secrets["gcp_service_account"]
        except Exception:
            pass

    if not account_info:
        raise RuntimeError(
            "Streamlit secrets に [google_service_account] がありません。"
            "既存アプリのsecretsを流用する場合は [gcp_service_account] でも読み込めます。"
            ".streamlit/secrets.toml を設定し、サービスアカウントをスプレッドシートに共有してください。"
        )

    info: dict[str, Any] = dict(account_info)
    if "private_key" in info:
        info["private_key"] = str(info["private_key"]).replace("\\n", "\n")
    return Credentials.from_service_account_info(info, scopes=SCOPES)


@st.cache_resource(show_spinner=False)
def get_gspread_client() -> gspread.Client:
    return gspread.authorize(_credentials_from_secrets())


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Google Sheetsから商品・部門データを読み込んでいます...")
def load_sales_data(spreadsheet_id: str) -> SalesData:
    client = get_gspread_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    loaded_at = datetime.now()
    products = _load_sheet(spreadsheet, PRODUCT_SHEET_NAME, PRODUCT_REQUIRED_COLUMNS)
    departments = _load_sheet(spreadsheet, DEPARTMENT_SHEET_NAME, DEPARTMENT_REQUIRED_COLUMNS)
    return SalesData(products=products, departments=departments, loaded_at=loaded_at)


@st.cache_data(ttl=86400, show_spinner=False)
def get_filter_options(products: pd.DataFrame, departments: pd.DataFrame) -> dict[str, list[str]]:
    source = departments if not departments.empty else products
    months = sorted(source["集計月"].dropna().astype(str).unique().tolist())
    stores = sorted(source["店舗名"].dropna().astype(str).unique().tolist())
    return {"months": months, "stores": stores}


def _load_sheet(spreadsheet: gspread.Spreadsheet, sheet_name: str, required_columns: list[str]) -> pd.DataFrame:
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound as exc:
        raise RuntimeError(f"必要なシート「{sheet_name}」が見つかりません。") from exc

    rows = worksheet.get_all_values()
    if not rows:
        raise RuntimeError(f"シート「{sheet_name}」が空です。")

    header = [str(column).strip() for column in rows[0]]
    values = rows[1:]
    dataframe = pd.DataFrame(values, columns=header)
    dataframe = dataframe.dropna(how="all")
    dataframe = dataframe.loc[
        ~dataframe.astype(str).apply(lambda row: row.str.strip().eq("").all(), axis=1)
    ]

    missing = [column for column in required_columns if column not in dataframe.columns]
    if missing:
        raise RuntimeError(
            f"シート「{sheet_name}」に必要な列がありません: {', '.join(missing)}。"
            f"現在の列: {', '.join(dataframe.columns.astype(str))}"
        )

    return normalize_sales_dataframe(dataframe)


def normalize_sales_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = dataframe.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]

    for column in normalized.columns:
        if normalized[column].dtype == object:
            normalized[column] = normalized[column].astype(str).str.strip()

    for column in NUMERIC_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = 0
        normalized[column] = (
            normalized[column]
            .replace(["", "null", "None", "nan", None], 0)
            .astype(str)
            .str.replace(",", "", regex=False)
        )
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0)

    normalized["集計月"] = normalized["集計月"].astype(str).str.slice(0, 7)
    normalized["店舗名"] = normalized["店舗名"].map(normalize_store_name)
    return normalized


def normalize_store_name(store_name: object) -> str:
    name = str(store_name).strip().replace("\u3000", " ")
    if "飯田橋" in name:
        return "飯田橋店"
    if "神田" in name:
        return "神田店"
    if "東池袋" in name:
        return "東池袋店"
    return name
