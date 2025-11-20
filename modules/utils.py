# modules/utils.py
import difflib
import re
import os
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CHART_DIR = "/tmp"
os.makedirs(CHART_DIR, exist_ok=True)

CANONICAL_CATEGORIES = [
    "Такси", "Еда", "Продукты", "Кафе", "Развлечения",
    "Транспорт", "Коммуналка", "Одежда", "Зарплата", "Подарки",
    "Аптека", "Образование", "Инвестиции", "Связь"
]

def normalize_category(raw: str) -> str:
    if not raw:
        return None
    s = raw.strip().lower()
    s_clean = re.sub(r"[^\w\u0400-\u04FF]+", " ", s).strip()
    # exact match
    for c in CANONICAL_CATEGORIES:
        if c.lower() == s_clean:
            return c
    # fuzzy match
    match = difflib.get_close_matches(s_clean, [c.lower() for c in CANONICAL_CATEGORIES], n=1, cutoff=0.6)
    if match:
        found = match[0]
        for c in CANONICAL_CATEGORIES:
            if c.lower() == found:
                return c
    return s_clean.capitalize()

# parse amount token like "-2500", "+1.5k", "1.2m", "2500"
UNIT_MAP = {"k": 1_000, "к": 1_000, "m": 1_000_000, "м": 1_000_000, "млн": 1_000_000}
def parse_amount_token(s: str):
    s0 = s.strip().lower().replace(" ", "").replace("\u2009","")
    sign = 1
    if s0.startswith("+"):
        s0 = s0[1:]; sign = 1
    elif s0.startswith("-"):
        s0 = s0[1:]; sign = -1
    s0 = s0.replace(",", ".")
    m = re.match(r"^([\d\.]+)([a-zа-яё%]*)$", s0, re.IGNORECASE)
    if not m:
        raise ValueError("invalid amount")
    num = float(m.group(1))
    unit = m.group(2)
    mult = 1
    if unit:
        for k,v in UNIT_MAP.items():
            if unit.startswith(k):
                mult = v
                break
    return int(round(num*mult*sign))

# quick free-text parse: finds first amount token and returns (amount, guessed_category, description)
def smart_parse_free_text(text: str):
    if not text:
        return None
    m = re.search(r"([+-]?\s*\d[\d\s\.,]*(?:k|K|m|M|к|К|м|М|млн)?)", text, re.IGNORECASE)
    if not m:
        return None
    token = m.group(1)
    try:
        amount = parse_amount_token(token)
    except Exception:
        return None
    left = (text[:m.start()] + " " + text[m.end():]).strip()
    category = None
    description = left.strip() if left else None
    # try to find keyword
    if left:
        for c in CANONICAL_CATEGORIES:
            if c.lower() in left.lower():
                category = c
                break
    return (amount, category, description)

# donut chart
def generate_donut(categories_dict, user_id):
    labels = list(categories_dict.keys())
    sizes = [float(v) for v in categories_dict.values()]
    total = sum(sizes)
    if total == 0:
        return None
    fig, ax = plt.subplots(figsize=(6,6))
    wedges, texts = ax.pie(sizes, wedgeprops=dict(width=0.4), startangle=-40)
    ax.text(0, 0, f"{int(total)}₽", ha='center', va='center', fontsize=16, fontweight='bold')
    ax.legend(wedges, labels, title="Категории", bbox_to_anchor=(0.5,1.12), loc="center", ncol=2)
    ax.set(aspect="equal")
    fname = f"{CHART_DIR}/donut_{user_id}_{int(datetime.utcnow().timestamp())}.png"
    plt.tight_layout()
    plt.savefig(fname)
    plt.close()
    return fname

# goals progress
def generate_goals_progress(goals_list, available_balance, user_id):
    titles = [g['title'] for g in goals_list]
    targets = [float(g['target']) for g in goals_list]
    currents = [float(g.get('current', 0)) for g in goals_list]
    remaining_balance = float(available_balance or 0)
    progresses = []
    for cur, tgt in zip(currents, targets):
        need = tgt - cur
        allocate = 0
        if remaining_balance > 0 and need > 0:
            allocate = min(need, remaining_balance)
            remaining_balance -= allocate
        total_filled = cur + allocate
        pct = int(round(min(100, (total_filled / tgt) * 100))) if tgt else 0
        progresses.append(pct)
    # plot
    fig, ax = plt.subplots(figsize=(8, max(2, len(titles)*0.6)))
    y_pos = list(range(len(titles)))
    ax.barh(y_pos, [100]*len(titles), color='#e0e0e0')
    ax.barh(y_pos, progresses, color='#4CAF50')
    ax.set_yticks(y_pos)
    ax.set_yticklabels([f"{t} — {p}%" for t,p in zip(titles,progresses)])
    ax.invert_yaxis()
    ax.set_xlim(0,100)
    ax.set_xlabel("Прогресс (%)")
    ax.set_title("Прогресс по целям")
    plt.tight_layout()
    fname = f"{CHART_DIR}/goals_{user_id}_{int(datetime.utcnow().timestamp())}.png"
    plt.savefig(fname)
    plt.close()
    return fname

# transactions table PNG
def generate_transactions_table_png(rows, user_id):
    if not rows:
        return None
    header = ["Сумма", "Категория", "Дата/Время"]
    data = []
    for r in rows:
        am = f"{int(r['amount'])}₽"
        cat = (r['category'] or "-").capitalize()
        dt = r['created_at'].strftime("%Y-%m-%d %H:%M")
        data.append([am, cat, dt])
    ncols = len(header); nrows = len(data)+1
    fig, ax = plt.subplots(figsize=(8, max(2, 0.4*nrows)))
    ax.set_axis_off()
    from matplotlib.table import Table
    tbl = Table(ax, bbox=[0,0,1,1])
    col_width = 1.0 / ncols
    row_height = 1.0 / nrows
    for j, h in enumerate(header):
        tbl.add_cell(0, j, col_width, row_height, text=h, loc='center', facecolor='#f2f2f2')
    for i, row in enumerate(data, start=1):
        for j, cell in enumerate(row):
            tbl.add_cell(i, j, col_width, row_height, text=cell, loc='center', facecolor='white')
    ax.add_table(tbl)
    fname = f"{CHART_DIR}/table_{user_id}_{int(datetime.utcnow().timestamp())}.png"
    plt.savefig(fname, dpi=150, bbox_inches='tight')
    plt.close()
    return fname
