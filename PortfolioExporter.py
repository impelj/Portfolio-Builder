from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import date
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import Image

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

def build_pie_chart_image(asset_summary, width=3.8, height=4.2):
    """Generate a donut chart of asset allocation, return as ReportLab Image."""
    import math

    labels = [name for name, pct in asset_summary]
    sizes  = [pct  for _, pct  in asset_summary]

    # Match document font
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']

    chart_colors = [
    '#4472C4',  # steel blue (their dominant color)
    '#FFC000',  # golden yellow
    '#70AD47',  # medium green
    '#FF0000',  # red
    '#2E5FA3',  # darker blue variant
    '#E6A000',  # darker gold variant
    '#507E32',  # darker green variant
    '#CC0000',  # darker red variant
    '#7096D1',  # lighter blue variant
    '#FFD966',  # lighter yellow variant
    '#A9D18E',  # lighter green variant
    '#FF6666',  # lighter red variant
    ]
    fig, ax = plt.subplots(figsize=(5, 5))
    fig.patch.set_alpha(0)
    # Give breathing room on all sides for leader lines
    fig.subplots_adjust(top=1.02, bottom=0.28, left=0.15, right=0.85)

    wedges, _ = ax.pie(
        sizes,
        labels=None,
        autopct=None,       # We handle labels manually
        startangle=90,
        wedgeprops=dict(width=0.5, edgecolor='white', linewidth=1.5),
        colors=chart_colors[:len(sizes)]
    )

    # Collect large and small slices separately
    small_items = []

    for wedge, pct in zip(wedges, sizes):
        angle = (wedge.theta1 + wedge.theta2) / 2
        rad   = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        if pct >= 8:
            # Large slice: label inside the donut ring
            ax.text(
                0.75 * cos_a, 0.75 * sin_a,
                f'{pct}%',
                ha='center', va='center',
                fontsize=11, color='#003366', fontweight='bold'
            )
        else:
            small_items.append((wedge, pct, angle, rad, cos_a, sin_a))

    # Sort small slices by angle so staggering is consistent
    small_items.sort(key=lambda x: x[2])

    for i, (wedge, pct, angle, rad, cos_a, sin_a) in enumerate(small_items):
        # Spread labels angularly around their actual position to avoid overlap
        n = len(small_items)
        spread_angle = angle + (i - n / 2) * 10  # 10 degrees apart
        spread_rad   = math.radians(spread_angle)
        label_cos    = math.cos(spread_rad)
        label_sin    = math.sin(spread_rad)

        ax.annotate(
            f'{pct}%',
            xy=(0.85 * cos_a, 0.85 * sin_a),        # arrow tip at wedge edge
            xytext=(1.4 * label_cos, 1.4 * label_sin),  # spread label outward
            fontsize=10, color='#003366', fontweight='bold',
            ha='center', va='center',
            arrowprops=dict(arrowstyle='->', color='#666666', lw=0.8)
        )

    ax.legend(
        wedges,
        labels,               # just names, no percentages (already on chart)
        loc='upper center',
        bbox_to_anchor=(0.5, -0.05),
        fontsize=6,
        frameon=False,
        ncol=2,
        handleheight=0.8,
        handlelength=1.0,
    )
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor='none', edgecolor='none')
    plt.close(fig)
    buf.seek(0)

    return Image(buf, width=width*inch, height=height*inch)


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
        fontSize=11,
        textColor=DARK_GRAY,
        alignment=TA_RIGHT
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=DARK_BLUE,
        fontName='Helvetica-Bold',
        spaceAfter=4
    )
    small_style = ParagraphStyle(
        'Small',
        parent=styles['Normal'],
        fontSize=9,
        textColor=DARK_GRAY
    )
    header_cell_style = ParagraphStyle(
        'TableHeader',
        fontSize=8,
        fontName='Helvetica-Bold',
        textColor=WHITE,
        alignment=TA_CENTER
    )
    cell_style = ParagraphStyle(
        'TableCell',
        fontSize=8,
        textColor=DARK_GRAY,
        alignment=TA_LEFT
    )
    center_cell_style = ParagraphStyle(
        'CenterCell',
        fontSize=8,
        textColor=DARK_GRAY,
        alignment=TA_CENTER
    )
    summary_header_style = ParagraphStyle(
        'SummaryHeader',
        fontSize=8,
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

    # --- Pie Chart ---
    # --- Build rows first (needed for everything below) ---
    rows = build_portfolio_rows(portfolio, allocations)
    asset_summary = build_asset_class_summary(rows)

    # --- Asset Class Summary Table + Pie Chart (side by side) ---
    story.append(Paragraph('Portfolio Allocation Summary', subtitle_style))
    story.append(Spacer(1, 4))

    summary_data = [[
        Paragraph('Asset Class', summary_header_style),
        Paragraph('Allocation %', summary_header_style),
        Paragraph('Amount ($)', summary_header_style),
    ]]
    for name, pct in asset_summary:
        amt = investment_amount * (pct / 100)
        summary_data.append([
            Paragraph(name, cell_style),
            Paragraph(f'{pct}%', center_cell_style),
            Paragraph(f'${amt:,.2f}', center_cell_style),
        ])

    summary_table = Table(
        summary_data,
        colWidths=[1.9*inch, 0.65*inch, 0.95*inch]
    )
    summary_table.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1,  0), DARK_BLUE),
        ('TEXTCOLOR',      (0, 0), (-1,  0), WHITE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ('GRID',           (0, 0), (-1, -1), 0.25, colors.HexColor('#CCCCCC')),
        ('TOPPADDING',     (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 4),
        ('LEFTPADDING',    (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 4),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    pie_image = build_pie_chart_image(asset_summary)

    side_by_side = Table(
        [[summary_table, pie_image]],
        colWidths=[3.5*inch, 4.0*inch]
    )
    side_by_side.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(side_by_side)
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
    if rows and total_pct > 0:
        avg_volatility = sum(fund.std3yr * pct for fund, pct, _ in rows) / total_pct
        avg_expense = sum(fund.expense_ratio * pct for fund, pct, _ in rows) / total_pct
        avg_yield = sum(fund.yield_val * pct for fund, pct, _ in rows) / total_pct
        avg_return = sum(fund.return_1yr * 100 * pct for fund, pct, _ in rows) / total_pct
    else:
        avg_volatility = avg_expense = avg_yield = avg_return = 0
    table_data.append([
        Paragraph('<b>Total:</b>', center_cell_style),
        Paragraph(f'<b>{total_pct}%</b>', center_cell_style),
        Paragraph(f'<b>{avg_volatility:.2f}%</b>', center_cell_style),
        Paragraph('', cell_style),
        Paragraph('', cell_style),
        Paragraph(f'<b>{avg_expense:.2f}%</b>', center_cell_style),
        Paragraph(f'<b>{avg_yield:.2f}%</b>', center_cell_style),
        Paragraph(f'<b>{avg_return:.2f}%</b>', center_cell_style),
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