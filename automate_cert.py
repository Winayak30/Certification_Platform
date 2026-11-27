"""Create GDGoC LNCTS tenure certificates from members.csv.

Safe defaults: renders PNGs only. Email is sent only with --send and a Gmail
App Password in the GMAIL_APP_PASSWORD environment variable.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import smtplib
import sys
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "template.png"
CSV_FILE = ROOT / "members.csv"
OUT_DIR = ROOT / "generated_certs"
# Roboto closely matches the reference. Google Sans files are also accepted.
FONT_REGULAR = ROOT / "Roboto-Regular.ttf"
FONT_BOLD = ROOT / "Roboto-Bold.ttf"
SENDER = os.getenv("GMAIL_ADDRESS", "")
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Relative positions tuned to the supplied 1200x900 example. Adjust these for
# the actual template; they scale with image size. Each (x,y) is normalized.
TEXT_LEFT = 0.43
SERIAL_AT = (TEXT_LEFT, 0.375)
AWARDED_AT = (TEXT_LEFT, 0.435)
NAME_AT = (TEXT_LEFT, 0.500)
PARAGRAPH_BOX = (TEXT_LEFT, 0.565, 0.96, 0.72)
INK = (13, 71, 43)

REQUIRED_COLUMNS = {"name", "email", "designation", "team", "serial"}
COPY_PREFIX = "For their exceptional dedication and impactful contributions to the student developer community. We proudly recognize their outstanding work as a"
COPY_SUFFIX = "during the 2025-2026 tenure."


def font(path: Path, size: int, fallback_bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # Prefer the requested Roboto file, then Google Sans if supplied. Both are
    # closer to the reference than the default Windows font.
    google_name = "GoogleSans-Bold.ttf" if fallback_bold else "GoogleSans-Regular.ttf"
    candidates = [path, ROOT / google_name,
                  Path("C:/Windows/Fonts/arialbd.ttf" if fallback_bold else "C:/Windows/Fonts/arial.ttf")]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def fit_font(draw: ImageDraw.ImageDraw, text: str, path: Path, max_size: int,
             max_width: int, bold: bool = False, min_size: int = 14):
    for size in range(max_size, min_size - 1, -1):
        f = font(path, size, bold)
        if draw.textbbox((0, 0), text, font=f)[2] <= max_width:
            return f
    return font(path, min_size, bold)


def wrap_words(draw: ImageDraw.ImageDraw, text: str, f: Any, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), trial, font=f)[2] > width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._") or "member"


def render(row: dict[str, Any], output: Path) -> None:
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Certificate template not found: {TEMPLATE}")
    image = Image.open(TEMPLATE).convert("RGB")
    draw = ImageDraw.Draw(image)
    w, h = image.size

    serial = str(row["serial"]).strip()
    name = str(row["name"]).strip()
    designation = str(row["designation"]).strip()
    team = str(row["team"]).strip()

    # Set font sizes relative to the supplied 1200x900 sample.
    scale = min(w / 1200, h / 900)
    content_x = round(TEXT_LEFT * w)
    draw.text((content_x, round(SERIAL_AT[1] * h)), f"Serial: {serial}",
              font=font(FONT_REGULAR, max(14, round(22 * scale))), fill=INK, anchor="lm")
    draw.text((content_x, round(AWARDED_AT[1] * h)), "is awarded to",
              font=font(FONT_REGULAR, max(15, round(24 * scale))), fill=INK, anchor="lm")
    name_font = fit_font(draw, name, FONT_BOLD, max(28, round(52 * scale)), int(w * 0.53), bold=True)
    draw.text((content_x, round(NAME_AT[1] * h)), name,
              font=name_font, fill=INK, anchor="lm")

    paragraph = f"{COPY_PREFIX} {designation} of the {team} {COPY_SUFFIX}"
    x0, y0, x1, y1 = (round(PARAGRAPH_BOX[0] * w), round(PARAGRAPH_BOX[1] * h),
                      round(PARAGRAPH_BOX[2] * w), round(PARAGRAPH_BOX[3] * h))
    para_font = font(FONT_REGULAR, max(15, round(22 * scale)))
    lines = wrap_words(draw, paragraph, para_font, x1 - x0)
    line_height = round(para_font.size * 1.35)
    if len(lines) * line_height > y1 - y0:
        para_font = font(FONT_REGULAR, max(13, round(19 * scale)))
        lines = wrap_words(draw, paragraph, para_font, x1 - x0)
        line_height = round(para_font.size * 1.3)
    y = y0
    for line in lines:
        draw.text((x0, y), line, font=para_font, fill=INK, anchor="lt")
        y += line_height
    if y > y1:
        raise ValueError("Paragraph does not fit. Reduce font size or enlarge PARAGRAPH_BOX.")

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def read_members() -> list[dict[str, Any]]:
    if CSV_FILE.exists():
        with CSV_FILE.open("r", newline="", encoding="utf-8-sig") as f:
            raw_rows = list(csv.reader(f))
        if not raw_rows:
            raise ValueError("members.csv is empty")
        headers = [str(v or "").strip().lower() for v in raw_rows[0]]
        data_rows = raw_rows[1:]
    else:
        raise FileNotFoundError("Put members.csv beside this script")
    # Accept the workbook's existing "E-mail" heading as well as "Email".
    headers = ["email" if h in {"e-mail", "email address"} else h for h in headers]
    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        raise ValueError("Missing column(s): " + ", ".join(sorted(missing)) +
                         ". Required headers: Name, E-mail (or Email), Designation, Team, Serial")
    index = {name: headers.index(name) for name in REQUIRED_COLUMNS}
    members = []
    seen_serials: set[str] = set()
    for excel_row, values in enumerate(data_rows, start=2):
        record = {key: (values[i] if i < len(values) else None) for key, i in index.items()}
        if all(v is None or str(v).strip() == "" for v in record.values()):
            continue
        for key in ("name", "email", "designation", "team", "serial"):
            if record[key] is None or not str(record[key]).strip():
                raise ValueError(f"Row {excel_row}: {key.title()} is blank")
            record[key] = str(record[key]).strip()
        if "@" not in record["email"]:
            raise ValueError(f"Row {excel_row}: email does not look valid")
        if record["serial"] in seen_serials:
            raise ValueError(f"Duplicate serial number {record['serial']} at row {excel_row}")
        seen_serials.add(record["serial"])
        members.append(record)
    if not members:
        raise ValueError("No member rows found")
    return members


def send_email(member: dict[str, Any], attachment: Path) -> None:
    message = EmailMessage()
    message["Subject"] = "With gratitude: Your GDGoC LNCTS Tenure Completion Certificate"
    message["From"] = SENDER
    message["To"] = member["email"]
    message.set_content(
        f"Dear {member['name']},\n\n"
        "As your GDGoC LNCTS tenure comes to a close, we want to thank you for "
        "the time, care, and energy you brought to our community. Your contributions "
        "helped make this a place where students could learn, build, and grow together.\n\n"
        "We’re grateful to have had you as part of the team, and proud to recognize "
        "your work with the attached Tenure Completion Certificate. We hope you carry "
        "the friendships, experiences, and memories from this journey with you into "
        "everything you do next.\n\n"
        "Wishing you every success in what lies ahead.\n\n"
        "With gratitude,\n"
        "GDGoC LNCTS"
    )
    message.add_attachment(attachment.read_bytes(), maintype="image", subtype="png",
                           filename=attachment.name)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.starttls()
        server.login(SENDER, APP_PASSWORD)
        server.send_message(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate certificates; email only with --send.")
    parser.add_argument("--send", action="store_true", help="Email certificates using Gmail SMTP")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between emails (default: 2)")
    args = parser.parse_args()
    try:
        members = read_members()
        OUT_DIR.mkdir(exist_ok=True)
        generated = []
        for member in members:
            path = OUT_DIR / f"{safe_filename(member['serial'])}_{safe_filename(member['name'])}.png"
            render(member, path)
            generated.append((member, path))
            print(f"Created: {path.name}")
        if not args.send:
            print(f"\nPreview mode: created {len(generated)} certificate(s); no email was sent.")
            print("Inspect generated_certs, then use --send only after confirming every row and image.")
            return 0
        if not SENDER or not APP_PASSWORD:
            raise ValueError("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables before --send")
        for i, (member, path) in enumerate(generated):
            send_email(member, path)
            print(f"Emailed: {member['email']}")
            if i + 1 < len(generated):
                time.sleep(max(0, args.delay))
        print(f"\nSent {len(generated)} email(s).")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
