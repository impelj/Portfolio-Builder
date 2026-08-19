from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import date
from collections import defaultdict
import re
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

SHARE_CLASS_SUFFIXES = {
    'a', 'b', 'c', 'i', 'k', 'n', 'p', 'r', 's', 't', 'w', 'x', 'y', 'z',
    'adm', 'admiral', 'inv', 'investor', 'instl', 'institutional', 'inst',
    'retail', 'retirement', 'service', 'signal', 'direct', 'advisor',
    'r1', 'r2', 'r3', 'r4', 'r5', 'r6',
    'k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7', 'k8',
    'y1', 'y2', 'y3', 'y4', 'y5', 'y6',
    'shares', 'class',
}


def normalize_fund_family(name):
    """
    Strip trailing share-class tokens from a fund name to get a base
    "fund family" key, so share classes of the same underlying strategy
    (e.g. "Invesco Energy R6" vs "Invesco Energy R5", or "Vanguard Energy
    Adm" vs "Vanguard Energy Inv") are recognized as the same fund.

    This is a heuristic based on common share-class naming conventions,
    not a real fund-family identifier -- but it's conservative: it only
    strips tokens from a known suffix list, so genuinely different funds
    stay distinct. E.g. "Fidelity Advisor Energy - Z" strips its trailing
    "Z" to "fidelity advisor energy", while "Fidelity Select Energy
    Portfolio" has no recognized suffix to strip and stays as-is -- the
    two remain distinct rather than being merged.
    """
    if not name:
        return name

    cleaned = re.sub(r'\s*-\s*', ' ', name.strip())
    tokens = cleaned.split()

    while tokens:
        last = tokens[-1].lower().strip(',.')
        if last in SHARE_CLASS_SUFFIXES:
            tokens.pop()
        else:
            break

    base = ' '.join(tokens).strip().lower()
    return base if base else name.strip().lower()


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


def select_diversified_funds(tranche_candidates, allocation_pct, num_funds, max_sector_pct=0.20, full_candidates=None):
    """
    Greedily select up to num_funds funds, preferring funds whose category
    won't push that category's score-weighted share over max_sector_pct of
    the WHOLE portfolio (not just this bucket). Never selects two funds
    that are just different share classes of the same underlying fund
    (see normalize_fund_family) -- that constraint is hard and is never
    relaxed, unlike the sector cap which can be exceeded as a last resort.

    tranche_candidates: this option's own ranked candidate list (highest
        score first) -- tried first, so Option 1/2/3 keep giving genuinely
        different picks in the normal case.
    full_candidates: optional COMPLETE ranked list of every eligible fund
        for this bucket (not just this option's tranche). Used only as a
        fallback when tranche_candidates truly can't diversify a slot --
        e.g. every candidate in the tranche shares the same over-cap
        category. Reaching into the full pool is a last resort to break
        that specific violation, not a way to add extra diversity beyond
        what's needed.

    At each slot: try the tranche first, picking the first ranked,
    non-duplicate-family candidate that keeps its category under the cap
    (projecting the score-weighted split as if only the funds chosen so
    far, plus this candidate, were selected). If nothing in the tranche
    works, try the full pool the same way. If nothing anywhere avoids the
    cap, fall back to the next best fund regardless of category -- but
    still never a duplicate family -- since the bucket is allowed to
    exceed the sector cap rather than force in an unrelated fund just to
    fill the slot.

    Returns the selected funds in the order chosen.
    """
    if not tranche_candidates:
        return []

    def is_duplicate_family(candidate, selected):
        candidate_family = normalize_fund_family(candidate.name)
        return any(normalize_fund_family(f.name) == candidate_family for f in selected)

    def first_valid(pool, selected, enforce_cap):
        for candidate in pool:
            if is_duplicate_family(candidate, selected):
                continue

            if not enforce_cap:
                return candidate

            trial = selected + [candidate]
            total_score = sum(f.score for f in trial if f.score)

            if total_score > 0:
                cat_totals = defaultdict(float)
                for f in trial:
                    fund_pct = (f.score / total_score) * allocation_pct
                    cat_totals[f.morningstar_cat or 'Uncategorized'] += fund_pct

                candidate_cat = candidate.morningstar_cat or 'Uncategorized'
                if cat_totals[candidate_cat] <= max_sector_pct:
                    return candidate
            else:
                return candidate
        return None

    selected = []
    remaining = list(tranche_candidates)

    tranche_ids = {id(f) for f in tranche_candidates}
    fallback_pool = [f for f in (full_candidates or []) if id(f) not in tranche_ids]

    while len(selected) < num_funds and (remaining or fallback_pool):
        # 1. Try this option's own tranche first (keeps options distinct)
        chosen = first_valid(remaining, selected, enforce_cap=True)
        source_list = remaining

        # 2. Tranche can't diversify this slot -- reach into the full pool
        if chosen is None and fallback_pool:
            chosen = first_valid(fallback_pool, selected, enforce_cap=True)
            source_list = fallback_pool

        # 3. Nothing anywhere avoids the cap -- accept the cap violation,
        # but still never a duplicate family
        if chosen is None:
            chosen = first_valid(remaining, selected, enforce_cap=False)
            source_list = remaining
            if chosen is None and fallback_pool:
                chosen = first_valid(fallback_pool, selected, enforce_cap=False)
                source_list = fallback_pool

        # 4. Truly nothing left (everything remaining is a duplicate family)
        if chosen is None:
            break

        selected.append(chosen)
        source_list.remove(chosen)

    return selected


