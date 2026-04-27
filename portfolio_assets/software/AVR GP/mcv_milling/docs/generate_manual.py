"""
MCV Milling Vision - GUI User Manual PDF Generator
Generates a comprehensive user manual for the MCV Vision web interface.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import (
    HexColor, white, black, Color
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable, ListFlowable, ListItem,
    Frame, PageTemplate, BaseDocTemplate
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import os
import datetime

# ── Color Palette (matching dark theme) ──────────────────────────────────────
DARK_BG = HexColor("#0d1117")
DARK_CARD = HexColor("#161b22")
DARK_BORDER = HexColor("#30363d")
ACCENT_ORANGE = HexColor("#f0883e")
ACCENT_GREEN = HexColor("#3fb950")
ACCENT_BLUE = HexColor("#58a6ff")
ACCENT_RED = HexColor("#f85149")
ACCENT_CYAN = HexColor("#39d2c0")
ACCENT_YELLOW = HexColor("#d29922")
TEXT_WHITE = HexColor("#e6edf3")
TEXT_MUTED = HexColor("#8b949e")
KUKA_ORANGE = HexColor("#FF6600")
HEADER_BG = HexColor("#1a1f2e")
SECTION_BG = HexColor("#0d1117")
TABLE_HEADER_BG = HexColor("#21262d")
TABLE_ROW_ALT = HexColor("#f6f8fa")
LIGHT_GRAY = HexColor("#f0f0f0")
MID_GRAY = HexColor("#666666")
DARK_GRAY = HexColor("#333333")

# ── Page dimensions ──────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


def build_styles():
    """Create all paragraph styles for the manual."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'ManualTitle',
        parent=styles['Title'],
        fontSize=28,
        leading=34,
        textColor=DARK_GRAY,
        spaceAfter=6,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        'ManualSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        leading=18,
        textColor=MID_GRAY,
        spaceAfter=4,
        fontName='Helvetica',
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        'CoverInfo',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=MID_GRAY,
        fontName='Helvetica',
        alignment=TA_CENTER,
        spaceBefore=2,
    ))

    styles.add(ParagraphStyle(
        'ChapterTitle',
        parent=styles['Heading1'],
        fontSize=22,
        leading=28,
        textColor=DARK_GRAY,
        spaceBefore=12,
        spaceAfter=10,
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderColor=ACCENT_ORANGE,
        borderPadding=0,
    ))

    styles.add(ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=16,
        leading=20,
        textColor=HexColor("#1a1a2e"),
        spaceBefore=14,
        spaceAfter=6,
        fontName='Helvetica-Bold',
    ))

    styles.add(ParagraphStyle(
        'SubSection',
        parent=styles['Heading3'],
        fontSize=13,
        leading=16,
        textColor=HexColor("#2d2d44"),
        spaceBefore=10,
        spaceAfter=4,
        fontName='Helvetica-Bold',
    ))

    # Override built-in BodyText style
    styles['BodyText'].fontSize = 10
    styles['BodyText'].leading = 14
    styles['BodyText'].textColor = DARK_GRAY
    styles['BodyText'].spaceAfter = 6
    styles['BodyText'].fontName = 'Helvetica'
    styles['BodyText'].alignment = TA_JUSTIFY

    styles.add(ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=DARK_GRAY,
        leftIndent=20,
        spaceAfter=3,
        fontName='Helvetica',
        bulletIndent=8,
        bulletFontSize=10,
    ))

    styles.add(ParagraphStyle(
        'SubBullet',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=MID_GRAY,
        leftIndent=36,
        spaceAfter=2,
        fontName='Helvetica',
        bulletIndent=24,
    ))

    styles.add(ParagraphStyle(
        'NoteText',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=HexColor("#555555"),
        spaceAfter=6,
        fontName='Helvetica-Oblique',
        leftIndent=12,
        borderWidth=0,
    ))

    styles.add(ParagraphStyle(
        'TipText',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=HexColor("#1a6b37"),
        spaceAfter=6,
        fontName='Helvetica',
        leftIndent=12,
    ))

    styles.add(ParagraphStyle(
        'WarningText',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=HexColor("#9a6700"),
        spaceAfter=6,
        fontName='Helvetica-Bold',
        leftIndent=12,
    ))

    styles.add(ParagraphStyle(
        'CautionText',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=ACCENT_RED,
        spaceAfter=6,
        fontName='Helvetica-Bold',
        leftIndent=12,
    ))

    styles.add(ParagraphStyle(
        'CodeText',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=DARK_GRAY,
        fontName='Courier',
        leftIndent=12,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=white,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=DARK_GRAY,
        fontName='Helvetica',
    ))

    styles.add(ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=TEXT_MUTED,
        fontName='Helvetica',
    ))

    styles.add(ParagraphStyle(
        'TOCEntry',
        parent=styles['Normal'],
        fontSize=12,
        leading=22,
        textColor=DARK_GRAY,
        fontName='Helvetica',
        leftIndent=0,
    ))

    styles.add(ParagraphStyle(
        'TOCEntryL2',
        parent=styles['Normal'],
        fontSize=10,
        leading=18,
        textColor=MID_GRAY,
        fontName='Helvetica',
        leftIndent=20,
    ))

    return styles


# ── Helper functions ─────────────────────────────────────────────────────────

def make_tip(text, styles):
    return Paragraph(f'<b>TIP:</b> {text}', styles['TipText'])

def make_note(text, styles):
    return Paragraph(f'<i>Note: {text}</i>', styles['NoteText'])

def make_warning(text, styles):
    return Paragraph(f'WARNING: {text}', styles['WarningText'])

def make_caution(text, styles):
    return Paragraph(f'CAUTION: {text}', styles['CautionText'])

def orange_hr():
    return HRFlowable(
        width="100%", thickness=2, color=ACCENT_ORANGE,
        spaceBefore=4, spaceAfter=8
    )

def gray_hr():
    return HRFlowable(
        width="100%", thickness=0.5, color=HexColor("#cccccc"),
        spaceBefore=4, spaceAfter=6
    )

def section_table(data, col_widths=None):
    """Create a styled info table."""
    if col_widths is None:
        col_widths = [120, 390]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEADING', (0, 0), (-1, -1), 13),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return t

def bullet(text, styles, bold_prefix=None):
    if bold_prefix:
        return Paragraph(f'<bullet>&bull;</bullet> <b>{bold_prefix}:</b> {text}', styles['BulletText'])
    return Paragraph(f'<bullet>&bull;</bullet> {text}', styles['BulletText'])

def sub_bullet(text, styles):
    return Paragraph(f'<bullet>-</bullet> {text}', styles['SubBullet'])

def numbered_step(num, text, styles):
    return Paragraph(f'<b>Step {num}:</b> {text}', styles['BodyText'])


# ── Page header/footer ───────────────────────────────────────────────────────

