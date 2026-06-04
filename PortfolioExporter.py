from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import date
import pandas as pd

# RFG-style color scheme
DARK_BLUE = colors.HexColor('#003366')
LIGHT_BLUE = colors.HexColor('#E8F0F7')
MID_BLUE = colors.HexColor('#336699')
WHITE = colors.white
LIGHT_GRAY = colors.HexColor('#F5F5F5')
DARK_GRAY = colors.HexColor('#333333')

def get_num_funds(allocation_pct: float) -> int:
    """
    Determine number of funds based on allocation size:
    - Under 10%: 1 fund
    - Under 20%: 2 funds
    - 20% or more: 3 funds
    """
    if allocation_pct < 0.10:
        return 1
    elif allocation_pct < 0.20:
        return 2
    else:
        return 3

def build_portfolio_report(
    portfolio: dict,
    allocations: dict,
    client_name: str,
    portfolio_name: str,
    investment_amount: float
) -> BytesIO:
    """
    Build a professional PDF portfolio report.
    Returns a BytesIO object containing the PDF.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    styles = getSampleStyleSheet()
    story = []

    # --- Header ---
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=10,
        textColor=DARK_GRAY,
        alignment=TA_RIGHT
    )
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Normal'],
        fontSize=16,
        textColor=DARK_BLUE,
        fontName='Helvetica-Bold',
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=MID_BLUE,
        fontName='Helvetica-Bold',
        spaceAfter=4
    )
    small_style = ParagraphStyle(
        'Small',
        parent=styles['Normal'],
        fontSize=8,
        textColor=DARK_GRAY
    )

    # Header table (logo placeholder left, info right)
    today = date.today().strftime("%B %d, %Y")
    timeframe_start = date.today().replace(year=date.today().year - 1).strftime("%b-%d-%Y")
    timeframe_end = date.today().strftime("%b-%d-%Y")

    header_data = [
        [
            Paragraph('<b>ASPIRE</b>', ParagraphStyle('Logo', fontSize=18, textColor=DARK_BLUE, fontName='Helvetica-Bold')),
            Paragraph(
                f'Prepared For: <b>{client_name}</b><br/>'
                f'Risk Profile: <b>{portfolio_name}</b><br/>'
                f'Date: {today}<br/>'
                f'Investment Amount: <b>${investment_amount:,.2f}</b>',
                header_style
            )
        ]
    ]
    header_table = Table(header_data, colWidths=[3.5*inch, 4*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)

    # Horizontal line
    story.append(HRFlowable(width="100%", thickness=2, color=DARK_BLUE))
    story.append(Spacer(1, 4))

    # Timeframe
    story.append(Paragraph(
        f'Timeframe: {timeframe_start} to {timeframe_end}',
        small_style
    ))
    story.append(Spacer(1, 8))

    # --- Holdings Table ---
    story.append(Paragraph('Holdings', subtitle_style))
    story.append(Spacer(1, 4))

    # Table headers
    col_headers = [
        'Symbol', 'Allocation\n%', 'Volatility', 'Name',
        'Asset Class', 'Expense\nRatio', 'Yield', 'Total\nReturn'
    ]

    col_widths = [0.55*inch, 0.55*inch, 0.55*inch, 1.8*inch, 1.3*inch, 0.55*inch, 0.45*inch, 0.55*inch]

    header_cell_style = ParagraphStyle(
        'TableHeader',
        fontSize=7,
        fontName='Helvetica-Bold',
        textColor=WHITE,
        alignment=TA_CENTER
    )
    cell_style = ParagraphStyle(
        'TableCell',
        fontSize=7,
        textColor=DARK_GRAY,
        alignment=TA_LEFT
    )
    center_cell_style = ParagraphStyle(
        'CenterCell',
        fontSize=7,
        textColor=DARK_GRAY,
        alignment=TA_CENTER
    )

    table_data = [[Paragraph(h, header_cell_style) for h in col_headers]]

    # Build rows
    row_num = 0
    total_allocation = 0

    for allocation_name, allocation_info in allocations.items():
        allocation_pct = allocation_info['pct']
        if allocation_pct == 0:
            continue

        funds_list = portfolio.get(allocation_name, [])
        if not funds_list:
            continue

        # Determine how many funds to show
        num_funds = get_num_funds(allocation_pct)
        selected_funds = funds_list[:num_funds]

        # Calculate score-weighted allocation per fund
        total_score = sum(f.score for f in selected_funds)
        
        for fund in selected_funds:
            if total_score > 0:
                fund_pct = (fund.score / total_score) * allocation_pct
            else:
                fund_pct = allocation_pct / len(selected_funds)

            total_allocation += fund_pct

            # Format values
            ticker = fund.ticker or 'N/A'
            name = fund.name or 'N/A'
            asset_class = fund.morningstar_cat or 'N/A'
            expense = f"{fund.expense_ratio:.2f}%" if fund.expense_ratio else 'N/A'
            volatility = f"{fund.std3yr:.2f}" if hasattr(fund, 'std3yr') and fund.std3yr else 'N/A'
            yield_val = f"{fund.yield_val:.2f}%" if hasattr(fund, 'yield_val') and fund.yield_val else 'N/A'
            total_return = f"{fund.return_1yr * 100:.2f}%" if fund.return_1yr else 'N/A'
            alloc_display = f"{fund_pct * 100:.2f}%"

            row = [
                Paragraph(ticker, center_cell_style),
                Paragraph(alloc_display, center_cell_style),
                Paragraph(str(volatility), center_cell_style),
                Paragraph(name, cell_style),
                Paragraph(asset_class, cell_style),
                Paragraph(expense, center_cell_style),
                Paragraph(yield_val, center_cell_style),
                Paragraph(total_return, center_cell_style),
            ]
            table_data.append(row)
            row_num += 1

    # Add total row
    table_data.append([
        Paragraph('<b>Total:</b>', center_cell_style),
        Paragraph(f'<b>{total_allocation * 100:.2f}%</b>', center_cell_style),
        Paragraph('', center_cell_style),
        Paragraph('', cell_style),
        Paragraph('', cell_style),
        Paragraph('', center_cell_style),
        Paragraph('', center_cell_style),
        Paragraph('', center_cell_style),
    ])

    # Build table
    holdings_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Style the table
    table_style = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [WHITE, LIGHT_GRAY]),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#CCCCCC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        # Total row
        ('BACKGROUND', (0, -1), (-1, -1), LIGHT_BLUE),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, DARK_BLUE),
    ]
    holdings_table.setStyle(TableStyle(table_style))
    story.append(holdings_table)

    # Footer
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'For Intended Recipient Only. Rankings generated by Aspire Portfolio Builder. '
        'Past performance does not guarantee future results.',
        ParagraphStyle('Footer', fontSize=7, textColor=DARK_GRAY, alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer