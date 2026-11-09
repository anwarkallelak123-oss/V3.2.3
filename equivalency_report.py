"""Review cover, comparison matrix, and supporting evidence for Equivalency Report."""
from collections import Counter
from io import BytesIO
from xml.sax.saxutils import escape
from branding import draw_report_logo, VARIANCE_COLORS

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from variance import VARIANCE_INTERPRETATION, VARIANCE_METHOD
from reportlab.platypus import Image, LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle


def review_table(headers, rows, column_widths, cell_style):
    def cell(value):
        return value if isinstance(value, Paragraph) else Paragraph(escape(str(value)), cell_style)

    grid = LongTable([[cell(value) for value in row] for row in [headers, *rows]],
                     colWidths=column_widths, repeatRows=1, hAlign='LEFT', splitInRow=1)
    grid.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DFEAF7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F7FA')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return grid

def variance_report(study, rows):
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=(842, 595), leftMargin=36, rightMargin=36,
                            topMargin=52, bottomMargin=36)
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle('VarianceCell', parent=styles['Normal'], fontSize=8, leading=10)
    headers = ['ET', 'Reference', 'Test', 'Parameter', 'N ref', 'N test',
               'SD ref', 'SD test', 'Statistic', 'p-value', 'Assessment', 'TOST model', 'Note']
    widths = [30, 67, 67, 67, 32, 32, 46, 46, 47, 57, 100, 47, 95]

    def display(value):
        return '—' if value is None else f'{value:.5g}' if isinstance(value, float) else value

    values = [[display(row[header]) for header in headers] for row in rows]
    styles_by_status = []
    assessment_column = headers.index('Assessment')
    for index, row in enumerate(rows, start=1):
        background, foreground = VARIANCE_COLORS[row['Assessment']]
        cell = (assessment_column, index)
        styles_by_status.append(('BACKGROUND', cell, cell, colors.HexColor(background)))
        values[index - 1][assessment_column] = Paragraph(
            f'<font color="{foreground}"><b>{escape(row["Assessment"])}</b></font>', cell_style)
    grid = review_table(headers, values, widths, cell_style)
    grid.setStyle(TableStyle(styles_by_status))
    story = [
        Paragraph('Equal variance study', styles['Title']),
        Paragraph(escape(study), styles['Heading2']),
        Spacer(1, 8),
        Paragraph(escape(VARIANCE_METHOD), styles['Normal']),
        Paragraph(escape(VARIANCE_INTERPRETATION), styles['Normal']),
        Spacer(1, 12),
        grid,
    ]
    doc.build(story, onFirstPage=draw_report_logo, onLaterPages=draw_report_logo)
    return out.getvalue()


def equivalency_report(study, review, impact, detailed, diagnostics, variance=None, *, heatmap=None):
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=(595, 842), leftMargin=42, rightMargin=42)
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10)
    widths = [36, 100, 100, 86, 70, 105]

    def table(headers, rows, column_widths):
        return review_table(headers, rows, column_widths, cell_style)

    statuses = ['Pass', 'Fail', 'Skipped', 'Missing data', 'Error', 'Pending']
    counts = Counter(row['Status'] for row in review)
    open_items = [row for row in review if row['Status'] in {'Fail', 'Missing data', 'Error', 'Pending'}]
    def heading(value):
        return Paragraph(value, styles['Heading2'])

    story = [
        Paragraph('Equivalency Report', styles['Title']),
        Spacer(1, 12), heading(escape(study)),
        Spacer(1, 20), heading('Review summary'),
        table(statuses, [[counts[status] for status in statuses]], [82] * 6),
        Spacer(1, 12),
        Paragraph(f'{len(open_items)} rows require review. Skipped rows are documented in the comparison matrix.', styles['Normal']),
        Paragraph(f"Completed equivalence decisions: {counts['Pass'] + counts['Fail']}.", styles['Normal']),
        Spacer(1, 8),
        Paragraph('Method: pooled or Welch two-sample TOST with a 90% confidence interval and alpha = 0.05.', styles['Normal']),
        Spacer(1, 8),
        Paragraph('Review the approved criteria, assumptions, and open items before controlled use.', styles['Normal']),
        PageBreak(), heading('Equipment comparison matrix'),
        table(['Pair', 'Reference', 'Test', 'Parameter', 'Status', 'Scope'], [
            [row['ET'], row['Reference'], row['Test'], row['Parameter'], row['Status'],
             f"{row['Type']} / {row['Location']}"] for row in review
        ], widths),
        Spacer(1, 14), heading('Open items and skipped comparisons'),
    ]
    actions = [row for row in review if row['Reason']]
    if actions:
        story.append(table(['Pair', 'Parameter', 'Status', 'Reason'], [
            [row['ET'], row['Parameter'], row['Status'], row['Reason']] for row in actions
        ], [40, 112, 76, 269]))
    else:
        story.append(Paragraph('No open items or skipped comparisons.', styles['Normal']))
    if impact:
        def number(value):
            return f'{value:.6g}' if value is not None else 'Unavailable'

        story += [PageBreak(), heading('Exclusion impact')]
        for row in impact:
            story += [
                heading(escape(f"{row['ET']} | {row['Parameter']} ({row['Unit']})")),
                table(['Metric', 'Before exclusion', 'After exclusion'], [
                    ['N reference / test', f"{row['N ref before']} / {row['N test before']}",
                     f"{row['N ref after']} / {row['N test after']}"],
                    *[[name, number(row[f'{name} before']), number(row[f'{name} after'])]
                      for name in ['Difference', 'CI low', 'CI high', 'EAC']],
                    ['Decision', row['Decision before'], row['Decision after']],
                ], [160, 168, 169]),
                Spacer(1, 8),
            ]
            if row.get('Baseline note'):
                story.append(Paragraph(escape(row['Baseline note']), styles['Normal']))
    if heatmap:
        chart = Image(BytesIO(heatmap))
        scale = min(495 / chart.imageWidth, 650 / chart.imageHeight)
        chart.drawWidth = chart.imageWidth * scale
        chart.drawHeight = chart.imageHeight * scale
        story.extend([PageBreak(), heading('Equivalence heatmap'), Spacer(1, 12), chart])
    doc.build(story, onFirstPage=draw_report_logo, onLaterPages=draw_report_logo)

    writer = PdfWriter()
    for title, section in [('Review summary and matrix', out.getvalue()),
                           ('Equal variance study', variance),
                           ('Detailed TOST results', detailed),
                           ('Normality and exclusion audit', diagnostics)]:
        if section:
            writer.append(PdfReader(BytesIO(section)), outline_item=title)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def combine_product_reports(reports):
    """Combine current product PDFs with a cover and separate bookmarks."""
    cover = BytesIO()
    document = SimpleDocTemplate(cover, pagesize=(595, 842))
    styles = getSampleStyleSheet()
    story = [
        Paragraph('Multi-product Equivalency Report', styles['Title']),
        Spacer(1, 12),
        Paragraph('Product sections', styles['Heading2']),
    ]
    for name, _ in reports:
        story.append(Paragraph(escape(name), styles['Normal']))
        story.append(Spacer(1, 6))
    document.build(story, onFirstPage=draw_report_logo, onLaterPages=draw_report_logo)

    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(cover.getvalue())))
    for name, report in reports:
        writer.append(PdfReader(BytesIO(report)), outline_item=name)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