def header_footer(canvas_obj, doc):
    """Draw page header and footer."""
    canvas_obj.saveState()

    # Header line
    canvas_obj.setStrokeColor(ACCENT_ORANGE)
    canvas_obj.setLineWidth(1.5)
    canvas_obj.line(MARGIN, PAGE_H - MARGIN + 5, PAGE_W - MARGIN, PAGE_H - MARGIN + 5)

    # Header text
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(TEXT_MUTED)
    canvas_obj.drawString(MARGIN, PAGE_H - MARGIN + 10, "MCV Milling Vision - User Manual")
    canvas_obj.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 10, "KUKA KR120 R2100 Calibration System")

    # Footer line
    canvas_obj.setStrokeColor(HexColor("#cccccc"))
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(MARGIN, MARGIN - 10, PAGE_W - MARGIN, MARGIN - 10)

    # Footer text
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(TEXT_MUTED)
    canvas_obj.drawString(MARGIN, MARGIN - 22, "Confidential - MCV Fiber Milling Vision System")
    canvas_obj.drawRightString(PAGE_W - MARGIN, MARGIN - 22, f"Page {doc.page}")

    canvas_obj.restoreState()


def cover_page(canvas_obj, doc):
    """Draw the cover page."""
    canvas_obj.saveState()

    # Top accent bar
    canvas_obj.setFillColor(ACCENT_ORANGE)
    canvas_obj.rect(0, PAGE_H - 8, PAGE_W, 8, fill=True, stroke=False)

    # Bottom accent bar
    canvas_obj.setFillColor(ACCENT_ORANGE)
    canvas_obj.rect(0, 0, PAGE_W, 8, fill=True, stroke=False)

    # Large gear icon placeholder (decorative box)
    canvas_obj.setFillColor(HexColor("#f5f5f5"))
    canvas_obj.roundRect(PAGE_W/2 - 60, PAGE_H - 260, 120, 120, 15, fill=True, stroke=False)
    canvas_obj.setFillColor(ACCENT_ORANGE)
    canvas_obj.setFont('Helvetica-Bold', 60)
    canvas_obj.drawCentredString(PAGE_W/2, PAGE_H - 220, "MCV")

    canvas_obj.restoreState()


# ── Content builders ─────────────────────────────────────────────────────────

