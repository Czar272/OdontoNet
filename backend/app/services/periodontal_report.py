"""Reporte PDF de un periodontograma finalizado (ODON-198).

Se genera en el servidor con reportlab (BSD): hoja A4 horizontal con la
identificación clínica (clínica, paciente, fecha del examen, autor y quien lo
finalizó), el resumen descriptivo, y por arcada la grilla de valores y un
dibujo propio con la línea del margen gingival y la del fondo de la bolsa.
No incluye diagnósticos: lo dice el pie de cada página.

Texto: las fuentes estándar de PDF solo cubren WinAnsi (cp1252); cualquier otro
carácter se dibujaría como un cuadrado. Por eso todo texto libre pasa por
`_clean` (quita controles, separa acentos combinados y reemplaza lo que no
exista por «?») y se ajusta al ancho disponible: las celdas se recortan con «…»
y las notas se dividen en líneas, sin perder texto.
"""
import unicodedata
from datetime import datetime
from io import BytesIO
from typing import Optional
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.periodontal import FURCATION_ENTRANCES, LOWER_TEETH, UPPER_TEETH, PeriodontalExam
from app.services.periodontal_service import DEEP_SITE_MM, summarize

PAGE = landscape(A4)
MARGIN = 12 * mm
LABEL_W = 26 * mm
BOTTOM = 16 * mm  # por encima del pie
RED = colors.HexColor("#dc2626")
BLUE = colors.HexColor("#2563eb")
SKY = colors.HexColor("#0ea5e9")
YELLOW = colors.HexColor("#ca8a04")
TEAL = colors.HexColor("#0f766e")
GREY = colors.HexColor("#64748b")
LIGHT = colors.HexColor("#e2e8f0")

DISCLAIMER = (
    "Registro clínico manual. El resumen es estadística descriptiva y no constituye diagnóstico. "
    "Margen gingival respecto a la UAC (negativo = recesión); NIC = sondaje - margen."
)


def _clean(text: Optional[str]) -> str:
    """Texto dibujable con las fuentes estándar (WinAnsi), sin controles."""
    if not text:
        return ""
    text = "".join(" " if unicodedata.category(ch) in ("Cc", "Zl", "Zp") and ch != "\n" else ch for ch in text)
    out = []
    for ch in text:
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            # «ễ» → «e»; si no tiene base latina, «?».
            base = unicodedata.normalize("NFKD", ch).encode("cp1252", "ignore").decode("cp1252")
            out.append(base or "?")
    return "".join(out)


def _fit(text: str, font: str, size: float, width: float) -> str:
    """Una línea que cabe en `width`; si no cabe, se recorta con «…»."""
    text = _clean(text).replace("\n", " ")
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _num(value: Optional[float], unit: str) -> str:
    return "—" if value is None else f"{value:g} {unit}".replace(".", ",")


def display_sites(tooth: int, face: str) -> list[str]:
    """Igual que el editor: lo distal hacia afuera (cuadrantes 1 y 4 a la izquierda)."""
    mesial, center, distal = ("mb", "b", "db") if face == "buccal" else ("ml", "l", "dl")
    return [distal, center, mesial] if tooth // 10 in (1, 4) else [mesial, center, distal]


def display_entrances(tooth: int, face: str) -> list[str]:
    """Entradas de furcación de una cara en el mismo orden que los sitios."""
    entrances = [e for e in FURCATION_ENTRANCES.get(tooth, ()) if (e == "b") == (face == "buccal")]
    return list(reversed(entrances)) if tooth // 10 in (1, 4) else entrances


