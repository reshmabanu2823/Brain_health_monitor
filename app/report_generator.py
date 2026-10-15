"""Generate a research model report without invented clinical endorsements."""
import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as ReportImage


def generate_pdf_report(patient_id, patient_name, filename, label, confidence, probabilities, tumor_metrics, original_pil, heatmap_pil=None, notes=''):
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    def paragraph(text):
        return Paragraph(escape(str(text)), styles['BodyText'])
    story = [Paragraph('Brain Health Monitor — Model Analysis', styles['Title']), paragraph('Research/demo classifier output. This report is not a certified clinical diagnosis.'), Spacer(1, 12)]
    for key, value in [('Generated (UTC)', datetime.now(timezone.utc).isoformat(timespec='seconds')), ('Subject ID', patient_id), ('Subject name', patient_name), ('Source', filename), ('Predicted class', label), ('Model confidence', f'{confidence:.1f}%')]:
        story.append(paragraph(f'{key}: {value}'))
    story.append(Spacer(1, 12))
    images = []
    buffers = []
    for image in (original_pil, heatmap_pil):
        if image is None:
            images.append(paragraph('Grad-CAM unavailable for this prediction.'))
        else:
            image_buffer = io.BytesIO()
            image.convert('RGB').save(image_buffer, 'JPEG')
            image_buffer.seek(0)
            buffers.append(image_buffer)
            images.append(ReportImage(image_buffer, width=230, height=230))
    story.append(Table([images], colWidths=[250, 250]))
    story.append(paragraph('Original image (left); classifier Grad-CAM when available (right).'))
    story.append(Spacer(1, 12))
    rows = [[paragraph('Class'), paragraph('Probability')]]
    rows.extend([paragraph(name), paragraph(f'{value:.2f}%')] for name, value in probabilities.items())
    table = Table(rows, colWidths=[300, 200])
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')), ('GRID', (0, 0), (-1, -1), .5, colors.grey)]))
    story.append(table)
    if tumor_metrics and heatmap_pil is not None:
        story.append(Spacer(1, 12))
        story.append(paragraph(f"Saliency coverage: {tumor_metrics.get('tumor_area_pct', 0)}%; peak activation: {tumor_metrics.get('peak_saliency', 0)}"))
        story.append(paragraph('Saliency coordinates refer to a 224 × 224 model image. Coverage is not measured tumor area or lesion segmentation.'))
    story.append(Spacer(1, 12))
    story.append(paragraph('Class probabilities do not establish clinical severity, tumor grade, or absence of disease.'))
    if notes:
        story.append(paragraph('Notes: ' + notes))
    SimpleDocTemplate(buffer, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36).build(story)
    return buffer.getvalue()