def build_cover(styles):
    """Build cover page content."""
    story = []
    story.append(Spacer(1, 100))
    story.append(Paragraph("MCV Milling Vision", styles['ManualTitle']))
    story.append(Spacer(1, 4))
    story.append(Paragraph("GUI User Manual", styles['ManualTitle']))
    story.append(Spacer(1, 12))
    story.append(orange_hr())
    story.append(Spacer(1, 8))
    story.append(Paragraph("KUKA KR120 R2100 Fiber Milling Calibration System", styles['ManualSubtitle']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Automated Vision-Based Robot Calibration", styles['ManualSubtitle']))
    story.append(Spacer(1, 40))
    story.append(Paragraph(f"Version 1.0", styles['CoverInfo']))
    story.append(Paragraph(f"Date: {datetime.date.today().strftime('%B %d, %Y')}", styles['CoverInfo']))
    story.append(Spacer(1, 20))
    story.append(Paragraph("Django Web Application with Bootstrap 5 Dark Theme", styles['CoverInfo']))
    story.append(Paragraph("ArUco Tag Detection | Hand-Eye Calibration | KRL Program Management", styles['CoverInfo']))
    story.append(PageBreak())
    return story


def build_toc(styles):
    """Build table of contents."""
    story = []
    story.append(Paragraph("Table of Contents", styles['ChapterTitle']))
    story.append(orange_hr())
    story.append(Spacer(1, 10))

    toc_entries = [
        ("1", "Introduction", [
            "1.1 System Overview",
            "1.2 System Requirements",
            "1.3 Starting the Application",
        ]),
        ("2", "Navigation & Layout", [
            "2.1 Sidebar Navigation",
            "2.2 Top Bar",
            "2.3 Theme Toggle",
            "2.4 Toast Notifications",
        ]),
        ("3", "Getting Started Wizard", [
            "3.1 Step 1: Configure Settings",
            "3.2 Step 2: Connect Robot",
            "3.3 Step 3: Open Camera",
            "3.4 Step 4: Teach Nominal",
            "3.5 Step 5: Calibrate",
        ]),
        ("4", "Dashboard", [
            "4.1 Robot Connection",
            "4.2 Live Camera Feed",
            "4.3 Statistics",
            "4.4 Calibration History Chart",
            "4.5 Event Log",
            "4.6 Recent Calibrations Table",
        ]),
        ("5", "Calibration Page", [
            "5.1 Setup Tab",
            "5.2 Control Tab",
            "5.3 Calibrate Tab",
            "5.4 Vision Tab",
            "5.5 Advanced Tab",
        ]),
        ("6", "KRL Programs (Jobs)", [
            "6.1 Uploading Programs",
            "6.2 Managing Programs",
            "6.3 Executing Cycles",
        ]),
        ("7", "Camera Calibration", [
            "7.1 Chessboard Settings",
            "7.2 Capturing Frames",
            "7.3 Computing Calibration",
            "7.4 Calibration History",
        ]),
        ("8", "Settings", [
            "8.1 Robot Configuration",
            "8.2 Camera Configuration",
            "8.3 ArUco Tag Configuration",
            "8.4 Nominal Base Frame",
            "8.5 Hand-Eye Matrix",
            "8.6 Base Frame Management",
            "8.7 Backup & Restore",
        ]),
        ("9", "Troubleshooting", []),
        ("10", "Quick Reference", []),
    ]

    for num, title, subsections in toc_entries:
        story.append(Paragraph(f"<b>{num}.</b>  {title}", styles['TOCEntry']))
        for sub in subsections:
            story.append(Paragraph(sub, styles['TOCEntryL2']))

    story.append(PageBreak())
    return story


def build_chapter1(styles):
    """Chapter 1: Introduction"""
    story = []
    story.append(Paragraph("1. Introduction", styles['ChapterTitle']))
    story.append(orange_hr())

    # 1.1
    story.append(Paragraph("1.1 System Overview", styles['SectionTitle']))
    story.append(Paragraph(
        "MCV Milling Vision is a web-based application for automated vision-based calibration of the "
        "KUKA KR120 R2100 industrial robot used in fiber milling operations. The system uses ArUco "
        "marker detection to compute real-time corrections to the robot's base frame, ensuring "
        "precise part positioning throughout production cycles.",
        styles['BodyText']
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph("The application provides:", styles['BodyText']))
    story.append(bullet("Real-time robot position monitoring and jog control", styles))
    story.append(bullet("ArUco tag-based part and table detection", styles))
    story.append(bullet("Automated calibration cycle with correction computation", styles))
    story.append(bullet("Hand-eye calibration for camera-to-robot transformation", styles))
    story.append(bullet("Live camera feed via WebSocket streaming", styles))
    story.append(bullet("KRL program upload, management, and execution", styles))
    story.append(bullet("Intrinsic camera calibration via chessboard pattern", styles))
    story.append(bullet("2D/3D workspace visualization", styles))
    story.append(bullet("Event logging and calibration history export (CSV/Excel)", styles))
    story.append(bullet("Full settings backup and restore", styles))

    # 1.2
    story.append(Paragraph("1.2 System Requirements", styles['SectionTitle']))

    req_data = [
        ['Component', 'Requirement'],
        ['Robot', 'KUKA KR120 R2100 with EKI interface'],
        ['Camera', 'USB camera (recommended: industrial grade)'],
        ['Network', 'TCP/IP connection to robot controller'],
        ['Browser', 'Chrome, Firefox, or Edge (modern version)'],
        ['Server', 'Python 3.10+, Django 5.x'],
        ['Ports', '8000 (HTTP), 8001 (WebSocket/Daphne)'],
    ]
    story.append(section_table(req_data))
    story.append(Spacer(1, 6))

    # 1.3
    story.append(Paragraph("1.3 Starting the Application", styles['SectionTitle']))
    story.append(Paragraph("To start the MCV Vision system, two servers must be launched:", styles['BodyText']))
    story.append(Spacer(1, 4))

    story.append(numbered_step(1, "Open a terminal and navigate to the project directory.", styles))
    story.append(Paragraph("<font face='Courier' size='9'>cd mcv_milling</font>", styles['BodyText']))
    story.append(Spacer(1, 4))

    story.append(numbered_step(2, "Start the Django development server (HTTP on port 8000):", styles))
    story.append(Paragraph("<font face='Courier' size='9'>python manage.py runserver 0.0.0.0:8000</font>", styles['BodyText']))
    story.append(Spacer(1, 4))

    story.append(numbered_step(3, "In a second terminal, start Daphne for WebSocket support (port 8001):", styles))
    story.append(Paragraph("<font face='Courier' size='9'>daphne -b 0.0.0.0 -p 8001 mcv_milling.asgi:application</font>", styles['BodyText']))
    story.append(Spacer(1, 4))

    story.append(numbered_step(4, "Open your browser and navigate to:", styles))
    story.append(Paragraph("<font face='Courier' size='9'>http://localhost:8000</font>", styles['BodyText']))
    story.append(Spacer(1, 6))

    server_data = [
        ['Server', 'Port', 'Purpose'],
        ['Django (runserver)', '8000', 'HTTP pages, REST API, static files'],
        ['Daphne (ASGI)', '8001', 'WebSocket for live camera streaming'],
    ]
    t = Table(server_data, colWidths=[140, 60, 310])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEADING', (0, 0), (-1, -1), 13),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 4))
    story.append(make_note(
        "The Daphne server is only required for the live camera feed. All other features work with just the Django server.",
        styles
    ))

    story.append(PageBreak())
    return story


def build_chapter2(styles):
    """Chapter 2: Navigation & Layout"""
    story = []
    story.append(Paragraph("2. Navigation & Layout", styles['ChapterTitle']))
    story.append(orange_hr())

    story.append(Paragraph(
        "The application uses a fixed sidebar layout with a top bar. All pages share the same "
        "navigation structure for consistent user experience.",
        styles['BodyText']
    ))

    # 2.1
    story.append(Paragraph("2.1 Sidebar Navigation", styles['SectionTitle']))
    story.append(Paragraph(
        "The left sidebar is always visible and organizes navigation into four logical sections:",
        styles['BodyText']
    ))

    nav_data = [
        ['Section', 'Page', 'Description'],
        ['OVERVIEW', 'Dashboard', 'System status, camera feed, event log'],
        ['OPERATIONS', 'Calibration', 'Setup, control, run calibration cycles'],
        ['OPERATIONS', 'Jobs', 'Upload and execute KRL programs'],
        ['VISION', 'Camera Cal', 'Intrinsic camera calibration'],
        ['SYSTEM', 'Settings', 'All system configuration parameters'],
    ]
    t = Table(nav_data, colWidths=[80, 80, 350])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEADING', (0, 0), (-1, -1), 13),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "The sidebar footer displays the real-time robot connection status with a colored indicator "
        "(green = connected, red = disconnected). The active page is highlighted in the sidebar.",
        styles['BodyText']
    ))

    # 2.2
    story.append(Paragraph("2.2 Top Bar", styles['SectionTitle']))
    story.append(Paragraph("The top bar spans across the main content area and displays:", styles['BodyText']))
    story.append(bullet("Page title (left side)", styles))
    story.append(bullet("Theme toggle button (sun/moon icon)", styles))
    story.append(bullet("Robot name badge (shows configured robot name or '--')", styles))
    story.append(bullet("Connection status badge ('Connected' in green or 'Disconnected' in red)", styles))
    story.append(bullet("User info and logout button (when authenticated)", styles))

    # 2.3
    story.append(Paragraph("2.3 Theme Toggle", styles['SectionTitle']))
    story.append(Paragraph(
        "Click the sun/moon icon in the top bar to switch between dark and light themes. "
        "Your preference is saved automatically and persists across browser sessions.",
        styles['BodyText']
    ))

    # 2.4
    story.append(Paragraph("2.4 Toast Notifications", styles['SectionTitle']))
    story.append(Paragraph(
        "The system displays brief notification messages (toasts) in the bottom-right corner of the screen "
        "whenever an action is performed. Toasts are color-coded by severity:",
        styles['BodyText']
    ))
    story.append(bullet("Blue - Information messages", styles, "Info"))
    story.append(bullet("Green - Successful operations", styles, "Success"))
    story.append(bullet("Yellow - Warnings requiring attention", styles, "Warning"))
    story.append(bullet("Red - Error messages (displayed for 6 seconds)", styles, "Error"))

    story.append(PageBreak())
    return story


def build_chapter3(styles):
    """Chapter 3: Getting Started Wizard"""
    story = []
    story.append(Paragraph("3. Getting Started Wizard", styles['ChapterTitle']))
    story.append(orange_hr())

    story.append(Paragraph(
        "The Getting Started wizard is displayed at the top of the Dashboard page. It provides a visual, "
        "step-by-step guide that shows the current system readiness and walks you through the initial setup "
        "process. Each step shows its current status and links to the relevant page.",
        styles['BodyText']
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "The wizard displays a horizontal progress bar that fills as steps are completed. Steps are shown "
        "with colored icons: green (completed), orange (active/current), or gray (locked/pending).",
        styles['BodyText']
    ))
    story.append(Spacer(1, 8))

    # Step 1
    story.append(Paragraph("3.1 Step 1: Configure Settings", styles['SectionTitle']))
    story.append(Paragraph(
        "Ensure the robot IP address and port are configured in the Settings page. The wizard checks "
        "that both <font face='Courier'>robot_ip</font> and <font face='Courier'>robot_port</font> "
        "fields are set. Click this step to navigate to Settings.",
        styles['BodyText']
    ))
    story.append(bullet("Status shows 'Configured' (green) when both fields have values", styles))
    story.append(bullet("Status shows 'Not set' (red) when either field is empty", styles))

    # Step 2
    story.append(Paragraph("3.2 Step 2: Connect Robot", styles['SectionTitle']))
    story.append(Paragraph(
        "Establish a TCP connection to the KUKA robot controller via the EKI interface. Click this step "
        "to focus the robot IP input field on the Dashboard.",
        styles['BodyText']
    ))
    story.append(bullet("Status shows 'Connected' (green) when the robot is online", styles))
    story.append(bullet("Status shows 'Not connected' (red) when disconnected", styles))

    # Step 3
    story.append(Paragraph("3.3 Step 3: Open Camera", styles['SectionTitle']))
    story.append(Paragraph(
        "The camera must be opened and streaming. Click this step to navigate to the Calibration page "
        "where you can start the camera feed.",
        styles['BodyText']
    ))
    story.append(bullet("Status shows 'Opened' (green) when the camera is active", styles))
    story.append(bullet("Status shows 'Not open' (red) when the camera is closed", styles))

    # Step 4
    story.append(Paragraph("3.4 Step 4: Teach Nominal Position", styles['SectionTitle']))
    story.append(Paragraph(
        "The nominal (reference) part position must be taught before calibration can run. Click this step "
        "to navigate to the Calibration page's Calibrate tab.",
        styles['BodyText']
    ))
    story.append(bullet("Status shows 'Taught' (green) when the nominal position is saved", styles))
    story.append(bullet("Status shows 'Not taught' (red) when no nominal exists", styles))

    # Step 5
    story.append(Paragraph("3.5 Step 5: Calibrate!", styles['SectionTitle']))
    story.append(Paragraph(
        "The final step is unlocked only when all four prerequisite steps are complete. It shows how many "
        "steps remain, or 'Ready!' when all prerequisites are met.",
        styles['BodyText']
    ))
    story.append(make_tip(
        "The wizard automatically polls the system status every time you open the Dashboard. "
        "Complete steps in any order - the wizard updates in real-time.",
        styles
    ))

    story.append(PageBreak())
    return story


def build_chapter4(styles):
    """Chapter 4: Dashboard"""
    story = []
    story.append(Paragraph("4. Dashboard", styles['ChapterTitle']))
    story.append(orange_hr())

    story.append(Paragraph(
        "The Dashboard is the main overview page providing a comprehensive view of system status, "
        "live camera feed, statistics, calibration history, and event logging.",
        styles['BodyText']
    ))

    # 4.1
    story.append(Paragraph("4.1 Robot Connection", styles['SectionTitle']))
    story.append(Paragraph(
        "The Robot Connection card allows you to connect or disconnect from the KUKA robot controller.",
        styles['BodyText']
    ))
    story.append(bullet("Enter the robot's IP address and EKI port number", styles, "IP & Port"))
    story.append(bullet("Click 'Connect' (green button) to establish the TCP connection", styles, "Connect"))
    story.append(bullet("Click 'Disconnect' (red button) to close the connection", styles, "Disconnect"))
    story.append(Spacer(1, 4))
    story.append(make_note(
        "The connection status is polled every 5 seconds and reflected in the sidebar, top bar, "
        "and all relevant pages across the application.",
        styles
    ))

    # 4.2
    story.append(Paragraph("4.2 Live Camera Feed", styles['SectionTitle']))
    story.append(Paragraph(
        "The camera feed card displays a real-time video stream from the connected camera via WebSocket.",
        styles['BodyText']
    ))
    story.append(bullet("Click the play button (green) to start the video stream", styles, "Play"))
    story.append(bullet("Click the stop button (red) to stop streaming", styles, "Stop"))
    story.append(Spacer(1, 4))
    story.append(make_warning(
        "The live camera feed requires the Daphne ASGI server running on port 8001. "
        "Without it, the feed will not work.",
        styles
    ))

    # 4.3
    story.append(Paragraph("4.3 Statistics", styles['SectionTitle']))
    story.append(Paragraph(
        "Displays quick statistics for the current session:",
        styles['BodyText']
    ))
    story.append(bullet("Total Cycles - number of calibration cycles run", styles))
    story.append(bullet("Successful - number of successful calibrations", styles))
    story.append(bullet("Active Program - currently loaded KRL program name", styles))

    # 4.4
    story.append(Paragraph("4.4 Calibration History Chart", styles['SectionTitle']))
    story.append(Paragraph(
        "A line chart (Chart.js) showing the history of calibration corrections over time. "
        "Three lines are plotted: dX (red), dY (blue), and dZ (teal), measured in millimeters. "
        "Click the refresh button to reload the chart data.",
        styles['BodyText']
    ))

    # 4.5
    story.append(Paragraph("4.5 Event Log", styles['SectionTitle']))
    story.append(Paragraph(
        "A scrollable table showing the most recent system events, auto-refreshing every 10 seconds.",
        styles['BodyText']
    ))
    story.append(bullet("Filter events by category using the dropdown: Robot, Calibration, Camera, Job, Settings, System", styles, "Filter"))
    story.append(bullet("Events are color-coded: info (blue), success (green), warning (yellow), error (red)", styles, "Levels"))
    story.append(bullet("Click refresh to manually reload the event list", styles, "Refresh"))

    # 4.6
    story.append(Paragraph("4.6 Recent Calibrations Table", styles['SectionTitle']))
    story.append(Paragraph(
        "A detailed table of recent calibration results showing per-axis corrections (dX, dY, dZ, dA, dB, dC), "
        "translation and rotation magnitudes, and status (OK, FAIL, REJ).",
        styles['BodyText']
    ))
    story.append(bullet("Click 'CSV' to export calibration data as a CSV file", styles, "CSV Export"))
    story.append(bullet("Click 'Excel' to export as an XLSX spreadsheet", styles, "Excel Export"))

    story.append(PageBreak())
    return story


def build_chapter5(styles):
    """Chapter 5: Calibration Page"""
    story = []
    story.append(Paragraph("5. Calibration Page", styles['ChapterTitle']))
    story.append(orange_hr())

    story.append(Paragraph(
        "The Calibration page is the core operational hub of the system. It is organized into five tabs "
        "to group related functions and eliminate scrolling. Each tab focuses on a specific phase of "
        "the calibration workflow.",
        styles['BodyText']
    ))
    story.append(Spacer(1, 4))

    tab_data = [
        ['Tab', 'Icon', 'Purpose'],
        ['Setup', 'Check-square', 'Prerequisites check, tag scanning, position readout'],
        ['Control', 'Joystick', 'Robot jog panel, capture position'],
        ['Calibrate', 'Crosshair', 'Teach nominal, run calibration, auto-cal'],
        ['Vision', 'Camera', 'Camera feed, 2D workspace, segmentation'],
        ['Advanced', 'Gear', '3D visualization, hand-eye cal, HSV tuner'],
    ]
    story.append(section_table(tab_data, [70, 80, 360]))
    story.append(Spacer(1, 10))

    # ── Tab 1: Setup ──
    story.append(Paragraph("5.1 Setup Tab", styles['SectionTitle']))
    story.append(gray_hr())

    story.append(Paragraph("5.1.1 Prerequisites Checklist", styles['SubSection']))
    story.append(Paragraph(
        "Displays a real-time readiness checklist showing whether each system component is ready:",
        styles['BodyText']
    ))
    story.append(bullet("Hand-Eye Calibration - whether a valid hand-eye matrix is loaded", styles))
    story.append(bullet("Nominal Position Taught - whether the reference position has been saved", styles))
    story.append(bullet("Camera Connected - live status, polled every 5 seconds", styles))
    story.append(bullet("Robot Connected - live status, polled every 5 seconds", styles))

    story.append(Paragraph("5.1.2 Tag Scanner", styles['SubSection']))
    story.append(Paragraph(
        "The Tag Scanner detects all visible ArUco markers in the camera frame and lets you assign "
        "them roles (Table tag or Part tag).",
        styles['BodyText']
    ))
    story.append(numbered_step(1, "Click 'Scan All Tags' to detect visible markers.", styles))
    story.append(numbered_step(2, "Review detected tags showing ID and distance.", styles))
    story.append(numbered_step(3, "Use the dropdown for each tag to assign: Table or Part.", styles))
    story.append(numbered_step(4, "Click 'Save Assignment' when exactly 1 Table and 1 Part tag are selected.", styles))
    story.append(Spacer(1, 4))
    story.append(make_note("Current tag assignments are displayed above the scan results.", styles))

    story.append(Paragraph("5.1.3 Robot Position", styles['SubSection']))
    story.append(Paragraph(
        "Shows the current robot TCP position in both Cartesian (X, Y, Z, A, B, C) and Joint "
        "(A1-A6) coordinates.",
        styles['BodyText']
    ))
    story.append(bullet("Click 'Live' to enable continuous position updates at 2 Hz", styles, "Live Mode"))
    story.append(bullet("Click 'Refresh' for a one-time position update", styles, "Manual Refresh"))
    story.append(Spacer(1, 10))

    # ── Tab 2: Control ──
    story.append(Paragraph("5.2 Control Tab", styles['SectionTitle']))
    story.append(gray_hr())

    story.append(Paragraph("5.2.1 Position Readout", styles['SubSection']))
    story.append(Paragraph(
        "A compact horizontal bar showing real-time X, Y, Z, A, B, C values, mirrored from the "
        "Setup tab's robot position card.",
        styles['BodyText']
    ))

    story.append(Paragraph("5.2.2 Robot Jog Panel", styles['SubSection']))
    story.append(Paragraph(
        "Provides manual control to move the robot in small increments. Essential for positioning "
        "the robot during setup and teaching operations.",
        styles['BodyText']
    ))
    story.append(Spacer(1, 4))
    story.append(bullet("Toggle between Cartesian (X/Y/Z/A/B/C) and Joint (A1-A6) jog modes", styles, "Mode"))
    story.append(bullet("Select step size: 0.1, 1, 10, or 50 mm (or degrees for rotation)", styles, "Step Size"))
    story.append(bullet("Adjust speed override: 1-100% (default 10%)", styles, "Speed"))
    story.append(bullet("Press +/- buttons for each axis to jog the robot", styles, "Jog Buttons"))
    story.append(Spacer(1, 4))
    story.append(make_caution(
        "Always start with small step sizes (0.1 or 1 mm) and low speed. Larger steps can cause rapid "
        "robot movement. Ensure the workspace is clear before jogging.",
        styles
    ))

    story.append(Paragraph("5.2.3 Capture Position", styles['SubSection']))
    story.append(Paragraph(
        "Saves the current robot joint position as the capture (measurement) position. This is the "
        "pose the robot moves to when performing a calibration cycle to take camera images.",
        styles['BodyText']
    ))
    story.append(bullet("Jog the robot to the desired capture position with the camera viewing the workspace", styles))
    story.append(bullet("Click 'Teach from Current' and confirm the dialog to save", styles))
    story.append(Spacer(1, 10))

    # ── Tab 3: Calibrate ──
    story.append(Paragraph("5.3 Calibrate Tab", styles['SectionTitle']))
    story.append(gray_hr())

    story.append(Paragraph("5.3.1 Step 1: Teach Nominal Position", styles['SubSection']))
    story.append(Paragraph(
        "The nominal position is the reference location of the part relative to the table tag. "
        "Place the part at its ideal position with the ArUco tag mounted, then click 'Teach Nominal'.",
        styles['BodyText']
    ))
    story.append(make_warning(
        "Both the table tag and part tag must be visible to the camera at the capture position. "
        "If either tag is not detected, the teach operation will fail.",
        styles
    ))

    story.append(Paragraph("5.3.2 Step 2: Run Calibration Cycle", styles['SubSection']))
    story.append(Paragraph(
        "Click the large green 'CALIBRATE' button to run a single calibration cycle. The system will:",
        styles['BodyText']
    ))
    story.append(bullet("Move the robot to the capture position", styles))
    story.append(bullet("Capture a camera image and detect ArUco tags", styles))
    story.append(bullet("Compute the displacement from the nominal position", styles))
    story.append(bullet("Calculate the corrected base frame ($BASE)", styles))
    story.append(bullet("Send the correction to the robot controller", styles))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "The Calibration Result card appears showing per-axis corrections (dX-dC) and the corrected base frame values.",
        styles['BodyText']
    ))

    story.append(Paragraph("5.3.3 Auto-Calibration", styles['SubSection']))
    story.append(Paragraph(
        "Run multiple calibration cycles automatically:",
        styles['BodyText']
    ))
    story.append(bullet("Set the number of cycles (1-20, default 3)", styles, "Cycles"))
    story.append(bullet("Click 'Auto-Calibrate' to run N consecutive cycles", styles, "Auto-Calibrate"))
    story.append(bullet("Click 'Repeatability' to run a repeatability test that reports statistics (mean, std, range)", styles, "Repeatability"))
    story.append(bullet("Enable the 'Dry Run' switch to simulate without sending corrections to the robot", styles, "Dry Run"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Results show average corrections per axis, color-coded: green (below 1mm), yellow (1-5mm), red (above 5mm).",
        styles['BodyText']
    ))
    story.append(Spacer(1, 10))

    # ── Tab 4: Vision ──
    story.append(Paragraph("5.4 Vision Tab", styles['SectionTitle']))
    story.append(gray_hr())

    story.append(Paragraph("5.4.1 Camera Feed", styles['SubSection']))
    story.append(Paragraph(
        "Live camera stream displayed via WebSocket, identical to the dashboard camera feed. "
        "Use play/stop buttons to control streaming.",
        styles['BodyText']
    ))

    story.append(Paragraph("5.4.2 XY Plane Workspace Visualization", styles['SubSection']))
    story.append(Paragraph(
        "A 2D canvas rendering showing a bird's-eye view of the workspace in the table tag's coordinate frame.",
        styles['BodyText']
    ))
    story.append(bullet("Table tag shown at the origin as a green square", styles, "Table Tag"))
    story.append(bullet("Nominal part position shown as a cyan wireframe", styles, "Nominal"))
    story.append(bullet("Current part position shown as an orange circle", styles, "Current"))
    story.append(bullet("Red dashed arrow shows displacement from nominal to current", styles, "Displacement"))
    story.append(Spacer(1, 4))
    story.append(bullet("Click 'Capture' for a one-time workspace snapshot", styles))
    story.append(bullet("Click 'Auto' to continuously update every second", styles))

    story.append(Paragraph("5.4.3 Workspace Coordinates", styles['SubSection']))
    story.append(Paragraph(
        "Numerical coordinate readout showing table tag origin, current part position, nominal position, "
        "and computed displacement. Displacement values are color-coded by magnitude.",
        styles['BodyText']
    ))

    story.append(Paragraph("5.4.4 Segmentation Diagnostics", styles['SubSection']))
    story.append(Paragraph(
        "Shows a 4-panel diagnostic view of the tag detection pipeline: Raw image, CLAHE enhanced, "
        "adaptive threshold, and detection overlay. Useful for debugging detection issues.",
        styles['BodyText']
    ))
    story.append(bullet("Click 'Capture' for a one-time diagnostic frame", styles))
    story.append(bullet("Click 'Auto' for continuous diagnostics at 1.5-second intervals", styles))
    story.append(bullet("Shows number of tags found, rejected candidates, and per-tag details", styles))

    story.append(PageBreak())

    # ── Tab 5: Advanced ──
    story.append(Paragraph("5.5 Advanced Tab", styles['SectionTitle']))
    story.append(gray_hr())

    story.append(Paragraph("5.5.1 3D Workspace View", styles['SubSection']))
    story.append(Paragraph(
        "An interactive Three.js 3D scene showing the spatial relationship between the table tag, "
        "nominal position, and current part position. Use the mouse to orbit, zoom, and pan.",
        styles['BodyText']
    ))
    story.append(bullet("Green cube at origin = table tag", styles))
    story.append(bullet("Blue wireframe = nominal position", styles))
    story.append(bullet("Orange sphere = current part position", styles))
    story.append(bullet("Click 'Update' to refresh positions from the camera", styles))

    story.append(Paragraph("5.5.2 Hand-Eye Calibration", styles['SubSection']))
    story.append(Paragraph(
        "Computes the transformation matrix between the camera and the robot's end-effector (hand-eye calibration). "
        "This is required for accurate coordinate transformation.",
        styles['BodyText']
    ))
    story.append(numbered_step(1, "Move the robot so the table tag is visible from different angles.", styles))
    story.append(numbered_step(2, "Click 'Capture Sample' at each pose (minimum 5 samples required).", styles))
    story.append(numbered_step(3, "Click 'Compute' when you have enough samples.", styles))
    story.append(numbered_step(4, "Click 'Apply to Settings' to save the computed matrix.", styles))
    story.append(Spacer(1, 4))
    story.append(make_tip(
        "Capture samples from widely varying angles and distances. More diverse poses yield "
        "a more accurate hand-eye calibration. 10-15 samples from different orientations is recommended.",
        styles
    ))
    story.append(bullet("Click 'Reset' (red) to clear all samples and start over", styles, "Reset"))

    story.append(Paragraph("5.5.3 HSV Color Tuner", styles['SubSection']))
    story.append(Paragraph(
        "Adjust HSV (Hue, Saturation, Value) color thresholds for image preprocessing. Six sliders "
        "control the lower and upper bounds for H, S, and V channels.",
        styles['BodyText']
    ))
    story.append(bullet("Adjust sliders to define the color range of interest", styles))
    story.append(bullet("Click 'Preview' to see the filtered camera image", styles))
    story.append(bullet("The mask percentage shows how much of the image falls within the HSV range", styles))
    story.append(bullet("Click 'Save' to store the HSV bounds to settings", styles))

    story.append(PageBreak())
    return story


