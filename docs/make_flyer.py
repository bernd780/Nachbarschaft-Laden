import io, qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from PIL import Image as PILImage

W, H = A4   # 595.27 x 841.89 pt

GREEN1  = HexColor('#2d6a4f')
GREEN2  = HexColor('#40916c')
GREEN3  = HexColor('#74c69d')
GREEN4  = HexColor('#d8f3dc')
AMBER   = HexColor('#e07b00')
INK     = HexColor('#1a1a1a')
MUTED   = HexColor('#5a6a5e')
BG      = HexColor('#f4f7f5')

URL = 'https://nachbarschaft-laden.de/local/nachbarschaft-laden/index.html'
OUT = r'C:\Users\bernd\Documents\Nachbarschaft-Laden\docs\flyer.pdf'

QR_TMP = r'C:\Users\bernd\Documents\Nachbarschaft-Laden\docs\_qr_tmp.png'

def qr_image_buf(url):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color='#1a1a1a', back_color='white')
    img.save(QR_TMP)
    return QR_TMP

def draw_rounded_rect(c, x, y, w, h, r, fill_color=None, stroke_color=None, stroke_width=0):
    c.saveState()
    if fill_color:   c.setFillColor(fill_color)
    if stroke_color: c.setStrokeColor(stroke_color); c.setLineWidth(stroke_width)
    else:            c.setLineWidth(0)
    p = c.beginPath()
    p.moveTo(x + r, y)
    p.lineTo(x + w - r, y)
    p.arcTo(x + w - 2*r, y, x + w, y + 2*r, -90, 90)
    p.lineTo(x + w, y + h - r)
    p.arcTo(x + w - 2*r, y + h - 2*r, x + w, y + h, 0, 90)
    p.lineTo(x + r, y + h)
    p.arcTo(x, y + h - 2*r, x + 2*r, y + h, 90, 90)
    p.lineTo(x, y + r)
    p.arcTo(x, y, x + 2*r, y + 2*r, 180, 90)
    p.close()
    c.drawPath(p, fill=1 if fill_color else 0, stroke=1 if stroke_color else 0)
    c.restoreState()

def draw_lightning(c, cx, cy, size, color):
    c.saveState(); c.setFillColor(color)
    s = size
    pts = [(cx, cy+s), (cx-s*.35, cy+s*.1), (cx-s*.05, cy+s*.1),
           (cx-s*.35, cy-s), (cx+s*.35, cy-s*.1), (cx+s*.05, cy-s*.1)]
    p = c.beginPath(); p.moveTo(*pts[0])
    for pt in pts[1:]: p.lineTo(*pt)
    p.close(); c.drawPath(p, fill=1, stroke=0); c.restoreState()

def draw_sun(c, cx, cy, r, color):
    import math
    c.saveState(); c.setFillColor(color)
    c.circle(cx, cy, r, fill=1, stroke=0)
    c.setStrokeColor(color); c.setLineWidth(1.5)
    for i in range(8):
        a = math.radians(i * 45)
        x1, y1 = cx + math.cos(a)*(r+2), cy + math.sin(a)*(r+2)
        x2, y2 = cx + math.cos(a)*(r+5), cy + math.sin(a)*(r+5)
        c.line(x1, y1, x2, y2)
    c.restoreState()

def draw_leaf(c, cx, cy, size, color):
    c.saveState(); c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(cx, cy+size)
    p.curveTo(cx+size*.8, cy+size*.5, cx+size*.8, cy-size*.2, cx, cy-size*.5)
    p.curveTo(cx-size*.8, cy-size*.2, cx-size*.8, cy+size*.5, cx, cy+size)
    p.close(); c.drawPath(p, fill=1, stroke=0)
    c.setStrokeColor(white); c.setLineWidth(0.8)
    c.line(cx, cy-size*.4, cx, cy+size*.8)
    c.restoreState()

def draw_location(c, cx, cy, size, color):
    c.saveState(); c.setFillColor(color)
    # pin: circle on top + teardrop
    r = size * .38
    c.circle(cx, cy+size*.22, r, fill=1, stroke=0)
    p = c.beginPath()
    p.moveTo(cx - r*.85, cy+size*.22)
    p.curveTo(cx - r*.85, cy - size*.5, cx, cy - size*.65, cx, cy - size*.65)
    p.curveTo(cx, cy - size*.65, cx + r*.85, cy - size*.5, cx + r*.85, cy+size*.22)
    p.close(); c.drawPath(p, fill=1, stroke=0)
    c.setFillColor(white); c.circle(cx, cy+size*.22, r*.42, fill=1, stroke=0)
    c.restoreState()