def apply_risk_prm_cap(rows, allocations, name_substring=' Risk Prm', cap_pct=0.03):
    """
    Caps any fund whose name contains `name_substring` (e.g. reinsurance
    risk premia funds like "Stone Ridge Hi Yld Reinsurance Risk Prml") at
    cap_pct of the whole portfolio (default 3%). Excess is redistributed
    proportionally to all other funds not matching the name filter.

    rows: list of (fund, pct, allocation_name) tuples, pct as a fraction (0-1).
    Returns a new list of (fund, pct, allocation_name) tuples.
    """
    rows = [list(r) for r in rows]  # mutable copies
    total_excess = 0.0

    for row in rows:
        fund = row[0]
        if name_substring in fund.name and row[1] > cap_pct:
            total_excess += row[1] - cap_pct
            row[1] = cap_pct

    if total_excess > 0:
        eligible = [row for row in rows if name_substring not in row[0].name]
        eligible_total = sum(row[1] for row in eligible)

        if eligible_total > 0:
            for row in eligible:
                row[1] += total_excess * (row[1] / eligible_total)
        # else: no eligible funds to absorb excess; portfolio will fall
        # short of 100%. Rare edge case.

    return [tuple(r) for r in rows]


FIXED_INCOME_BUCKETS = {'Short-term Fixed Income', 'Other Fixed Income'}