def build_chapter6(styles):
    """Chapter 6: KRL Programs (Jobs)"""
    story = []
    story.append(Paragraph("6. KRL Programs (Jobs)", styles['ChapterTitle']))
    story.append(orange_hr())

    story.append(Paragraph(
        "The Jobs page manages KUKA Robot Language (KRL) programs. You can upload .src/.dat files, "
        "view source code with syntax highlighting, activate programs, and execute calibrated motion cycles.",
        styles['BodyText']
    ))

    # 6.1
    story.append(Paragraph("6.1 Uploading Programs", styles['SectionTitle']))
    story.append(numbered_step(1, "Select a <b>.src file</b> (required) - the main KRL source.", styles))
    story.append(numbered_step(2, "Optionally select a <b>.dat file</b> - the data file with point declarations.", styles))
    story.append(numbered_step(3, "Enter a program name (or leave blank to auto-detect from the DEF statement).", styles))
    story.append(numbered_step(4, "Optionally add a description.", styles))
    story.append(numbered_step(5, "Click 'Upload' to submit.", styles))
    story.append(Spacer(1, 4))
    story.append(make_note("The system automatically parses the .src file to count motion points.", styles))

    # 6.2
    story.append(Paragraph("6.2 Managing Programs", styles['SectionTitle']))
    story.append(Paragraph("The Programs table lists all uploaded KRL programs with the following actions:", styles['BodyText']))
    story.append(Spacer(1, 4))

    action_data = [
        ['Action', 'Icon', 'Description'],
        ['View Source', 'Code', 'Opens a modal with syntax-highlighted KRL code'],
        ['Activate', 'Check', 'Sets this program as the active program for execution'],
        ['Statistics', 'Chart', 'Shows execution statistics (cycles, errors, durations)'],
        ['Delete', 'Trash', 'Permanently removes the program (with confirmation)'],
    ]
    story.append(section_table(action_data, [80, 50, 380]))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "The source viewer provides syntax highlighting for KRL keywords (DEF, END), motion commands "
        "(PTP, LIN, CIRC), control flow (IF, FOR, WHILE), and comments.",
        styles['BodyText']
    ))

    # 6.3
    story.append(Paragraph("6.3 Executing Cycles", styles['SectionTitle']))
    story.append(Paragraph(
        "The Execute Cycle card runs the active KRL program on the robot:",
        styles['BodyText']
    ))
    story.append(bullet("Enable 'Auto-calibrate before execution' (checked by default) to run a calibration cycle before program execution", styles))
    story.append(bullet("Click 'Execute Cycle' to start - the robot will run the loaded program", styles))
    story.append(bullet("Results show cycle number, duration, and whether calibration was applied", styles))
    story.append(Spacer(1, 4))
    story.append(make_caution(
        "Ensure the workspace is clear and safety systems are active before executing robot programs.",
        styles
    ))

    story.append(PageBreak())
    return story


