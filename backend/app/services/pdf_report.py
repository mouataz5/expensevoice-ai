import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def simple_table_pdf(title: str, headers: list[str], rows: list[list[str]]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, title)
    y -= 25

    c.setFont("Helvetica-Bold", 10)
    x_positions = [40, 140, 240, 340, 440]  # simple columns
    for i, h in enumerate(headers[:5]):
        c.drawString(x_positions[i], y, str(h)[:18])
    y -= 15
    c.setFont("Helvetica", 9)

    for row in rows:
        if y < 60:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 9)

        for i, cell in enumerate(row[:5]):
            c.drawString(x_positions[i], y, str(cell)[:18])
        y -= 12

    c.showPage()
    c.save()
    return buf.getvalue()
