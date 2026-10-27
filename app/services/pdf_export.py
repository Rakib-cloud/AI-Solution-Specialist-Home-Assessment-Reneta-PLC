from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.authored import _numbered

INK = colors.HexColor("#17211c")
MUTED = colors.HexColor("#5c675f")
LINE = colors.HexColor("#d9d0c2")
HEAD = colors.HexColor("#e7efe9")


def render_policy_pdf(draft: dict) -> bytes:
    buffer = BytesIO()
    header = draft.get("title") or "Leave policy"
    if draft.get("status") != "published":
        header = f"{header} (Draft)"
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title=draft.get("title") or "Leave policy",
    )
    styles = _styles()
    story = _story(draft, styles)
    document.build(story, onFirstPage=lambda canvas, doc: _chrome(canvas, doc, header), onLaterPages=lambda canvas, doc: _chrome(canvas, doc, header), canvasmaker=_numbered_canvas())
    return buffer.getvalue()


def _story(draft: dict, styles) -> list:
    story = [Paragraph(_xml(draft.get("title") or "Leave policy"), styles["title"])]
    if draft.get("disclaimer"):
        story.extend([Spacer(1, 6), Paragraph(_xml(draft["disclaimer"]), styles["note"])])
    meta = [(key, value) for key, value in (draft.get("metadata") or {}).items() if value]
    if meta:
        story.extend([Spacer(1, 10), _meta_table(meta, styles)])
    for number, section, children in _numbered(draft):
        story.extend([Spacer(1, 12), Paragraph(f"{number}. {_xml(section['heading'])}", styles["section"])])
        if section.get("body"):
            story.append(Paragraph(_xml(section["body"]), styles["body"]))
        for child_id, child in children:
            if child.get("kind") == "roles" and not (child.get("heading") or "").strip():
                story.extend([Spacer(1, 8), _roles_table(child.get("rows") or [], styles)])
                continue
            story.extend(_child_flowables(child_id, child, styles))
    number = (draft.get("metadata") or {}).get("Policy number", "")
    version = (draft.get("metadata") or {}).get("Version", "")
    closing = "End of policy."
    if number or version:
        closing = "End of policy. " + ", ".join(part for part in (number, f"Version {version}" if version else "") if part) + "."
    story.extend([Spacer(1, 16), Paragraph(_xml(closing), styles["note"])])
    return story


def _child_flowables(child_id: str, child: dict, styles) -> list:
    flow = []
    heading = child.get("heading") or ""
    kind = child.get("kind") or "text"
    if kind == "entitlements":
        label = f"{child_id} {heading}".strip()
        flow.extend([Spacer(1, 8), Paragraph(_xml(label), styles["subhead"]), _entitlement_table(child.get("rows") or [], styles)])
        return flow
    if kind == "roles":
        label = f"{child_id} {heading}".strip() if heading else child_id
        flow.extend([Spacer(1, 8), Paragraph(_xml(label), styles["subhead"]), _roles_table(child.get("rows") or [], styles)])
        return flow
    if heading:
        flow.extend([Spacer(1, 8), Paragraph(f"{child_id} {_xml(heading)}", styles["subhead"])])
        if child.get("body"):
            flow.append(Paragraph(_xml(child["body"]), styles["body"]))
    elif child.get("body"):
        flow.append(Paragraph(f"<b>{child_id}</b> {_xml(child['body'])}", styles["body"]))
    for index, clause in enumerate(child.get("clauses") or []):
        if not str(clause).strip():
            continue
        marker = chr(ord("a") + index)
        flow.append(Paragraph(f"<b>({marker})</b> {_xml(clause)}", styles["clause"]))
    return flow


def _meta_table(rows: list[tuple[str, str]], styles) -> Table:
    data = [[Paragraph(_xml(key), styles["meta_label"]), Paragraph(_xml(value), styles["meta_value"])] for key, value in rows]
    table = Table(data, colWidths=[42 * mm, 120 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
            ]
        )
    )
    return table


def _entitlement_table(rows: list[dict], styles) -> Table:
    header = ["Leave type", "Entitlement", "Paid", "Section"]
    data = [header]
    for row in rows:
        if not row.get("leave_type") and not row.get("entitlement"):
            continue
        data.append([row.get("leave_type", ""), row.get("entitlement", ""), row.get("paid", ""), row.get("section", "")])
    if len(data) == 1:
        data.append(["—", "", "", ""])
    return _grid(data, [48 * mm, 62 * mm, 22 * mm, 28 * mm])


def _roles_table(rows: list[dict], styles) -> Table:
    data = [["Role", "Responsibility"]]
    for row in rows:
        if not row.get("role") and not row.get("responsibility"):
            continue
        data.append([row.get("role", ""), row.get("responsibility", "")])
    if len(data) == 1:
        data.append(["—", ""])
    return _grid(data, [42 * mm, 118 * mm])


def _grid(data: list[list[str]], widths: list) -> Table:
    wrapped = [[Paragraph(_xml(cell), _styles()["cell"]) for cell in row] for row in data]
    for cell in wrapped[0]:
        cell.style = _styles()["cell_head"]
    table = Table(wrapped, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEAD),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _styles():
    return {
        "title": ParagraphStyle("PolicyTitle", fontName="Times-Bold", fontSize=18, leading=22, textColor=INK, spaceAfter=4),
        "note": ParagraphStyle("PolicyNote", fontName="Times-Italic", fontSize=10, leading=13, textColor=MUTED),
        "section": ParagraphStyle("PolicySection", fontName="Times-Bold", fontSize=13, leading=16, textColor=INK, spaceBefore=2, spaceAfter=4),
        "subhead": ParagraphStyle("PolicySubhead", fontName="Times-Bold", fontSize=11, leading=14, textColor=INK, spaceBefore=2, spaceAfter=3),
        "body": ParagraphStyle("PolicyBody", fontName="Times-Roman", fontSize=11, leading=15, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=4),
        "clause": ParagraphStyle("PolicyClause", fontName="Times-Roman", fontSize=11, leading=15, textColor=INK, leftIndent=12, spaceAfter=3),
        "meta_label": ParagraphStyle("MetaLabel", fontName="Times-Bold", fontSize=10, leading=13, textColor=INK),
        "meta_value": ParagraphStyle("MetaValue", fontName="Times-Roman", fontSize=10, leading=13, textColor=INK),
        "cell": ParagraphStyle("Cell", fontName="Times-Roman", fontSize=9, leading=12, textColor=INK),
        "cell_head": ParagraphStyle("CellHead", fontName="Times-Bold", fontSize=9, leading=12, textColor=INK),
    }


def _chrome(canvas, doc, header: str) -> None:
    canvas.saveState()
    canvas.setFillColor(MUTED)
    canvas.setFont("Times-Roman", 9)
    canvas.drawString(18 * mm, A4[1] - 12 * mm, header[:90])
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, A4[1] - 14 * mm, A4[0] - 18 * mm, A4[1] - 14 * mm)
    canvas.restoreState()


def _numbered_canvas():
    from reportlab.pdfgen import canvas as pdfcanvas

    class NumberedCanvas(pdfcanvas.Canvas):
        def __init__(self, *args, **kwargs):
            pdfcanvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            page_count = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.setFillColor(MUTED)
                self.setFont("Times-Roman", 9)
                self.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {self._pageNumber} of {page_count}")
                pdfcanvas.Canvas.showPage(self)
            pdfcanvas.Canvas.save(self)

    return NumberedCanvas


def _xml(value) -> str:
    text = str(value or "")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