def build_chapter7(styles):
    """Chapter 7: Camera Calibration"""
    story = []
    story.append(Paragraph("7. Camera Calibration", styles['ChapterTitle']))
    story.append(orange_hr())

    story.append(Paragraph(
        "The Camera Calibration page performs intrinsic camera calibration using a chessboard pattern. "
        "This calibration determines the camera's focal length, principal point, and distortion coefficients, "
        "which are essential for accurate ArUco tag detection.",
        styles['BodyText']
    ))

    # 7.1
    story.append(Paragraph("7.1 Chessboard Settings", styles['SectionTitle']))
    story.append(Paragraph("Configure the chessboard pattern parameters:", styles['BodyText']))

    chess_data = [
        ['Parameter', 'Default', 'Description'],
        ['Rows', '9', 'Number of inner corners (rows)'],
        ['Cols', '6', 'Number of inner corners (columns)'],
        ['Square (mm)', '25', 'Physical size of each square in millimeters'],
    ]
    story.append(section_table(chess_data, [90, 60, 360]))
    story.append(Spacer(1, 6))

    story.append(make_note(
        "The rows and columns refer to inner corners, not squares. A standard 10x7 chessboard "
        "has 9x6 inner corners.",
        styles
    ))

    # 7.2
    story.append(Paragraph("7.2 Capturing Frames", styles['SectionTitle']))
    story.append(numbered_step(1, "Hold the chessboard pattern in front of the camera.", styles))
    story.append(numbered_step(2, "Click 'Detect Board' to preview corner detection (without saving).", styles))
    story.append(numbered_step(3, "When corners are detected correctly, click 'Capture Frame' to save.", styles))
    story.append(numbered_step(4, "Move the board to a different angle/distance and repeat.", styles))
    story.append(numbered_step(5, "Capture at least 5 frames (15-25 recommended for best results).", styles))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "A progress bar shows how many frames have been captured out of the recommended 15.",
        styles['BodyText']
    ))
    story.append(make_tip(
        "Vary the board position, angle, and distance between captures. Include tilted views "
        "and positions near the edges of the frame for better calibration.",
        styles
    ))

    # 7.3
    story.append(Paragraph("7.3 Computing Calibration", styles['SectionTitle']))
    story.append(Paragraph(
        "Once 5 or more frames are captured, the 'Compute Calibration' button becomes active. "
        "Click it to compute the camera intrinsic parameters. The results show:",
        styles['BodyText']
    ))
    story.append(bullet("RMS Error - reprojection error (green: below 1, yellow: 1-2, red: above 2)", styles))
    story.append(bullet("fx, fy - focal lengths in pixels", styles))
    story.append(bullet("cx, cy - principal point coordinates", styles))
    story.append(bullet("Frames - number of frames used in computation", styles))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Click 'Apply to Settings' to save the computed parameters as the active camera calibration. "
        "The page will reload to reflect the new values.",
        styles['BodyText']
    ))

    # 7.4
    story.append(Paragraph("7.4 Calibration History", styles['SectionTitle']))
    story.append(Paragraph(
        "A table of all previous camera calibrations showing date, RMS error, pose count, intrinsic "
        "parameters, board dimensions, and whether the calibration is currently applied. "
        "You can apply any historical calibration by clicking the 'Apply' button in its row.",
        styles['BodyText']
    ))

    story.append(PageBreak())
    return story


