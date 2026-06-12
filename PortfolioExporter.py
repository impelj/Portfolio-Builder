from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import date
from collections import defaultdict

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


def build_portfolio_rows(portfolio, allocations):
    """
    Build fund rows with score-weighted allocations.
    Fixes the total % bug by normalizing to exactly 100%.
    Returns list of (fund, fund_pct, allocation_name) tuples.
    """
    rows = []

    for allocation_name, allocation_info in allocations.items():
        allocation_pct = allocation_info['pct']
        if allocation_pct == 0:
            continue

        funds_list = portfolio.get(allocation_name, [])
        if not funds_list:
            continue

        num_funds = get_num_funds(allocation_pct)
        selected_funds = funds_list[:num_funds]

        # Score-weighted split within allocation
        total_score = sum(f.score for f in selected_funds if f.score)
        for fund in selected_funds:
            if total_score > 0:
                fund_pct = (fund.score / total_score) * allocation_pct
            else:
                fund_pct = allocation_pct / len(selected_funds)
            rows.append((fund, fund_pct, allocation_name))

    # Fix total % bug: normalize so rows sum to exactly the total allocation
    raw_total = sum(pct for _, pct, _ in rows)
    expected_total = sum(
        info['pct'] for info in allocations.values() if info['pct'] > 0
    )

    if raw_total > 0:
        scale = expected_total / raw_total
        rows = [(fund, pct * scale, name) for fund, pct, name in rows]

    # Round allocations and fix rounding errors
    rounded = [(fund, round(pct * 100), name) for fund, pct, name in rows]

    # Fix rounding so it sums to exactly 100
    target = round(expected_total * 100)
    diff = target - sum(pct for _, pct, _ in rounded)

    if diff != 0:
        # Add/subtract the difference from the largest allocation
        largest_idx = max(range(len(rounded)), key=lambda i: rounded[i][1])
        fund, pct, name = rounded[largest_idx]
        rounded[largest_idx] = (fund, pct + diff, name)

    return rounded


