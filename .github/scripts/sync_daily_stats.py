#!/usr/bin/env python3
"""Synchronize live stats JSON into stats_data.json, index.html, and stats.html."""

from __future__ import annotations

import html
import json
import math
import re
import sys
from pathlib import Path

REQUIRED_KEYS = (
    "treasury",
    "shop",
    "warehouse",
    "quiz",
    "leaderboards",
    "timeseries",
)

EXCLUDED_ADMIN_SET = {
    "aziz",
    "azizaboba",
    "77phoenix77",
    "phoenix_",
    "cracen2",
    "dahyshechka",
    "chesnok_fpv",
    "karas_mentolist",
    "feyk",
    "p5ych0p41h",
    "p1zd6bol",
    "goodplayer",
    "egolek",
    "dmitnik",
    "popka2014",
    "ferm_1",
    "ferm_2",
}

FORBIDDEN_VISIBLE_CHARS = ("\u2014", "\u2013", "(", ")")


def to_num(value) -> float:
    if value is None or value == "":
        return 0.0
    try:
        num = float(value)
        return 0.0 if (math.isnan(num) or math.isinf(num)) else num
    except (TypeError, ValueError):
        return 0.0


def js_round(value) -> int:
    """Match JavaScript Math.round(Number(n) || 0) semantics."""
    return int(math.floor(to_num(value) + 0.5))


def fmt_int(value) -> str:
    rounded = js_round(value)
    sign = "-" if rounded < 0 else ""
    return sign + f"{abs(rounded):,}".replace(",", " ")


def fmt_rub(value, show_plus: bool = False) -> str:
    rounded = js_round(value)
    sign = "+" if rounded > 0 and show_plus else ""
    return f"{sign}{fmt_int(rounded)} ₽"


def medal_class(idx: int) -> str:
    if idx == 0:
        return " rank-medal-1"
    if idx == 1:
        return " rank-medal-2"
    if idx == 2:
        return " rank-medal-3"
    return ""


def filter_non_admin(items) -> list[dict]:
    out: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        low = name.lower()
        if low and low not in EXCLUDED_ADMIN_SET and not low.startswith("ferm_"):
            out.append(item)
    return out


def validate_stats_data(data) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Stats JSON root must be an object.")
    missing = [k for k in REQUIRED_KEYS if k not in data or data[k] is None]
    if missing:
        raise ValueError(f"Stats JSON missing required keys: {', '.join(missing)}")
    for dict_key in ("treasury", "shop", "quiz", "leaderboards"):
        if not isinstance(data[dict_key], dict):
            raise ValueError(f"Key {dict_key!r} must be a JSON object.")
    for list_key in ("warehouse", "timeseries"):
        if not isinstance(data[list_key], list):
            raise ValueError(f"Key {list_key!r} must be a JSON array.")
    return data


def replace_element_inner_by_id(
    html_text: str, elem_id: str, new_inner: str, tag_pattern: str = r"[a-zA-Z0-9]+"
) -> str:
    pattern = re.compile(
        rf'(<(?P<tag>{tag_pattern})\b[^>]*\bid=["\']{re.escape(elem_id)}["\'][^>]*>)'
        rf"(?P<inner>.*?)"
        rf"(</(?P=tag)>)",
        re.DOTALL | re.IGNORECASE,
    )
    matches = list(pattern.finditer(html_text))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly 1 element with id={elem_id!r}, found {len(matches)}."
        )
    m = matches[0]
    return html_text[: m.start("inner")] + new_inner + html_text[m.end("inner") :]


def update_ratio_bar_width(html_text: str, buy_pct: str) -> str:
    tag_pattern = re.compile(
        r'<div\b[^>]*\bid=["\']ratioBarBuyFill["\'][^>]*>', re.IGNORECASE
    )
    matches = list(tag_pattern.finditer(html_text))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly 1 #ratioBarBuyFill element, found {len(matches)}."
        )
    m = matches[0]
    tag_str = m.group(0)
    style_pattern = re.compile(r'style=["\'][^"\']*["\']', re.IGNORECASE)
    if style_pattern.search(tag_str):
        new_tag = style_pattern.sub(f'style="width: {buy_pct}%;"', tag_str, count=1)
    else:
        new_tag = tag_str[:-1] + f' style="width: {buy_pct}%;">'
    return html_text[: m.start()] + new_tag + html_text[m.end() :]