def apply_sector_cap(rows, max_pct=0.20, max_iterations=10, excluded_allocations=None):
    """
    Cap total portfolio exposure to any single asset class (fund.morningstar_cat)
    at max_pct of the whole portfolio. Excess weight is redistributed
    proportionally across funds outside capped categories.

    Rows whose allocation_name is in excluded_allocations are left untouched
    entirely -- they don't count toward any sector total, aren't capped, and
    never receive redistributed excess. This keeps fixed-income sleeves (which
    are legitimately meant to be concentrated, e.g. 40% Ultrashort Bond by
    design) from being dragged toward the equity-sector cap.

    Iterative because redistributing excess into other funds can push a
    second category over the cap, which then needs its own pass.

    rows: list of (fund, pct, allocation_name) tuples, pct as a fraction (0-1).
    Returns a new list of (fund, pct, allocation_name) tuples.
    """
    excluded_allocations = excluded_allocations or set()
    rows = [list(r) for r in rows]  # mutable copies
    permanently_capped = set()

    def sector_of(fund):
        return fund.morningstar_cat or 'Uncategorized'

    eligible_indices = [i for i, row in enumerate(rows) if row[2] not in excluded_allocations]

    for _ in range(max_iterations):
        sector_totals = defaultdict(float)
        for i in eligible_indices:
            fund, pct, _ = rows[i]
            sector_totals[sector_of(fund)] += pct

        over_cap = {
            s: t for s, t in sector_totals.items()
            if t > max_pct and s not in permanently_capped
        }
        if not over_cap:
            break

        total_excess = 0.0
        for sector, total in over_cap.items():
            excess = total - max_pct
            total_excess += excess
            scale = max_pct / total if total > 0 else 0
            for i in eligible_indices:
                if sector_of(rows[i][0]) == sector:
                    rows[i][1] *= scale
            permanently_capped.add(sector)

        # Redistribute excess proportionally among eligible rows not in a capped sector
        redistribute_indices = [
            i for i in eligible_indices if sector_of(rows[i][0]) not in permanently_capped
        ]
        redistribute_total = sum(rows[i][1] for i in redistribute_indices)

        if redistribute_total > 0:
            for i in redistribute_indices:
                rows[i][1] += total_excess * (rows[i][1] / redistribute_total)
        # else: nothing left to absorb the excess — portfolio will fall
        # short of 100%. Rare edge case (nearly every eligible bucket is capped).

    return [tuple(r) for r in rows]


