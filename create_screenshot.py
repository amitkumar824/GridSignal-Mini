import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def create_dashboard_screenshot():
    width, height = 1280, 840
    img = Image.new("RGB", (width, height), color="#f8fafc")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 20)
        font_subtitle = ImageFont.truetype("arial.ttf", 12)
        font_h2 = ImageFont.truetype("arial.ttf", 15)
        font_stat_num = ImageFont.truetype("arial.ttf", 26)
        font_stat_label = ImageFont.truetype("arial.ttf", 11)
        font_body = ImageFont.truetype("arial.ttf", 12)
        font_mono = ImageFont.truetype("consolas.ttf", 11)
        font_badge = ImageFont.truetype("arial.ttf", 10)
    except Exception:
        font_title = font_subtitle = font_h2 = font_stat_num = font_stat_label = font_body = font_mono = font_badge = ImageFont.load_default()

    # 1. Top Navigation Bar (Slate-900)
    draw.rectangle([0, 0, width, 64], fill="#0f172a")
    # Logo square
    draw.rounded_rectangle([24, 14, 60, 50], radius=6, fill="#0d9488")
    draw.text((32, 22), "GS", fill="#0f172a", font=font_title)
    draw.text((72, 17), "GridSignal Mini", fill="#ffffff", font=font_title)
    draw.rounded_rectangle([220, 20, 310, 36], radius=4, fill="#134e4a")
    draw.text((228, 22), "Django Edition", fill="#2dd4bf", font=font_badge)
    draw.text((72, 41), "Utility Incident Intelligence & Cross-Type Pair Analytics", fill="#94a3b8", font=font_subtitle)

    # Top right pills
    # Health status pill
    draw.rounded_rectangle([720, 18, 840, 46], radius=6, fill="#1e293b")
    draw.ellipse([732, 28, 740, 36], fill="#34d399")
    draw.text((748, 24), "API: Healthy", fill="#e2e8f0", font=font_subtitle)

    # Admin button
    draw.rounded_rectangle([850, 18, 950, 46], radius=6, fill="#334155")
    draw.text((862, 25), "Django Admin", fill="#ffffff", font=font_stat_label)

    # Action buttons
    draw.rounded_rectangle([960, 18, 1070, 46], radius=6, fill="#0d9488")
    draw.text((974, 25), "Run Seed Import", fill="#ffffff", font=font_stat_label)

    draw.rounded_rectangle([1080, 18, 1195, 46], radius=6, fill="#d97706")
    draw.text((1092, 25), "Run Replay Import", fill="#ffffff", font=font_stat_label)

    draw.rounded_rectangle([1205, 18, 1260, 46], radius=6, fill="#334155")
    draw.text((1214, 25), "Refresh", fill="#ffffff", font=font_stat_label)

    # 2. Rules / Banner
    draw.rounded_rectangle([24, 76, width - 24, 134], radius=10, fill="#1e293b", outline="#334155")
    draw.text((40, 86), "Correlation Engine Rules & Conflict Policy", fill="#f1f5f9", font=font_h2)
    draw.text((40, 108), "Correlation: Match GAS <-> ELECTRIC if Planar Distance <= 200 ft AND Reporting Time Diff <= 6 hours (both inclusive).", fill="#2dd4bf", font=font_subtitle)
    draw.text((40, 122), "Conflict Policy: Identical duplicates skipped. Conflicting duplicates update record (Last-Write-Wins). Malformed timestamps skipped with logged warning.", fill="#fde68a", font=font_subtitle)

    # 3. Four Metric Stat Cards
    card_w = (width - 48 - 36) // 4
    cards_data = [
        ("TOTAL INCIDENTS", "11", "Stored in SQLite", "#0f172a", "#f1f5f9"),
        ("GAS INCIDENTS", "4", "Utility: GAS", "#ea580c", "#fff7ed"),
        ("ELECTRIC INCIDENTS", "7", "Utility: ELECTRIC", "#2563eb", "#eff6ff"),
        ("CORRELATED ALERTS", "6", "Unique Pairs <=200ft, <=6hr", "#0f766e", "#f0fdfa"),
    ]

    card_y = 146
    for i, (title, num, desc, text_col, bg_col) in enumerate(cards_data):
        cx = 24 + i * (card_w + 12)
        draw.rounded_rectangle([cx, card_y, cx + card_w, card_y + 88], radius=10, fill="#ffffff", outline="#e2e8f0")
        draw.text((cx + 16, card_y + 12), title, fill="#64748b", font=font_stat_label)
        draw.text((cx + 16, card_y + 28), num, fill=text_col, font=font_stat_num)
        draw.text((cx + 16, card_y + 64), desc, fill="#94a3b8", font=font_stat_label)

    # 4. Table Card (Correlated Alerts)
    tbl_y = 246
    draw.rounded_rectangle([24, tbl_y, width - 24, height - 48], radius=10, fill="#ffffff", outline="#e2e8f0")

    # Table Header Tab Bar
    draw.rounded_rectangle([36, tbl_y + 14, 210, tbl_y + 44], radius=6, fill="#0f766e")
    draw.text((48, tbl_y + 22), "Correlated Alerts (6)", fill="#ffffff", font=font_body)

    draw.rounded_rectangle([220, tbl_y + 14, 410, tbl_y + 44], radius=6, fill="#f8fafc", outline="#cbd5e1")
    draw.text((232, tbl_y + 22), "All Incidents Inventory (11)", fill="#475569", font=font_body)

    # Table Columns Header
    hdr_y = tbl_y + 54
    draw.rectangle([24, hdr_y, width - 24, hdr_y + 30], fill="#f1f5f9")
    draw.text((40, hdr_y + 8), "#", fill="#64748b", font=font_stat_label)
    draw.text((80, hdr_y + 8), "GAS INCIDENT", fill="#64748b", font=font_stat_label)
    draw.text((280, hdr_y + 8), "ELECTRIC INCIDENT", fill="#64748b", font=font_stat_label)
    draw.text((480, hdr_y + 8), "PLANAR DISTANCE", fill="#64748b", font=font_stat_label)
    draw.text((680, hdr_y + 8), "TIME GAP", fill="#64748b", font=font_stat_label)
    draw.text((880, hdr_y + 8), "CLASSIFICATION / BOUNDARY STATUS", fill="#64748b", font=font_stat_label)

    # 6 Alert Rows
    rows = [
        ("1", "G-X4 (LOW, OPEN)", "E-X7 (LOW, OPEN)", "0.00 ft", "60.0 min (1.00 hr)", "Within Threshold", False),
        ("2", "G-X1 (HIGH, OPEN)", "E-X3 (LOW, CLOSED)", "0.00 ft", "300.0 min (5.00 hr)", "Within Threshold (CLOSED matches)", False),
        ("3", "G-X4 (LOW, OPEN)", "E-X6 (LOW, OPEN)", "10.00 ft", "0.0 min (0.00 hr)", "Within Threshold", False),
        ("4", "G-X3 (MEDIUM, OPEN)", "E-X7 (LOW, OPEN)", "90.00 ft", "180.0 min (3.00 hr)", "Within Threshold", False),
        ("5", "G-X3 (MEDIUM, OPEN)", "E-X6 (LOW, OPEN)", "100.00 ft", "120.0 min (2.00 hr)", "Within Threshold", False),
        ("6", "G-X1 (HIGH, OPEN)", "E-X1 (MEDIUM, OPEN)", "200.00 ft", "360.0 min (6.00 hr)", "EXACT LIMIT (200 ft & 6 hrs)", True),
    ]

    row_y = hdr_y + 30
    for r_idx, (num, gas_info, elec_info, dist, gap, status, is_exact) in enumerate(rows):
        fill_bg = "#faf5ff" if is_exact else ("#ffffff" if r_idx % 2 == 0 else "#f8fafc")
        draw.rectangle([24, row_y, width - 24, row_y + 44], fill=fill_bg, outline="#f1f5f9")

        draw.text((40, row_y + 14), num, fill="#94a3b8", font=font_mono)
        draw.text((80, row_y + 12), gas_info, fill="#c2410c", font=font_body)
        draw.text((280, row_y + 12), elec_info, fill="#1d4ed8", font=font_body)
        draw.text((480, row_y + 12), dist, fill="#0f172a", font=font_mono)
        draw.text((680, row_y + 12), gap, fill="#0f172a", font=font_mono)

        badge_x = 880
        badge_y = row_y + 10
        if is_exact:
            draw.rounded_rectangle([badge_x, badge_y, badge_x + 220, badge_y + 24], radius=12, fill="#f3e8ff", outline="#d8b4fe")
            draw.text((badge_x + 12, badge_y + 5), status, fill="#6b21a8", font=font_badge)
        else:
            draw.rounded_rectangle([badge_x, badge_y, badge_x + 230, badge_y + 24], radius=12, fill="#ecfdf5", outline="#a7f3d0")
            draw.text((badge_x + 12, badge_y + 5), status, fill="#047857", font=font_badge)

        row_y += 44

    draw.text((40, height - 32), "GridSignal Mini · Internal Utility Incident Intelligence Platform · Django + SQLite + React", fill="#94a3b8", font=font_subtitle)
    draw.text((width - 240, height - 32), "Persistent Storage: db.sqlite3", fill="#94a3b8", font=font_mono)

    out_dir = Path(__file__).resolve().parent / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "dashboard_screenshot.png"
    img.save(out_path, format="PNG")
    print(f"Saved screenshot to {out_path} ({out_path.stat().st_size} bytes)")

if __name__ == "__main__":
    create_dashboard_screenshot()
