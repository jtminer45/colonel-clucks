#!/usr/bin/env python3
"""Make a Colonel Clucks receipt PDF (and a PNG for WhatsApp) from an order JSON file.

Usage: python3 make_receipt.py order.json out_dir

order.json:
{
  "receipt_no": "CC-0001",
  "receipt_date": "2026-12-05",
  "customer": "Ada Okafor",
  "phone": "0803 000 0000",
  "mode": "Delivery",            # or "Pickup"
  "area": "Rayfield",            # delivery area (optional)
  "date_wanted": "Fri 18 Dec",
  "items": [ {"type": "whole", "qty": 2, "price": 15000},
             {"type": "cut",   "qty": 1, "price": 16000} ],
  "paid": 10000
}
Writes <out_dir>/<receipt_no>.pdf and <out_dir>/<receipt_no>.png
"""
import base64, html, json, os, sys, datetime
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))


def naira(n):
    return "₦" + f"{float(n):,.0f}"


def nice_date(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10]).strftime("%-d %b %Y")
    except ValueError:
        return str(s)


def main(order_path, out_dir):
    o = json.load(open(order_path))
    e = lambda v: html.escape(str(v if v is not None else ""))
    rows, total = [], 0.0
    for it in o["items"]:
        qty, price = float(it["qty"]), float(it["price"])
        amt = qty * price
        total += amt
        label = "Whole broiler" if str(it["type"]).lower().startswith("whole") else "Cut broiler"
        rows.append(f'<tr><td>{label}</td><td class="r">{qty:g}</td>'
                    f'<td class="r">{naira(price)}</td><td class="r">{naira(amt)}</td></tr>')
    paid = float(o.get("paid") or 0)
    balance = total - paid
    mode = str(o.get("mode") or "Pickup")
    if mode.lower().startswith("deliver"):
        mode_label, mode_detail = "Delivery", "Delivery in Jos" + (f": {o['area']}" if o.get("area") else "")
    else:
        mode_label, mode_detail = "Pickup", "Pickup from the farm"
    chicken = base64.b64encode(open(os.path.join(HERE, "happy-chicken.png"), "rb").read()).decode()
    first = (str(o["customer"]).split() or ["friend"])[0].capitalize()
    t = open(os.path.join(HERE, "receipt.html"), encoding="utf-8").read()
    subs = {
        "{{RECEIPT_NO}}": e(o["receipt_no"]),
        "{{RECEIPT_DATE}}": e(nice_date(o.get("receipt_date") or datetime.date.today().isoformat())),
        "{{CUSTOMER}}": e(o["customer"]),
        "{{FIRST_NAME}}": e(first),
        "{{PHONE}}": e(o.get("phone", "")),
        "{{MODE_LABEL}}": e(mode_label),
        "{{MODE_DETAIL}}": e(mode_detail),
        "{{DATE_WANTED}}": e(o.get("date_wanted", "")),
        "{{ITEM_ROWS}}": "\n".join(rows),
        "{{TOTAL}}": naira(total),
        "{{PAID}}": naira(paid),
        "{{BALANCE}}": naira(balance),
        "{{STAMP}}": "PAID IN FULL" if balance <= 0 else "ORDER CONFIRMED",
        "{{CHICKEN_SRC}}": "data:image/png;base64," + chicken,
    }
    for k, v in subs.items():
        t = t.replace(k, v)
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, f"{o['receipt_no']}.html")
    open(tmp, "w", encoding="utf-8").write(t)
    pdf = os.path.join(out_dir, f"{o['receipt_no']}.pdf")
    png = os.path.join(out_dir, f"{o['receipt_no']}.png")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 397, "height": 926}, device_scale_factor=2)
        pg.goto("file://" + tmp)
        pg.pdf(path=pdf, width="105mm", height="245mm", print_background=True)
        pg.locator(".page").screenshot(path=png)
        b.close()
    os.remove(tmp)
    print(json.dumps({"pdf": pdf, "png": png, "total": total, "paid": paid, "balance": balance}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