def build_portfolio_rows(portfolio, allocations, max_sector_pct=0.20, full_ranked_funds=None):
    """
    Build fund rows with score-weighted allocations.
    Fixes the total % bug by normalizing to exactly 100%.
    Caps "Risk Prm" (reinsurance risk premia) funds at 3% of the whole
    portfolio, redistributing excess elsewhere.
    Fund selection within each bucket is diversification-aware
    (select_diversified_funds): it avoids letting a single
    fund.morningstar_cat category exceed max_sector_pct of the whole
    portfolio when better-diversified alternatives exist, rather than
    picking the naive top-N and clipping/redistributing after the fact.
    If the option's own candidate tranche can't diversify a slot,
    full_ranked_funds (the bucket's complete ranked candidate list, not
    just this option's tranche) is used as a fallback pool before
    accepting a cap violation. If no alternative exists anywhere, the
    bucket is allowed to exceed the cap.
    Rounds each fund's % using largest-remainder rounding, scoped
    independently per allocation bucket, so a bucket's total can never
    drift because of rounding elsewhere in the portfolio.
    Returns list of (fund, fund_pct, allocation_name) tuples.
    """
    full_ranked_funds = full_ranked_funds or {}
    rows = []

    for allocation_name, allocation_info in allocations.items():
        allocation_pct = allocation_info['pct']
        if allocation_pct == 0:
            continue

        funds_list = portfolio.get(allocation_name, [])
        if not funds_list:
            continue

        num_funds = get_num_funds(allocation_pct)
        selected_funds = select_diversified_funds(
            funds_list, allocation_pct, num_funds,
            max_sector_pct=max_sector_pct,
            full_candidates=full_ranked_funds.get(allocation_name)
        )

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

    # Cap reinsurance "Risk Prm" funds at 3% of the whole portfolio
    rows = apply_risk_prm_cap(rows, allocations)

    # Round each fund's % using largest-remainder rounding, applied
    # independently PER BUCKET. This guarantees every bucket's rounded
    # total exactly matches its own current sum (its Allocations.py target,
    # unless legitimately shifted by the scale-up above or by
    # apply_risk_prm_cap) -- rounding drift can never cross a bucket
    # boundary and land on an unrelated fund in a different bucket.
    bucket_indices = defaultdict(list)
    for i, (fund, pct, name) in enumerate(rows):
        bucket_indices[name].append(i)

    rounded_pct = [0] * len(rows)

    for allocation_name, indices in bucket_indices.items():
        bucket_sum = sum(rows[i][1] for i in indices) * 100
        bucket_target_int = round(bucket_sum)

        floors = [(i, int(rows[i][1] * 100), (rows[i][1] * 100) - int(rows[i][1] * 100)) for i in indices]
        floor_sum = sum(f for _, f, _ in floors)
        remainder_needed = bucket_target_int - floor_sum

        # Give the +1s to the funds with the largest fractional remainder first
        floors_sorted = sorted(floors, key=lambda x: x[2], reverse=True)
        for rank, (i, floor_val, _) in enumerate(floors_sorted):
            bump = 1 if rank < remainder_needed else 0
            rounded_pct[i] = floor_val + bump

    rounded = [(rows[i][0], rounded_pct[i], rows[i][2]) for i in range(len(rows))]

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
    '#4472C4',  # blue
    '#FFC000',  # yellow
    '#70AD47',  # green
    '#FF0000',  # red
    '#9E480E',  # burnt orange
    '#264478',  # dark navy
    '#43682B',  # dark green
    '#FF66CC',  # pink
    '#7030A0',  # purple
    '#00B0F0',  # light blue
    '#CCCCCC',  # gray
    '#FF9900',  # orange
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

        if pct >= 5:
            # Only label slices big enough to hold text
            ax.text(
                0.75 * cos_a, 0.75 * sin_a,
                f'{pct}%',
                ha='center', va='center',
                fontsize=11, color="#000000", fontname='DejaVu Sans'
            )
        # Small slices: no label, legend handles it

    # Sort small slices by angle so staggering is consistent
    small_items.sort(key=lambda x: x[2])

    for i, (wedge, pct, angle, rad, cos_a, sin_a) in enumerate(small_items):
        # Spread labels angularly around their actual position to avoid overlap
        n = len(small_items)
        spread_angle = angle + (i - n / 2) * 18  # 10 degrees apart
        spread_rad   = math.radians(spread_angle)
        label_cos    = math.cos(spread_rad)
        label_sin    = math.sin(spread_rad)

        ax.annotate(
            f'{pct}%',
            xy=(0.85 * cos_a, 0.85 * sin_a),        # arrow tip at wedge edge
            xytext=(1.35 * label_cos, 1.35 * label_sin),  # spread label outward
            fontsize=10, color='#003366', fontweight='bold',
            ha='center', va='center',
            arrowprops=dict(arrowstyle='->', color='#666666', lw=0.8)
        )

    ax.legend(
        wedges,
        labels,               # just names, no percentages (already on chart)
        loc='upper center',
        bbox_to_anchor=(0.5, -0.05),
        fontsize=9,
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
    investment_amount: float,
    option_number: int = None,
    fund_source: str = "403b Funds",
    max_sector_pct: float = 0.20,
    full_ranked_funds: dict = None
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
            Paragraph(
            f'<b>LIONHEART</b><br/><font size=14>{portfolio_name}</font>'
            f'<br/><font size=10 color="#336699">{fund_source}</font>',
                ParagraphStyle('Logo', fontSize=18, textColor=DARK_BLUE, fontName='Helvetica-Bold')
            ),
            Paragraph(
                (f'<b>OPTION {option_number}</b><br/>' if option_number else '')
                + f'Prepared For: <b>{client_name}</b><br/>'
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
    rows = build_portfolio_rows(portfolio, allocations, max_sector_pct=max_sector_pct, full_ranked_funds=full_ranked_funds)
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
        'Asset Class', 'Expense\nRatio', 'Yield', '3 YR Total\nReturn'
    ]
    col_widths = [
        0.55*inch, 0.85*inch, 0.65*inch, 1.8*inch,
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
        total_return = f"{fund.return_3yr * 100:.2f}%" if fund.return_3yr else '0.00%'

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
        avg_return = sum(fund.return_3yr * 100 * pct for fund, pct, _ in rows) / total_pct
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