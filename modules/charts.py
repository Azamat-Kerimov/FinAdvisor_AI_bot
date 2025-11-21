# modules/charts.py
import io
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
from modules.db import db


# -------------------------------------------------------------
# 1) DIAGRAM: Расходы за текущий месяц (donut)
# -------------------------------------------------------------
async def make_expense_chart(db_pool, user_id: int):
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)

    rows = await db_pool.fetch(
        """
        SELECT category, SUM(amount) as total
        FROM transactions
        WHERE user_id=$1 AND amount < 0 AND created_at >= $2
        GROUP BY category
        """,
        user_id, month_start
    )

    if not rows:
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.text(0.5, 0.5, "Нет расходов", ha="center", va="center")
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=200, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf

    labels = []
    values = []

    for r in rows:
        labels.append(r["category"] or "Без категории")
        values.append(abs(float(r["total"])))

    fig, ax = plt.subplots(figsize=(6, 6))

    wedges, texts = ax.pie(values, wedgeprops=dict(width=0.4))

    total = sum(values)
    ax.text(0, 0, f"{int(total)} ₽", ha='center', va='center', fontsize=16, fontweight='bold')

    ax.legend(wedges, labels, title="Категории", loc="upper center", bbox_to_anchor=(0.5, 1.1))

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=200, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf


# -------------------------------------------------------------
# 2) BAR: Прогресс целей (progress bars)
# -------------------------------------------------------------
async def make_goals_progress_chart(db_pool, user_id: int):
    goals = await db_pool.fetch(
        """
        SELECT target, current
        FROM goals
        WHERE user_id=$1 ORDER BY id
        """,
        user_id
    )

    if not goals:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "Цели не созданы", ha="center", va="center")
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=200, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf

    titles = [f"Цель {i+1}" for i in range(len(goals))]
    targets = [g["target"] for g in goals]
    currents = [g["current"] for g in goals]

    percentages = [min(100, int(currents[i] / targets[i] * 100)) for i in range(len(goals))]

    fig, ax = plt.subplots(figsize=(7, 4))

    y_pos = np.arange(len(goals))

    ax.barh(y_pos, percentages, color="green")
    ax.barh(y_pos, [100 - p for p in percentages], left=percentages, color="lightgray")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(titles)
    ax.invert_yaxis()

    for i, pct in enumerate(percentages):
        ax.text(pct + 1, i, f"{pct} %", va='center')

    ax.set_title("Прогресс целей")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=200, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf
