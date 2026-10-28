"""Renders a client-facing quote proposal PDF with ReportLab. Internal cost/margin data is never included."""
from decimal import Decimal
from io import BytesIO
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.app.core.config import settings

_BILLING_LABEL = {"MRC": "Monthly", "NRC": "One-time", "USAGE": "Usage"}


def _money(value, currency: str) -> str:
    return f"{currency} {Decimal(value or 0):,.2f}"


def _p(text: Optional[str], style) -> Paragraph:
    return Paragraph(escape(text or ""), style)


def build_quote_pdf(quote, customer, contact, address, prepared_by: str) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Proposal {quote.quote_number} v{quote.version}", author=settings.COMPANY_NAME,
    )
    ss = getSampleStyleSheet()
    brand = colors.HexColor("#1d4ed8")
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=20, textColor=brand, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading3"], fontSize=10, textColor=colors.HexColor("#334155"), spaceBefore=10, spaceAfter=3)
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.HexColor("#64748b"), leading=10)
    cell = ParagraphStyle("cell", parent=body, fontSize=8.5, leading=10.5)
    cur = quote.currency or "USD"

    story = [Paragraph(escape(settings.COMPANY_NAME), h1), Paragraph("Sales Proposal", h2)]

    meta = [
        ["Quote #", f"{quote.quote_number}  (version {quote.version})"],
        ["Date", quote.created_at.strftime("%d %b %Y") if quote.created_at else ""],
        ["Valid until", quote.valid_until.strftime("%d %b %Y") if quote.valid_until else "On request"],
        ["Prepared by", prepared_by],
    ]
    cust_lines = [customer.display_name or customer.legal_name]
    if customer.display_name and customer.display_name != customer.legal_name:
        cust_lines.append(customer.legal_name)
    if contact:
        cust_lines.append(f"Attn: {contact.first_name} {contact.last_name}")
        cust_lines.append(contact.email)
    elif customer.email:
        cust_lines.append(customer.email)
    if address:
        cust_lines.append(", ".join(x for x in [address.line1, address.line2, address.city, address.state, address.postal_code, address.country] if x))
    header = Table(
        [[Paragraph("<b>Prepared for</b><br/>" + "<br/>".join(escape(x) for x in cust_lines), body),
          Table([[_p(k, small), _p(v, body)] for k, v in meta], colWidths=[24 * mm, 56 * mm])]],
        colWidths=[90 * mm, 84 * mm],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [header, Spacer(1, 6)]
    if quote.title:
        story.append(Paragraph(f"<b>{escape(quote.title)}</b>", body))
    if quote.description:
        story.append(_p(quote.description, body))

    rows = [["#", "Item", "Billing", "Qty", "Unit price", "Disc %", "Total"]]
    for i, it in enumerate(quote.items, 1):
        name = f"<b>{escape(it.product_name or '')}</b><br/><font size=7 color='#64748b'>{escape(it.sku or '')}</font>"
        rows.append([
            str(i), Paragraph(name, cell), _BILLING_LABEL.get(it.billing_type, it.billing_type), str(it.quantity),
            _money(it.unit_price, cur), f"{Decimal(it.discount_percentage or 0):.1f}", _money(it.total_price, cur),
        ])
    tbl = Table(rows, colWidths=[8 * mm, 56 * mm, 18 * mm, 12 * mm, 28 * mm, 14 * mm, 38 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [Paragraph("Line items", h2), tbl, Spacer(1, 8)]

    totals = [["Subtotal", _money(quote.subtotal, cur)]]
    if Decimal(quote.discount_amount or 0) > 0:
        totals.append(["Discount", "-" + _money(quote.discount_amount, cur)])
    if Decimal(quote.tax_amount or 0) > 0:
        totals.append(["Tax", _money(quote.tax_amount, cur)])
    totals.append(["Total", _money(quote.total_amount, cur)])
    t2 = Table(totals, colWidths=[30 * mm, 40 * mm], hAlign="RIGHT")
    t2.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("LINEABOVE", (0, -1), (-1, -1), 0.8, brand),
    ]))
    story.append(t2)

    mrc = sum((Decimal(i.total_price) for i in quote.items if i.billing_type == "MRC"), Decimal("0"))
    nrc = sum((Decimal(i.total_price) for i in quote.items if i.billing_type != "MRC"), Decimal("0"))
    if mrc > 0:
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"Recurring (monthly): <b>{_money(mrc, cur)}</b> &nbsp;|&nbsp; One-time: <b>{_money(nrc, cur)}</b>", small))

    if quote.notes:
        story += [Paragraph("Notes", h2), _p(quote.notes, body)]
    story += [Paragraph("Terms &amp; conditions", h2), _p(settings.QUOTE_TERMS, small)]
    if settings.COMPANY_ADDRESS or settings.COMPANY_EMAIL:
        story += [Spacer(1, 6), _p(" | ".join(x for x in [settings.COMPANY_ADDRESS, settings.COMPANY_EMAIL] if x), small)]

    doc.build(story)
    return buf.getvalue()