class _Report:
    def __init__(self, exam: PeriodontalExam, patient: Patient, clinic: Clinic):
        self.exam = exam
        self.patient = patient
        self.clinic = clinic
        self.zone = ZoneInfo(getattr(clinic, "timezone", None) or "UTC")
        self.buffer = BytesIO()
        self.pdf = canvas.Canvas(self.buffer, pagesize=PAGE)
        self.pdf.setTitle(f"Periodontograma {exam.exam_date.strftime('%d/%m/%Y')}")
        self.pdf.setAuthor("OdontoNet")
        self.page = 0
        self.teeth = {tooth.tooth: tooth for tooth in exam.teeth}
        self.sites = {(site.tooth, site.site): site for site in exam.sites}

    def _local(self, moment: Optional[datetime], with_time: bool = False) -> str:
        if not moment:
            return "—"
        local = moment.astimezone(self.zone)
        return local.strftime("%d/%m/%Y %H:%M" if with_time else "%d/%m/%Y")

    # --- Página -----------------------------------------------------------------

    def _footer(self) -> None:
        self.page += 1
        pdf = self.pdf
        pdf.setFont("Helvetica", 7)
        pdf.setFillColor(GREY)
        pdf.drawString(MARGIN, 7 * mm, DISCLAIMER)
        pdf.drawRightString(PAGE[0] - MARGIN, 7 * mm, f"Página {self.page}")
        pdf.setFillColor(colors.black)

    def _new_page(self) -> float:
        self._footer()
        self.pdf.showPage()
        return PAGE[1] - MARGIN - 4 * mm

    def _legend(self, y: float) -> float:
        """Leyenda en cada página: líneas y marcas se distinguen por forma, no solo por color."""
        pdf = self.pdf
        x = MARGIN
        pdf.setFont("Helvetica", 7)
        items = [
            ("line", RED, "Margen gingival"), ("line", BLUE, "Fondo de la bolsa"),
            ("dash", GREY, "UAC"), ("circle", RED, "S = sangrado"),
            ("triangle", YELLOW, "U = supuración"), ("square", SKY, "P = placa"),
        ]
        for kind, color, label in items:
            pdf.setStrokeColor(color)
            pdf.setFillColor(color)
            if kind == "line":
                pdf.setLineWidth(1.2)
                pdf.line(x, y + 1 * mm, x + 6 * mm, y + 1 * mm)
                x += 7 * mm
            elif kind == "dash":
                pdf.setDash(1, 1)
                pdf.line(x, y + 1 * mm, x + 6 * mm, y + 1 * mm)
                pdf.setDash()
                x += 7 * mm
            else:
                self._mark(kind, x + 1 * mm, y + 1 * mm)
                x += 3 * mm
            pdf.setFillColor(colors.black)
            pdf.drawString(x, y, label)
            x += stringWidth(label, "Helvetica", 7) + 6 * mm
        pdf.setLineWidth(1)
        pdf.setStrokeColor(colors.black)
        return y - 5 * mm

    def _mark(self, kind: str, x: float, y: float) -> None:
        pdf, r = self.pdf, 0.8 * mm
        if kind == "circle":
            pdf.circle(x, y, r, stroke=0, fill=1)
        elif kind == "square":
            pdf.rect(x - r, y - r, 2 * r, 2 * r, stroke=0, fill=1)
        else:
            path = pdf.beginPath()
            path.moveTo(x - r, y - r)
            path.lineTo(x + r, y - r)
            path.lineTo(x, y + r)
            path.close()
            pdf.drawPath(path, stroke=0, fill=1)

    def _header(self) -> float:
        pdf, exam, patient = self.pdf, self.exam, self.patient
        top = PAGE[1] - MARGIN
        pdf.setFont("Helvetica-Bold", 15)
        pdf.setFillColor(TEAL)
        pdf.drawString(MARGIN, top - 5 * mm, "Periodontograma")
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(PAGE[0] - MARGIN, top - 5 * mm, _fit(self.clinic.name, "Helvetica", 9, 120 * mm))

        visit = exam.clinical_visit
        rows = [
            ("Paciente", f"{patient.first_name} {patient.last_name}"),
            ("Fecha de nacimiento", patient.birth_date.strftime("%d/%m/%Y") if patient.birth_date else "—"),
            ("Fecha del examen", exam.exam_date.strftime("%d/%m/%Y")),
            ("Registró", exam.created_by.name),
            ("Finalizó", f"{exam.finalized_by.name} · {self._local(exam.finalized_at, with_time=True)}"),
            ("Consulta", f"{self._local(visit.visit_at)} · {visit.reason}" if visit else "—"),
        ]
        column = (PAGE[0] - 2 * MARGIN) / 3
        label_w = 30 * mm
        y = top - 12 * mm
        for index, (label, value) in enumerate(rows):
            x = MARGIN + (index % 3) * column
            if index and index % 3 == 0:
                y -= 5 * mm
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(x, y, f"{label}:")
            pdf.setFont("Helvetica", 8)
            pdf.drawString(x + label_w, y, _fit(value, "Helvetica", 8, column - label_w - 3 * mm))
        return y - 7 * mm

    def _paragraph(self, title: str, text: str, y: float) -> float:
        """Texto libre completo, en varias líneas y, si hace falta, en varias páginas."""
        pdf = self.pdf
        width = PAGE[0] - 2 * MARGIN
        lines = []
        for paragraph in _clean(text).split("\n"):
            lines += simpleSplit(paragraph, "Helvetica", 7.5, width - 4 * mm) or [""]
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(MARGIN, y, title)
        y -= 4 * mm
        for line in lines:
            if y < BOTTOM:
                y = self._new_page()
                y = self._legend(y)
                pdf.setFont("Helvetica-Bold", 8)
                pdf.drawString(MARGIN, y, f"{title} (continuación)")
                y -= 4 * mm
            pdf.setFont("Helvetica", 7.5)
            pdf.drawString(MARGIN + 2 * mm, y, line)
            y -= 3.6 * mm
        return y - 2 * mm

    def _summary(self, y: float) -> float:
        summary = summarize(self.exam)
        items = [
            ("Sondaje medio", _num(summary["mean_probing_depth"], "mm")),
            ("NIC medio", _num(summary["mean_attachment_level"], "mm")),
            ("Sangrado al sondaje", _num(summary["bleeding_pct"], "%")),
            ("Placa", _num(summary["plaque_pct"], "%")),
            (f"Sitios >= {DEEP_SITE_MM} mm", _num(summary["deep_sites_pct"], "%")),
            ("Sitios medidos", str(summary["measured_sites"])),
            ("Piezas presentes", str(summary["present_teeth"])),
        ]
        pdf = self.pdf
        pdf.setFillColor(colors.HexColor("#f0fdfa"))
        pdf.rect(MARGIN, y - 10 * mm, PAGE[0] - 2 * MARGIN, 11 * mm, stroke=0, fill=1)
        pdf.setFillColor(colors.black)
        width = (PAGE[0] - 2 * MARGIN) / len(items)
        for index, (label, value) in enumerate(items):
            x = MARGIN + 3 * mm + index * width
            pdf.setFont("Helvetica", 7)
            pdf.setFillColor(GREY)
            pdf.drawString(x, y - 3.5 * mm, label)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.setFillColor(colors.black)
            pdf.drawString(x, y - 8 * mm, value)
        return y - 14 * mm

    # --- Arcadas --------------------------------------------------------------

    def _grid(self, teeth: tuple[int, ...], face: str, y: float, tooth_rows: bool) -> float:
        """Grilla de una cara: una fila por parámetro y tres celdas por pieza."""
        pdf = self.pdf
        col = (PAGE[0] - 2 * MARGIN - LABEL_W) / len(teeth)
        row_h = 3.6 * mm
        rows: list[tuple[str, str]] = []
        if tooth_rows:
            rows += [("Pieza", "number"), ("Movilidad", "mobility"), ("Implante", "implant")]
        rows += [("Furcación", "furcation"), ("S / U / P", "marks"), ("Margen", "gingival_margin"),
                 ("Sondaje", "probing_depth"), ("NIC", "nic")]
        for label, key in rows:
            pdf.setFont("Helvetica", 6.5)
            pdf.setFillColor(GREY)
            pdf.drawString(MARGIN, y - row_h + 1 * mm, label)
            pdf.setFillColor(colors.black)
            for index, number in enumerate(teeth):
                tooth = self.teeth[number]
                x0 = MARGIN + LABEL_W + index * col
                cx = x0 + col / 2
                pdf.setStrokeColor(LIGHT)
                pdf.rect(x0, y - row_h, col, row_h, stroke=1, fill=0)
                if tooth.missing and key != "number":
                    continue
                if key == "number":
                    pdf.setFont("Helvetica-Bold", 7)
                    pdf.drawCentredString(cx, y - row_h + 1 * mm, f"{number}{' (aus.)' if tooth.missing else ''}")
                elif key == "mobility":
                    pdf.setFont("Helvetica", 7)
                    pdf.drawCentredString(cx, y - row_h + 1 * mm, "" if tooth.mobility is None else str(tooth.mobility))
                elif key == "implant":
                    pdf.setFont("Helvetica", 7)
                    pdf.drawCentredString(cx, y - row_h + 1 * mm, "Sí" if tooth.implant else "")
                elif key == "furcation":
                    grades = [getattr(tooth, f"furcation_{e}") for e in display_entrances(number, face)]
                    text = " ".join(["I", "II", "III"][g - 1] if g else "–" for g in grades)
                    pdf.setFont("Helvetica", 6.5)
                    pdf.drawCentredString(cx, y - row_h + 1 * mm, text)
                else:
                    for slot, code in enumerate(display_sites(number, face)):
                        site = self.sites[(number, code)]
                        sx = x0 + col * (slot + 0.5) / 3
                        if key == "marks":
                            # Letras además de formas y colores: legible en blanco y negro.
                            letters = "".join(
                                letter for letter, on in (("S", site.bleeding), ("U", site.suppuration), ("P", site.plaque)) if on
                            )
                            if letters:
                                pdf.setFont("Helvetica-Bold", 5.5)
                                pdf.setFillColor(RED if site.bleeding else (YELLOW if site.suppuration else SKY))
                                pdf.drawCentredString(sx, y - row_h + 1.1 * mm, letters)
                                pdf.setFillColor(colors.black)
                            continue
                        if key == "nic":
                            value = (
                                None if site.probing_depth is None or site.gingival_margin is None
                                else site.probing_depth - site.gingival_margin
                            )
                        else:
                            value = getattr(site, key)
                        if value is None:
                            continue
                        deep = key == "probing_depth" and value >= DEEP_SITE_MM
                        pdf.setFont("Helvetica-Bold" if deep else "Helvetica", 6.5)
                        pdf.setFillColor(BLUE if deep else colors.black)
                        pdf.drawCentredString(sx, y - row_h + 1 * mm, str(value))
                        pdf.setFillColor(colors.black)
            y -= row_h
        return y - 1 * mm

    def _drawing(self, teeth: tuple[int, ...], face: str, y: float, apical: int) -> float:
        """Dibujo propio: UAC punteada, margen (rojo) y fondo de bolsa (azul) por pieza."""
        pdf = self.pdf
        col = (PAGE[0] - 2 * MARGIN - LABEL_W) / len(teeth)
        height = 24 * mm
        scale = 0.8 * mm  # 1 mm clínico
        cej = y - height / 2
        # Raíz hacia arriba (apical = -1) o hacia abajo (+1); en PDF el eje y crece hacia arriba.
        direction = -apical
        low, high = y - height, y

        def clamp(value: float) -> float:
            # Sondajes extremos se recortan al área del dibujo (los valores exactos están en la grilla).
            return max(low + 0.5 * mm, min(high - 0.5 * mm, value))

        pdf.setFont("Helvetica", 6.5)
        pdf.setFillColor(GREY)
        pdf.drawString(MARGIN, cej - 1 * mm, "Vestibular" if face == "buccal" else (
            "Palatino" if teeth == UPPER_TEETH else "Lingual"))
        pdf.setFillColor(colors.black)
        for index, number in enumerate(teeth):
            tooth = self.teeth[number]
            x0 = MARGIN + LABEL_W + index * col
            # Silueta mínima: cuello, raíz y corona.
            pdf.setStrokeColor(LIGHT if tooth.missing else GREY)
            pdf.setLineWidth(0.5)
            root_tip = cej + direction * 9 * mm
            crown_tip = cej - direction * 7 * mm
            pdf.line(x0 + col * 0.25, cej, x0 + col * 0.4, root_tip)
            pdf.line(x0 + col * 0.75, cej, x0 + col * 0.6, root_tip)
            pdf.line(x0 + col * 0.25, cej, x0 + col * 0.3, crown_tip)
            pdf.line(x0 + col * 0.75, cej, x0 + col * 0.7, crown_tip)
            pdf.line(x0 + col * 0.3, crown_tip, x0 + col * 0.7, crown_tip)
            if tooth.missing:
                pdf.line(x0 + 2, cej - 6 * mm, x0 + col - 2, cej + 6 * mm)
                continue
            pdf.setDash(1, 1)
            pdf.setStrokeColor(LIGHT)
            pdf.line(x0, cej, x0 + col, cej)
            pdf.setDash()
            margin_pts, pocket_pts = [], []
            for slot, code in enumerate(display_sites(number, face)):
                site = self.sites[(number, code)]
                if site.probing_depth is None and site.gingival_margin is None:
                    continue
                sx = x0 + col * (slot + 0.5) / 3
                gm = site.gingival_margin or 0
                pd = site.probing_depth or 0
                my = cej - direction * gm * scale
                margin_pts.append((sx, clamp(my)))
                pocket_pts.append((sx, clamp(my + direction * pd * scale)))
            pdf.setLineWidth(1)
            for points, color in ((margin_pts, RED), (pocket_pts, BLUE)):
                pdf.setStrokeColor(color)
                for (x1, y1), (x2, y2) in zip(points, points[1:]):
                    pdf.line(x1, y1, x2, y2)
                if len(points) == 1:
                    pdf.circle(points[0][0], points[0][1], 0.5 * mm, stroke=1, fill=0)
        pdf.setLineWidth(1)
        pdf.setStrokeColor(colors.black)
        return y - height - 1 * mm

    def _arch(self, title: str, teeth: tuple[int, ...], faces: tuple[str, str], y: float) -> float:
        pdf = self.pdf
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(MARGIN, y, title)
        y -= 2 * mm
        top_face, bottom_face = faces
        # Como en el editor: coronas enfrentadas (la cara de arriba con la raíz hacia arriba).
        y = self._grid(teeth, top_face, y, tooth_rows=top_face == "buccal")
        y = self._drawing(teeth, top_face, y, apical=-1)
        y = self._drawing(teeth, bottom_face, y, apical=1)
        y = self._grid(teeth, bottom_face, y, tooth_rows=bottom_face == "buccal")
        return y - 3 * mm

    def build(self) -> bytes:
        y = self._header()
        y = self._summary(y)
        y = self._legend(y)
        self._arch("Arcada superior", UPPER_TEETH, ("buccal", "lingual"), y)
        y = self._new_page()
        y = self._legend(y)
        y = self._arch("Arcada inferior", LOWER_TEETH, ("lingual", "buccal"), y)
        if self.exam.notes:
            y = self._paragraph("Notas generales", self.exam.notes, y)
        tooth_notes = [f"{t.tooth}: {t.note}" for t in sorted(self.exam.teeth, key=lambda t: t.tooth) if t.note]
        if tooth_notes:
            y = self._paragraph("Notas por pieza", "\n".join(tooth_notes), y)
        self._footer()
        self.pdf.showPage()
        self.pdf.save()
        return self.buffer.getvalue()


def build_report(exam: PeriodontalExam, patient: Patient, clinic: Clinic) -> bytes:
    return _Report(exam, patient, clinic).build()