def build_chapter8(styles):
    """Chapter 8: Settings"""
    story = []
    story.append(Paragraph("8. Settings", styles['ChapterTitle']))
    story.append(orange_hr())

    story.append(Paragraph(
        "The Settings page centralizes all system configuration. Changes are saved by clicking "
        "the green 'Save Settings' button at the bottom of the form.",
        styles['BodyText']
    ))

    # 8.1
    story.append(Paragraph("8.1 Robot Configuration", styles['SectionTitle']))
    settings_robot = [
        ['Field', 'Description'],
        ['IP Address', 'KUKA robot controller IP (e.g., 192.168.1.1)'],
        ['Port', 'EKI communication port (e.g., 54610)'],
        ['Override %', 'Robot speed override percentage (1-100%)'],
    ]
    story.append(section_table(settings_robot))

    # 8.2
    story.append(Paragraph("8.2 Camera Configuration", styles['SectionTitle']))
    settings_camera = [
        ['Field', 'Description'],
        ['Index', 'Camera device index (usually 0)'],
        ['FPS', 'Desired frames per second'],
        ['Width / Height', 'Camera resolution in pixels'],
        ['fx, fy', 'Focal lengths (from camera calibration)'],
        ['cx, cy', 'Principal point (from camera calibration)'],
    ]
    story.append(section_table(settings_camera))

    # 8.3
    story.append(Paragraph("8.3 ArUco Tag Configuration", styles['SectionTitle']))
    settings_aruco = [
        ['Field', 'Description'],
        ['Dictionary', 'ArUco dictionary type (auto-detected if wrong)'],
        ['Table Tag ID', 'ArUco ID of the table reference tag'],
        ['Part Tag ID', 'ArUco ID of the part tag'],
        ['Tag Size (mm)', 'Physical size of the ArUco marker'],
        ['Max Correction (mm)', 'Maximum allowed translation correction'],
        ['Max Correction (deg)', 'Maximum allowed rotation correction'],
    ]
    story.append(section_table(settings_aruco))
    story.append(Spacer(1, 4))
    story.append(make_note(
        "Corrections exceeding the maximum thresholds will be rejected (status: REJ) "
        "to prevent unsafe robot movements.",
        styles
    ))

    # 8.4
    story.append(Paragraph("8.4 Nominal Base Frame", styles['SectionTitle']))
    story.append(Paragraph(
        "The nominal $BASE frame defines the robot's reference coordinate system. Enter the six "
        "components: X, Y, Z (mm) and A, B, C (degrees). This frame is the starting point for "
        "calibration corrections.",
        styles['BodyText']
    ))

    # 8.5
    story.append(Paragraph("8.5 Hand-Eye Matrix", styles['SectionTitle']))
    story.append(Paragraph(
        "The 4x4 transformation matrix from hand-eye calibration. This can be pasted as a JSON "
        "array or computed and applied from the Calibration > Advanced > Hand-Eye Calibration card.",
        styles['BodyText']
    ))

    # 8.6
    story.append(Paragraph("8.6 Base Frame Management", styles['SectionTitle']))
    story.append(Paragraph(
        "Manage multiple robot base frames (up to 32, matching KUKA $BASE[1] through $BASE[32]).",
        styles['BodyText']
    ))
    story.append(bullet("Click 'Add Frame' to create a new base frame with name, BASE number, and X/Y/Z/A/B/C values", styles, "Add"))
    story.append(bullet("Click 'Activate' to set a frame as the active calibration reference", styles, "Activate"))
    story.append(bullet("Click 'Edit' to modify an existing frame's values", styles, "Edit"))
    story.append(bullet("Click 'Delete' to remove a frame (with confirmation)", styles, "Delete"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Each frame shows badges: 'HE' (blue) if hand-eye data is attached, 'NOM' (yellow) if "
        "nominal data is saved for that frame.",
        styles['BodyText']
    ))

    # 8.7
    story.append(Paragraph("8.7 Backup & Restore", styles['SectionTitle']))
    story.append(Paragraph(
        "Create a complete backup of all settings, base frames, and capture positions as a JSON file.",
        styles['BodyText']
    ))
    story.append(bullet("Click 'Download Backup' to save a JSON backup file", styles, "Backup"))
    story.append(bullet("Click 'Restore from File' to upload and apply a previous backup", styles, "Restore"))
    story.append(Spacer(1, 4))
    story.append(make_warning(
        "Restoring from a backup will overwrite ALL current settings. A confirmation dialog "
        "will appear before the restore is applied.",
        styles
    ))

    story.append(PageBreak())
    return story