def build_home_quiz_rows(data: dict) -> str:
    quiz_raw = (data.get("quiz") or {}).get("top_solvers") or []
    quiz_list = filter_non_admin(quiz_raw)[:10]
    indent = " " * 36
    rows: list[str] = []
    for i, entry in enumerate(quiz_list):
        name = html.escape(str(entry.get("name") or ""), quote=True)
        qty = to_num(entry.get("qty"))
        rub = to_num(entry.get("rub")) or (qty * 1500.0)
        rows.append(
            f'{indent}<tr><td class="col-rank{medal_class(i)}">{i + 1}</td>'
            f'<td class="col-name"><strong>{name}</strong></td>'
            f'<td class="col-mid">{fmt_int(qty)} шт.</td>'
            f'<td class="col-num" style="color:#22c55e;">{fmt_int(rub)} ₽</td></tr>'
        )
    for i in range(len(rows), 10):
        rows.append(
            f'{indent}<tr class="row-empty"><td class="col-rank">{i + 1}</td>'
            f'<td class="col-name">Свободный слот</td>'
            f'<td class="col-mid">•</td>'
            f'<td class="col-num">0</td></tr>'
        )
    return "\n" + "\n".join(rows) + "\n" + (" " * 32)


def build_home_balance_rows(data: dict) -> str:
    bal_raw = (data.get("leaderboards") or {}).get("top_balances") or []
    bal_list = filter_non_admin(bal_raw)[:10]
    top10_sum = sum(to_num(x.get("rub")) for x in bal_list) or 1.0
    indent = " " * 36
    rows: list[str] = []
    for i, entry in enumerate(bal_list):
        name = html.escape(str(entry.get("name") or ""), quote=True)
        rub = to_num(entry.get("rub"))
        share = f"{(rub / top10_sum) * 100.0:.1f}%"
        rows.append(
            f'{indent}<tr><td class="col-rank{medal_class(i)}">{i + 1}</td>'
            f'<td class="col-name"><strong>{name}</strong></td>'
            f'<td class="col-mid">{share}</td>'
            f'<td class="col-num" style="color:#f59e0b;">{fmt_int(rub)} ₽</td></tr>'
        )
    for i in range(len(rows), 10):
        rows.append(
            f'{indent}<tr class="row-empty"><td class="col-rank">{i + 1}</td>'
            f'<td class="col-name">Свободный слот</td>'
            f'<td class="col-mid">•</td>'
            f'<td class="col-num">0</td></tr>'
        )
    return "\n" + "\n".join(rows) + "\n" + (" " * 32)


def format_indented_js_object(data: dict, base_indent: str = "        ") -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    lines = raw.split("\n")
    return "\n".join([lines[0]] + [base_indent + line for line in lines[1:]])


def replace_current_stats_data(html_text: str, data: dict) -> str:
    indented_obj = format_indented_js_object(data, base_indent="        ")

    marker_pat = re.compile(
        r"(^[ \t]*//\s*BEGIN_CURRENT_STATS_DATA\s*\r?\n)(.*?)(^[ \t]*//\s*END_CURRENT_STATS_DATA)",
        re.DOTALL | re.MULTILINE,
    )
    marker_match = marker_pat.search(html_text)
    if marker_match:
        replacement = f"        let currentStatsData = {indented_obj};\n"
        return (
            html_text[: marker_match.start(2)]
            + replacement
            + html_text[marker_match.start(3) :]
        )

    decl_pat = re.compile(r"([ \t]*)let\s+currentStatsData\s*=\s*\{")
    decl_matches = list(decl_pat.finditer(html_text))
    if len(decl_matches) != 1:
        raise ValueError(
            f"Expected 1 'let currentStatsData = {{' declaration, found {len(decl_matches)}."
        )
    m = decl_matches[0]
    brace_start = m.end() - 1
    depth = 0
    in_string = False
    quote_char = ""
    escaped = False
    brace_end = -1

    for idx in range(brace_start, len(html_text)):
        ch = html_text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote_char:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                quote_char = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    brace_end = idx
                    break

    if brace_end == -1 or depth != 0:
        raise ValueError("Unbalanced braces while parsing 'let currentStatsData = {...}'.")

    tail = brace_end + 1
    while tail < len(html_text) and html_text[tail] in " \t\r\n":
        tail += 1
    if tail >= len(html_text) or html_text[tail] != ";":
        raise ValueError("Expected ';' after currentStatsData object literal.")

    return html_text[:brace_start] + indented_obj + ";" + html_text[tail + 1 :]


def update_index_html(html_text: str, data: dict) -> str:
    updated = replace_element_inner_by_id(
        html_text, "homeTopQuiz", build_home_quiz_rows(data), tag_pattern="tbody"
    )
    updated = replace_element_inner_by_id(
        updated, "homeTopBalance", build_home_balance_rows(data), tag_pattern="tbody"
    )
    return updated


def update_stats_html(html_text: str, data: dict) -> str:
    t = data.get("treasury") or {}
    s = data.get("shop") or {}

    today_shop_buy = (
        to_num(t.get("today_shop_buy_rub"))
        if t.get("today_shop_buy_rub") is not None
        else to_num(s.get("today_buy_rub"))
    )
    today_other_inc = (
        to_num(t.get("today_other_income_rub"))
        if t.get("today_other_income_rub") is not None
        else max(0.0, to_num(t.get("today_income_rub")) - today_shop_buy)
    )
    today_shop_sell = (
        to_num(t.get("today_shop_sell_rub"))
        if t.get("today_shop_sell_rub") is not None
        else to_num(s.get("today_sell_rub"))
    )
    today_rewards_exp = (
        to_num(t.get("today_rewards_expense_rub"))
        if t.get("today_rewards_expense_rub") is not None
        else max(0.0, to_num(t.get("today_expense_rub")) - today_shop_sell)
    )

    buy_rub = to_num(s.get("buy_rub"))
    sell_rub = to_num(s.get("sell_rub"))
    total_turnover = buy_rub + sell_rub
    buy_pct = f"{(buy_rub / total_turnover) * 100.0:.1f}" if total_turnover > 0 else "96.6"
    sell_pct = f"{(sell_rub / total_turnover) * 100.0:.1f}" if total_turnover > 0 else "3.4"

    today_exp = to_num(t.get("today_expense_rub"))
    today_exp_text = ("-" if today_exp > 0 else "") + fmt_rub(today_exp, False)

    players_count = to_num(t.get("real_players_count")) or 74
    coverage_pct = to_num(t.get("coverage_ratio_pct")) or 100.0

    kpi_updates = {
        "statUpdatedAt": html.escape(str(data.get("updated_at_human") or "Актуально"), quote=False),
        "kpiTreasuryBalance": fmt_rub(t.get("balance_rub"), False),
        "kpiTreasuryGrowth": fmt_rub(t.get("net_growth_rub"), True),
        "kpiShopBuyRub": fmt_rub(buy_rub, False),
        "kpiShopBuyTx": "Сделок: " + fmt_int(s.get("buy_tx")),
        "kpiShopBuyItems": fmt_int(s.get("buy_items")) + " шт.",
        "kpiShopSellRub": fmt_rub(sell_rub, False),
        "kpiShopSellTx": "Сделок: " + fmt_int(s.get("sell_tx")),
        "kpiShopSellItems": fmt_int(s.get("sell_items")) + " шт.",
        "kpiM1Supply": fmt_rub(t.get("m1_supply_rub"), False),
        "kpiPlayersCount": "Игроков: " + fmt_int(players_count),
        "kpiCoverage": f"Казна: {coverage_pct:.1f}%",
        "kpiShopNetProfit": fmt_rub(s.get("net_profit_rub"), True),
        "kpiTodayIncome": fmt_rub(t.get("today_income_rub"), True),
        "kpiTodayBuyLabel": "Магазин: " + fmt_rub(today_shop_buy, False),
        "kpiTodayOtherIncome": "Услуги: " + fmt_rub(today_other_inc, False),
        "kpiTodayExpense": today_exp_text,
        "kpiTodaySellLabel": "Скупка: " + fmt_rub(today_shop_sell, False),
        "kpiTodayRewardsExpense": "Премии: " + fmt_rub(today_rewards_exp, False),
        "kpiMedianBalance": fmt_rub(t.get("median_balance_rub"), False),
        "kpiMeanBalance": fmt_rub(t.get("mean_balance_rub"), False),
        "barBuyLabel": f"{fmt_rub(buy_rub, False)}, {buy_pct}% оборота",
        "barSellLabel": f"{fmt_rub(sell_rub, False)}, {sell_pct}% оборота",
    }

    updated = html_text
    for elem_id, value in kpi_updates.items():
        updated = replace_element_inner_by_id(
            updated, elem_id, value, tag_pattern=r"(?:div|span|strong)"
        )
    updated = update_ratio_bar_width(updated, buy_pct)
    updated = replace_current_stats_data(updated, data)
    return updated