def build_asset_class_summary(rows):
    """
    Build a summary of allocations grouped by asset class (allocation_name).
    Returns list of (allocation_name, total_pct) tuples sorted by pct desc.
    """
    summary = defaultdict(int)
    for _, pct, allocation_name in rows:
        summary[allocation_name] += pct

    return sorted(summary.items(), key=lambda x: x[1], reverse=True)


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

    # --- Styles ---
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=10,
        textColor=DARK_GRAY,
        alignment=TA_RIGHT
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=DARK_BLUE,
        fontName='Helvetica-Bold',
        spaceAfter=4
    )
    small_style = ParagraphStyle(
        'Small',
        parent=styles['Normal'],
        fontSize=8,
        textColor=DARK_GRAY
    )
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
    summary_header_style = ParagraphStyle(
        'SummaryHeader',
        fontSize=7,
        fontName='Helvetica-Bold',
        textColor=WHITE,
        alignment=TA_CENTER
    )

    # --- Header ---
    today = date.today().strftime("%B %d, %Y")
    timeframe_start = date.today().replace(year=date.today().year - 1).strftime("%b-%d-%Y")
    timeframe_end = date.today().strftime("%b-%d-%Y")

    header_data = [
        [
            Paragraph('<b>ASPIRE</b>', ParagraphStyle(
                'Logo', fontSize=18, textColor=DARK_BLUE, fontName='Helvetica-Bold'
            )),
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

    story.append(HRFlowable(width="100%", thickness=2, color=DARK_BLUE))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f'Timeframe: {timeframe_start} to {timeframe_end}', small_style))
    story.append(Spacer(1, 12))

    # --- Build rows first (needed for summary) ---
    rows = build_portfolio_rows(portfolio, allocations)
    asset_summary = build_asset_class_summary(rows)

    # --- Asset Class Summary Table ---
    story.append(Paragraph('Portfolio Allocation Summary', subtitle_style))
    story.append(Spacer(1, 4))

    # Split summary into two columns for compact display
    summary_data = [[
        Paragraph('Asset Class', summary_header_style),
        Paragraph('Allocation %', summary_header_style),
        Paragraph('Amount ($)', summary_header_style),
        Paragraph('Asset Class', summary_header_style),
        Paragraph('Allocation %', summary_header_style),
        Paragraph('Amount ($)', summary_header_style),
    ]]

    # Fill two columns
    half = (len(asset_summary) + 1) // 2
    left_col = asset_summary[:half]
    right_col = asset_summary[half:]

    for i in range(half):
        left_name, left_pct = left_col[i]
        left_amt = investment_amount * (left_pct / 100)

        if i < len(right_col):
            right_name, right_pct = right_col[i]
            right_amt = investment_amount * (right_pct / 100)
            row = [
                Paragraph(left_name, cell_style),
                Paragraph(f'{left_pct}%', center_cell_style),
                Paragraph(f'${left_amt:,.2f}', center_cell_style),
                Paragraph(right_name, cell_style),
                Paragraph(f'{right_pct}%', center_cell_style),
                Paragraph(f'${right_amt:,.2f}', center_cell_style),
            ]
        else:
            row = [
                Paragraph(left_name, cell_style),
                Paragraph(f'{left_pct}%', center_cell_style),
                Paragraph(f'${left_amt:,.2f}', center_cell_style),
                Paragraph('', cell_style),
                Paragraph('', center_cell_style),
                Paragraph('', center_cell_style),
            ]
        summary_data.append(row)

    summary_table = Table(
        summary_data,
        colWidths=[1.8*inch, 0.8*inch, 0.9*inch, 1.8*inch, 0.8*inch, 0.9*inch]
    )
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#CCCCCC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Divider between left and right columns
        ('LINEAFTER', (2, 0), (2, -1), 1.5, DARK_BLUE),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 12))

    # --- Holdings Table ---
    story.append(Paragraph('Holdings', subtitle_style))
    story.append(Spacer(1, 4))

    col_headers = [
        'Symbol', 'Allocation\n%', 'Volatility', 'Name',
        'Asset Class', 'Expense\nRatio', 'Yield', '1 YR Total\nReturn'
    ]
    col_widths = [
        0.55*inch, 0.75*inch, 0.55*inch, 1.8*inch,
        1.3*inch, 0.75*inch, 0.55*inch, 0.75*inch
    ]

    table_data = [[Paragraph(h, header_cell_style) for h in col_headers]]

    for fund, alloc_pct, allocation_name in rows:
        ticker = fund.ticker or 'N/A'
        name = fund.name or 'N/A'
        asset_class = fund.morningstar_cat or 'N/A'
        expense = f"{fund.expense_ratio:.2f}%" if fund.expense_ratio else '0.00%'
        volatility = f"{fund.std3yr:.2f}" if hasattr(fund, 'std3yr') and fund.std3yr else 'N/A'

        # Yield: show 0.00% if missing
        if hasattr(fund, 'yield_val') and fund.yield_val:
            yield_display = f"{fund.yield_val:.2f}%"
        else:
            yield_display = '0.00%'

        # Total return
        total_return = f"{fund.return_1yr * 100:.2f}%" if fund.return_1yr else '0.00%'

        row = [
            Paragraph(ticker, center_cell_style),
            Paragraph(f'{alloc_pct}%', center_cell_style),
            Paragraph(str(volatility), center_cell_style),
            Paragraph(name, cell_style),
            Paragraph(asset_class, cell_style),
            Paragraph(expense, center_cell_style),
            Paragraph(yield_display, center_cell_style),
            Paragraph(total_return, center_cell_style),
        ]
        table_data.append(row)

    # Total row
    total_pct = sum(pct for _, pct, _ in rows)
    total_volatility = sum(vol for _, vol, _ in rows)
    total_expense = sum(exp for _, exp, _ in rows)
    total_yield = sum(yield_val for _, yield_val, _ in rows)
    total_return = sum(ret for _, ret, _ in rows)
    table_data.append([
        Paragraph('<b>Total:</b>', center_cell_style),
        Paragraph(f'<b>{total_pct}%</b>', center_cell_style),
        Paragraph(f'<b>{total_volatility}</b>', center_cell_style),
        Paragraph('', cell_style),
        Paragraph('', cell_style),
        Paragraph(f'<b>{total_expense}</b>', center_cell_style),
        Paragraph(f'<b>{total_yield}</b>', center_cell_style),
        Paragraph(f'<b>{total_return}</b>', center_cell_style),
    ])

    holdings_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    holdings_table.setStyle(TableStyle([
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
        ('BACKGROUND', (0, -1), (-1, -1), LIGHT_BLUE),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, DARK_BLUE),
    ]))
    story.append(holdings_table)

    # --- Footer ---
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