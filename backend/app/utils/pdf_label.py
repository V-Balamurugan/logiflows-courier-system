import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import qrcode


def generate_shipping_label_pdf(parcel_data: dict) -> bytes:
    """Generates an industry-standard 4x6 / letter shipping label PDF for a parcel."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        alignment=0
    )
    bold_style = ParagraphStyle(
        'BoldText',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        fontName='Helvetica-Bold'
    )
    regular_style = ParagraphStyle(
        'RegularText',
        parent=styles['Normal'],
        fontSize=10,
        leading=13
    )
    badge_style = ParagraphStyle(
        'Badge',
        parent=styles['Normal'],
        fontSize=14,
        leading=16,
        fontName='Helvetica-Bold',
        textColor=colors.white,
        alignment=1
    )

    elements = []

    # Header with Tracking & Service Type
    header_data = [
        [
            Paragraph("<b>LOGIFLOWS EXPRESS</b><br/><font size=9>Logistics & Delivery System</font>", regular_style),
            Paragraph(f"<font size=16><b>{parcel_data.get('service_type', 'STANDARD')}</b></font>", ParagraphStyle('HRight', parent=regular_style, alignment=2))
        ]
    ]
    header_table = Table(header_data, colWidths=[300, 240])
    header_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#0f172a')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 15))

    # Tracking Number Banner
    tracking_no = parcel_data.get("tracking_number", "LF-0000-000000")
    trk_data = [
        [Paragraph(f"TRACKING #: <b>{tracking_no}</b>", ParagraphStyle('Trk', parent=title_style, fontSize=16, alignment=1))]
    ]
    trk_table = Table(trk_data, colWidths=[540])
    trk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(trk_table)
    elements.append(Spacer(1, 15))

    # Sender and Receiver Details
    sender_text = f"""
    <b>FROM (SENDER):</b><br/>
    {parcel_data.get('sender_name', '')}<br/>
    {parcel_data.get('sender_address', '')}<br/>
    {parcel_data.get('sender_city', '')}, {parcel_data.get('sender_state', '')} - {parcel_data.get('sender_pincode', '')}<br/>
    Phone: {parcel_data.get('sender_phone', '')}
    """

    receiver_text = f"""
    <b>SHIP TO (RECEIVER):</b><br/>
    <font size=12><b>{parcel_data.get('receiver_name', '')}</b></font><br/>
    {parcel_data.get('receiver_address', '')}<br/>
    <b>{parcel_data.get('receiver_city', '')}, {parcel_data.get('receiver_state', '')} - {parcel_data.get('receiver_pincode', '')}</b><br/>
    Phone: {parcel_data.get('receiver_phone', '')}
    """

    addr_data = [
        [Paragraph(sender_text, regular_style), Paragraph(receiver_text, regular_style)]
    ]
    addr_table = Table(addr_data, colWidths=[270, 270])
    addr_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#94a3b8')),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(addr_table)
    elements.append(Spacer(1, 15))

    # QR Code & Parcel Metrics
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(tracking_no)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_io = io.BytesIO()
    qr_img.save(qr_io, format="PNG")
    qr_io.seek(0)
    rl_qr = RLImage(qr_io, width=120, height=120)

    metrics_text = f"""
    <b>PARCEL SPECIFICATIONS:</b><br/>
    Weight: {parcel_data.get('weight_kg', 0)} kg<br/>
    Dimensions: {parcel_data.get('length_cm', 0)} x {parcel_data.get('width_cm', 0)} x {parcel_data.get('height_cm', 0)} cm<br/>
    Volumetric Wt: {parcel_data.get('volumetric_weight_kg', 0)} kg<br/>
    Payment Status: <b>{parcel_data.get('payment_status', 'PAID')}</b><br/>
    Booking Date: {parcel_data.get('booking_date', '')[:10]}
    """

    bottom_data = [
        [rl_qr, Paragraph(metrics_text, regular_style)]
    ]
    bottom_table = Table(bottom_data, colWidths=[140, 400])
    bottom_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#94a3b8')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(bottom_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