def extract_visible_text(raw_html: str) -> tuple[str, str]:
    stripped = re.sub(r"<!--.*?-->", " ", raw_html, flags=re.DOTALL)
    stripped = re.sub(
        r"<script\b[^>]*>.*?</script>", " ", stripped, flags=re.DOTALL | re.IGNORECASE
    )
    stripped = re.sub(
        r"<style\b[^>]*>.*?</style>", " ", stripped, flags=re.DOTALL | re.IGNORECASE
    )
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    return stripped, html.unescape(stripped)


def assert_clean_visible_html(filename: str, raw_html: str) -> None:
    raw_vis, unescaped_vis = extract_visible_text(raw_html)
    for label, text in (("raw", raw_vis), ("unescaped", unescaped_vis)):
        for ch in FORBIDDEN_VISIBLE_CHARS:
            idx = text.find(ch)
            if idx != -1:
                snippet = text[max(0, idx - 30) : idx + 30].replace("\n", " ")
                raise ValueError(
                    f"Forbidden visible character {ch!r} ({label}) in {filename} near: {snippet!r}"
                )


def write_utf8_lf(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    return True


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    dest_json_path = repo_root / "stats_data.json"
    src_json_path = Path(argv[1]).expanduser() if len(argv) > 1 else dest_json_path

    if not src_json_path.exists():
        raise FileNotFoundError(f"Source stats JSON not found: {src_json_path}")

    raw_src = src_json_path.read_text(encoding="utf-8")
    data = validate_stats_data(json.loads(raw_src))
    normalized_json = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    index_path = repo_root / "index.html"
    stats_path = repo_root / "stats.html"

    index_orig = index_path.read_text(encoding="utf-8")
    stats_orig = stats_path.read_text(encoding="utf-8")

    index_next = update_index_html(index_orig, data)
    stats_next = update_stats_html(stats_orig, data)

    assert_clean_visible_html("index.html", index_next)
    assert_clean_visible_html("stats.html", stats_next)

    json_written = False
    if src_json_path.resolve() != dest_json_path.resolve() or (
        not dest_json_path.exists()
        or dest_json_path.read_text(encoding="utf-8") != normalized_json
    ):
        json_written = write_utf8_lf(dest_json_path, normalized_json)

    index_written = write_utf8_lf(index_path, index_next)
    stats_written = write_utf8_lf(stats_path, stats_next)

    print(
        f"sync_daily_stats complete: snapshot={data.get('updated_at_iso', 'unknown')} "
        f"(stats_data.json={'updated' if json_written else 'unchanged'}, "
        f"index.html={'updated' if index_written else 'unchanged'}, "
        f"stats.html={'updated' if stats_written else 'unchanged'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