def build_chapter9(styles):
    """Chapter 9: Troubleshooting"""
    story = []
    story.append(Paragraph("9. Troubleshooting", styles['ChapterTitle']))
    story.append(orange_hr())

    issues = [
        ["Robot won't connect",
         "Verify the IP address and port match the KUKA controller's EKI configuration. "
         "Ensure the robot is powered on and the network cable is connected. Check that no "
         "firewall is blocking the port."],
        ["Camera feed is black / won't start",
         "Ensure the Daphne ASGI server is running on port 8001. Check that the camera index "
         "in Settings matches your camera device. Try a different camera index (0, 1, 2)."],
        ["Tags not detected",
         "Ensure adequate lighting. Check that the correct ArUco dictionary is selected in Settings. "
         "Use the Segmentation Diagnostics in the Vision tab to debug detection. Ensure tags are "
         "not too far from the camera or at extreme angles."],
        ["Calibration returns REJ status",
         "The computed correction exceeds the maximum thresholds set in Settings. Either increase "
         "the Max Correction limits or investigate why the part displacement is so large."],
        ["Teach Nominal fails",
         "Both the table tag and part tag must be visible to the camera at the capture position. "
         "Check tag assignments in the Setup tab's Tag Scanner."],
        ["Hand-Eye calibration is inaccurate",
         "Capture more samples (15+) from diverse robot poses. Ensure the table tag is fully "
         "visible in all captured frames. Avoid capturing samples where the tag is at the edge "
         "of the camera frame."],
        ["Camera calibration RMS is high (> 2.0)",
         "Re-capture calibration frames. Ensure the chessboard is flat and well-lit. Include "
         "frames from various angles and distances. Avoid motion blur."],
        ["WebSocket connection fails",
         "Ensure the Daphne server is running: daphne -b 0.0.0.0 -p 8001 mcv_milling.asgi:application. "
         "Check browser console for WebSocket errors."],
    ]

    for issue, solution in issues:
        story.append(Paragraph(f'<b>{issue}</b>', styles['BodyText']))
        story.append(Paragraph(solution, styles['NoteText']))
        story.append(Spacer(1, 6))

    story.append(PageBreak())
    return story


def build_chapter10(styles):
    """Chapter 10: Quick Reference"""
    story = []
    story.append(Paragraph("10. Quick Reference", styles['ChapterTitle']))
    story.append(orange_hr())

    # Workflow summary
    story.append(Paragraph("10.1 Typical Calibration Workflow", styles['SectionTitle']))
    workflow = [
        ['Step', 'Action', 'Page / Tab'],
        ['1', 'Configure robot IP, port, and camera settings', 'Settings'],
        ['2', 'Connect to the robot', 'Dashboard'],
        ['3', 'Start the camera feed and verify image quality', 'Dashboard or Calibration > Vision'],
        ['4', 'Run Camera Calibration (if not done)', 'Camera Cal'],
        ['5', 'Perform Hand-Eye Calibration (if not done)', 'Calibration > Advanced'],
        ['6', 'Scan and assign Table/Part tags', 'Calibration > Setup'],
        ['7', 'Jog robot to capture position and save it', 'Calibration > Control'],
        ['8', 'Place part at reference position, Teach Nominal', 'Calibration > Calibrate'],
        ['9', 'Run calibration cycle(s)', 'Calibration > Calibrate'],
        ['10', 'Verify results in Vision tab and History chart', 'Calibration > Vision / Dashboard'],
    ]
    t = Table(workflow, colWidths=[35, 280, 195])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEADING', (0, 0), (-1, -1), 13),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Keyboard shortcuts / color codes
    story.append(Paragraph("10.2 Color Code Reference", styles['SectionTitle']))
    colors_ref = [
        ['Color', 'Meaning'],
        ['Green', 'Connected / OK / Completed / Below threshold'],
        ['Orange', 'Active step / Current / Accent highlights'],
        ['Yellow', 'Warning / Part tag / 1-5mm correction'],
        ['Red', 'Error / Disconnected / Above 5mm correction'],
        ['Cyan', 'Nominal values / Joint positions / Info'],
        ['Blue', 'Information / Hand-eye data / Interactive elements'],
    ]
    story.append(section_table(colors_ref, [80, 430]))
    story.append(Spacer(1, 12))

    # Status codes
    story.append(Paragraph("10.3 Calibration Status Codes", styles['SectionTitle']))
    status_ref = [
        ['Code', 'Badge', 'Meaning'],
        ['OK', 'Green', 'Calibration successful, correction applied to robot'],
        ['FAIL', 'Red', 'Calibration failed (tag detection error, computation error)'],
        ['REJ', 'Yellow', 'Correction rejected (exceeded max threshold limits)'],
    ]
    story.append(section_table(status_ref, [50, 60, 400]))

    return story


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    output_path = os.path.join(os.path.dirname(__file__), "MCV_Vision_User_Manual.pdf")

    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 8,
        bottomMargin=MARGIN + 8,
        title="MCV Milling Vision - GUI User Manual",
        author="MCV Vision System",
        subject="User manual for the MCV Milling Vision calibration GUI",
    )

    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id='main_frame'
    )

    cover_template = PageTemplate(id='cover', frames=frame, onPage=cover_page)
    normal_template = PageTemplate(id='normal', frames=frame, onPage=header_footer)

    doc.addPageTemplates([cover_template, normal_template])

    styles = build_styles()

    # Build complete story
    story = []

    # Cover page
    story += build_cover(styles)

    # Switch to normal template after cover
    from reportlab.platypus import NextPageTemplate
    story.insert(len(story) - 1, NextPageTemplate('normal'))

    # Table of Contents
    story += build_toc(styles)

    # Chapters
    story += build_chapter1(styles)
    story += build_chapter2(styles)
    story += build_chapter3(styles)
    story += build_chapter4(styles)
    story += build_chapter5(styles)
    story += build_chapter6(styles)
    story += build_chapter7(styles)
    story += build_chapter8(styles)
    story += build_chapter9(styles)
    story += build_chapter10(styles)

    # Build PDF
    doc.build(story)
    print(f"PDF generated successfully: {output_path}")
    print(f"File size: {os.path.getsize(output_path) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