def make_flyer():
    c = canvas.Canvas(OUT, pagesize=A4)

    # ── Background ────────────────────────────────────────────────
    c.setFillColor(white); c.rect(0, 0, W, H, fill=1, stroke=0)

    # ── Header block ──────────────────────────────────────────────
    header_h = 210
    draw_rounded_rect(c, 0, H - header_h, W, header_h, 0, fill_color=GREEN1)
    # subtle gradient effect – lighter strip at top
    c.saveState(); c.setFillColor(HexColor('#3a7a5f')); c.setFillAlpha(0.4)
    c.rect(0, H - 60, W, 60, fill=1, stroke=0); c.restoreState()

    # decorative circle
    c.saveState(); c.setFillColor(HexColor('#40916c')); c.setFillAlpha(0.35)
    c.circle(W - 60, H - 50, 130, fill=1, stroke=0); c.restoreState()
    c.saveState(); c.setFillColor(HexColor('#74c69d')); c.setFillAlpha(0.15)
    c.circle(W - 40, H - 30, 80, fill=1, stroke=0); c.restoreState()

    # Lightning icon in header
    draw_lightning(c, 52*mm, H - 55, 14, HexColor('#ffd166'))

    # Title
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 36)
    c.drawString(22*mm, H - 72, 'Nachbarschaft-Laden')
    c.setFont('Helvetica', 14)
    c.setFillColor(GREEN3)
    c.drawString(22*mm, H - 90, 'Solarstrom vom Nachbardach – direkt ins Auto')

    # Tagline box
    draw_rounded_rect(c, 18*mm, H - 155, W - 36*mm, 52, 8,
                      fill_color=HexColor('#1b4332'))
    c.setFont('Helvetica', 11)
    c.setFillColor(GREEN3)
    tagline = ('Wenn die Sonne scheint, sinkt der Preis – lade günstig mit '
               'überschüssigem Solarstrom aus der Nachbarschaft.')
    # word-wrap manually
    words = tagline.split()
    line, lines = '', []
    for w in words:
        test = (line + ' ' + w).strip()
        c.setFont('Helvetica', 11)
        if c.stringWidth(test, 'Helvetica', 11) < (W - 52*mm):
            line = test
        else:
            lines.append(line); line = w
    lines.append(line)
    ty = H - 122
    for ln in lines:
        c.drawString(26*mm, ty, ln); ty -= 16

    # ── Feature cards (3 columns) ─────────────────────────────────
    card_y = H - 310
    card_h = 88
    card_w = (W - 40*mm) / 3 - 4*mm
    cards = [
        (GREEN3,  '☀',  'Dynamischer Preis',
         'Je mehr Solarüberschuss, desto günstiger – automatisch und transparent.'),
        (AMBER,   '⚡', 'Einfach laden',
         'RFID-Karte an die Wallbox – Ladevorgang startet, Session wird zugeordnet.'),
        (GREEN2,  '📍', 'Lokal & fair',
         'Strom vom Dach nebenan. Kurze Wege, keine Aufschläge, echte Nachbarschaft.'),
    ]
    for i, (color, icon, title, desc) in enumerate(cards):
        cx = 20*mm + i * (card_w + 4*mm)
        draw_rounded_rect(c, cx, card_y, card_w, card_h, 10, fill_color=GREEN4)
        c.setFillColor(color); c.setFont('Helvetica-Bold', 18)
        c.drawString(cx + 8, card_y + card_h - 24, icon)
        c.setFillColor(GREEN1); c.setFont('Helvetica-Bold', 9.5)
        c.drawString(cx + 8, card_y + card_h - 40, title)
        # wrap desc
        c.setFont('Helvetica', 8.5); c.setFillColor(MUTED)
        dwords = desc.split(); dline, dlines = '', []
        for dw in dwords:
            dt = (dline + ' ' + dw).strip()
            if c.stringWidth(dt, 'Helvetica', 8.5) < card_w - 16:
                dline = dt
            else:
                dlines.append(dline); dline = dw
        dlines.append(dline)
        dy = card_y + card_h - 58
        for dl in dlines:
            c.drawString(cx + 8, dy, dl); dy -= 12

    # ── How it works ──────────────────────────────────────────────
    section_y = card_y - 30
    c.setFillColor(GREEN1); c.setFont('Helvetica-Bold', 14)
    c.drawString(20*mm, section_y, 'So funktioniert\'s')
    c.setStrokeColor(GREEN3); c.setLineWidth(1.5)
    c.line(20*mm, section_y - 5, W - 20*mm, section_y - 5)

    steps = [
        ('1', 'Nachbar-Karte besorgen',  'Einfach melden – wir geben dir eine Karte, die die Wallbox freischaltet.'),
        ('2', 'Preis checken',           'Das Web-Dashboard zeigt den aktuellen Preis und die PV-Prognose für morgen.'),
        ('3', 'Karte an die Wallbox',    'Karte scannen – Ladevorgang startet automatisch und wird dir zugeordnet.'),
        ('4', 'Laden – fertig',          'Abrechnung nach tatsächlichem Verbrauch. Transparent, fair, günstig.'),
    ]
    sy = section_y - 22
    for num, title, desc in steps:
        # number circle
        c.setFillColor(GREEN1); c.circle(27*mm, sy + 4, 8, fill=1, stroke=0)
        c.setFillColor(white); c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(27*mm, sy + 1.5, num)
        c.setFillColor(INK); c.setFont('Helvetica-Bold', 10)
        c.drawString(38*mm, sy + 4, title)
        c.setFillColor(MUTED); c.setFont('Helvetica', 9)
        c.drawString(38*mm, sy - 8, desc)
        sy -= 30

    # ── Benefits strip ────────────────────────────────────────────
    strip_y = sy - 10
    draw_rounded_rect(c, 18*mm, strip_y - 28, W - 36*mm, 44, 10, fill_color=GREEN4)
    benefits = ['Günstiger als Festtarif', 'Keine Grundgebühr', 'Transparent & fair', 'Solarstrom sinnvoll nutzen']
    bx = 26*mm
    for b in benefits:
        c.setFillColor(GREEN2); c.setFont('Helvetica-Bold', 8)
        c.drawString(bx, strip_y - 10, '✓')
        c.setFillColor(GREEN1); c.setFont('Helvetica', 8.5)
        c.drawString(bx + 9, strip_y - 10, b)
        bx += (W - 52*mm) / len(benefits)

    # ── CTA + QR ──────────────────────────────────────────────────
    cta_y = strip_y - 55

    # CTA box left
    cta_w = 95*mm
    draw_rounded_rect(c, 20*mm, cta_y - 80, cta_w, 90, 12, fill_color=GREEN1)
    c.setFillColor(white); c.setFont('Helvetica-Bold', 14)
    c.drawString(28*mm, cta_y - 18, 'Mitmachen?')
    c.setFont('Helvetica', 9.5)
    c.setFillColor(GREEN3)
    cta_lines = [
        'Du brauchst nur eine Nachbar-Karte.',
        'Sprich uns einfach an – wir freuen',
        'uns über jeden neuen Mitmacher!',
        '',
        'Alle Infos & aktueller Preis:',
    ]
    cy2 = cta_y - 36
    for ln in cta_lines:
        c.drawString(28*mm, cy2, ln); cy2 -= 14
    c.setFillColor(HexColor('#ffd166')); c.setFont('Helvetica-Bold', 8.5)
    short_url = 'nachbarschaft-laden.de'
    c.drawString(28*mm, cy2, short_url)

    # QR code right
    qr_buf = qr_image_buf(URL)
    qr_size = 72*mm
    qr_x = W - 20*mm - qr_size
    qr_box_pad = 5*mm
    draw_rounded_rect(c, qr_x - qr_box_pad, cta_y - 80 - qr_box_pad,
                      qr_size + 2*qr_box_pad, qr_size + 2*qr_box_pad + 14,
                      10, fill_color=white,
                      stroke_color=GREEN3, stroke_width=1.5)
    c.drawImage(qr_buf, qr_x, cta_y - 80 + 8, qr_size, qr_size)
    c.setFillColor(MUTED); c.setFont('Helvetica', 7.5)
    c.drawCentredString(qr_x + qr_size/2, cta_y - 80 - 2, 'Jetzt scannen & Preis checken')

    # ── Footer ────────────────────────────────────────────────────
    footer_h = 22
    c.setFillColor(GREEN1)
    c.rect(0, 0, W, footer_h, fill=1, stroke=0)
    c.setFillColor(GREEN3); c.setFont('Helvetica', 8)
    c.drawCentredString(W/2, 8, 'Nachbarschaft-Laden · Solarstrom lokal nutzen · ' + short_url)

    c.save()
    print('Flyer gespeichert:', OUT)

make_flyer()
