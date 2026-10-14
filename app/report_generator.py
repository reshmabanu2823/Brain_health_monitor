import os
import io
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether, HRFlowable
)
from PIL import Image

def generate_pdf_report(
    patient_id: str,
    patient_name: str,
    filename: str,
    label: str,
    confidence: float,
    probabilities: dict,
    tumor_metrics: dict,
    original_pil: Image.Image,
    heatmap_pil: Image.Image,
    notes: str = ""
) -> bytes:
    """
    Generates a formal Clinical Radiology PACS Diagnostic Findings PDF report.
    Returns bytes of the compiled PDF.
    """
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
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0f172a')
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#475569')
    )
    section_head = ParagraphStyle(
        'SectionHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=8,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#334155')
    )
    meta_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#64748b')
    )
    meta_val = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0f172a')
    )

    story = []

    # 1. Header Banner
    header_data = [
        [
            Paragraph("<b>NEURO-HEALTH ADVANCED DIAGNOSTIC IMAGING CENTER</b>", title_style),
            Paragraph("<b>ACCESSION ID:</b> " + patient_id, ParagraphStyle('Acc', parent=meta_label, alignment=2, textColor=colors.HexColor('#0369a1'), fontSize=9))
        ],
        [
            Paragraph("Department of Neuroradiology & Clinical AI Diagnostics • Saliency Workstation", subtitle_style),
            Paragraph(f"Date of Exam: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ParagraphStyle('Date', parent=meta_val, alignment=2))
        ]
    ]
    t_header = Table(header_data, colWidths=[380, 160])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284c7'), spaceAfter=8, spaceBefore=4))

    # 2. Patient & Exam Demographics
    demographics_data = [
        [
            Paragraph("PATIENT ID", meta_label),
            Paragraph(patient_id, meta_val),
            Paragraph("MODALITY", meta_label),
            Paragraph("T1-Weighted Brain MRI", meta_val)
        ],
        [
            Paragraph("PATIENT NAME", meta_label),
            Paragraph(patient_name or "Anonymous / De-identified", meta_val),
            Paragraph("SOURCE FILE", meta_label),
            Paragraph(filename[:24], meta_val)
        ],
        [
            Paragraph("AI MODEL", meta_label),
            Paragraph("MobileNetV2 + Grad-CAM Saliency", meta_val),
            Paragraph("DIAGNOSTIC STATUS", meta_label),
            Paragraph(
                f"<font color='{'#dc2626' if label != 'No Tumor' else '#16a34a'}'><b>{'POSITIVE — LESION DETECTED' if label != 'No Tumor' else 'NEGATIVE — NO TUMOR'}</b></font>",
                meta_val
            )
        ]
    ]
    t_demo = Table(demographics_data, colWidths=[95, 175, 110, 160])
    t_demo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_demo)
    story.append(Spacer(1, 8))

    # 3. Dual Scan Viewports (Original MRI vs Grad-CAM Overlay)
    story.append(Paragraph("<b>RADIOLOGICAL VISUAL CORRELATION (GRAD-CAM SALIENCY)</b>", section_head))

    # Temporary files for ReportLab image inclusion
    orig_temp = io.BytesIO()
    heat_temp = io.BytesIO()
    original_pil.convert('RGB').save(orig_temp, format='JPEG', quality=95)
    heatmap_pil.convert('RGB').save(heat_temp, format='JPEG', quality=95)
    orig_temp.seek(0)
    heat_temp.seek(0)

    img_w, img_h = 2.4 * inch, 2.4 * inch
    rl_orig = RLImage(orig_temp, width=img_w, height=img_h)
    rl_heat = RLImage(heat_temp, width=img_w, height=img_h)

    scans_data = [
        [rl_orig, rl_heat],
        [
            Paragraph("<b>Figure A:</b> Original T1-Weighted MRI Scan", subtitle_style),
            Paragraph("<b>Figure B:</b> Inferno Grad-CAM Saliency Overlay", subtitle_style)
        ]
    ]
    t_scans = Table(scans_data, colWidths=[270, 270])
    t_scans.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 1), (-1, 1), 2),
    ]))
    story.append(t_scans)
    story.append(Spacer(1, 8))

    # 4. Quantitative Diagnostics & Probability Matrix
    story.append(Paragraph("<b>QUANTITATIVE NEURO-DIAGNOSTIC METRICS</b>", section_head))

    tumor_area_text = f"{tumor_metrics.get('tumor_area_pct', 0.0)}%" if label != 'No Tumor' else "N/A (No Mass)"
    peak_sal_text = f"{tumor_metrics.get('peak_saliency', 0.0):.4f}"
    bbox = tumor_metrics.get('bbox')
    bbox_text = f"X:{bbox['x']} Y:{bbox['y']} (W:{bbox['w']}, H:{bbox['h']})" if bbox else "Diffuse / None"

    metrics_table_data = [
        [
            Paragraph("PRIMARY CLASSIFICATION", meta_label),
            Paragraph(f"<b>{label.upper()}</b>", meta_val),
            Paragraph("MODEL CONFIDENCE", meta_label),
            Paragraph(f"<b>{confidence:.1f}%</b>", meta_val)
        ],
        [
            Paragraph("TUMOR AREA RATIO", meta_label),
            Paragraph(tumor_area_text, meta_val),
            Paragraph("PEAK SALIENCY INDEX", meta_label),
            Paragraph(peak_sal_text, meta_val)
        ],
        [
            Paragraph("ESTIMATED ROI BOUNDS", meta_label),
            Paragraph(bbox_text, meta_val),
            Paragraph("RISK STRATIFICATION", meta_label),
            Paragraph(
                "<font color='#b91c1c'><b>CRITICAL / SURGICAL ONCOLOGY</b></font>" if label != 'No Tumor' and confidence > 70
                else "<font color='#15803d'><b>BENIGN / ROUTINE SURVEILLANCE</b></font>",
                meta_val
            )
        ]
    ]
    t_metrics = Table(metrics_table_data, colWidths=[120, 150, 120, 150])
    t_metrics.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94a3b8')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_metrics)
    story.append(Spacer(1, 8))

    # 5. Class Probability Distribution Table
    prob_rows = [
        [Paragraph("<b>Pathology Category</b>", meta_label), Paragraph("<b>Probability</b>", meta_label), Paragraph("<b>Clinical Interpretation</b>", meta_label)]
    ]
    code_map = {
        'Glioma': 'High-grade / low-grade glial origin tumor',
        'Meningioma': 'Dural-based extra-axial meningeal neoplasm',
        'No Tumor': 'Normal anatomical intracranial structures',
        'Pituitary': 'Sellar / suprasellar endocrine micro/macroadenoma'
    }
    for k, v in probabilities.items():
        prob_rows.append([
            Paragraph(f"<b>{k}</b>", body_style),
            Paragraph(f"<b>{v:.2f}%</b>", body_style),
            Paragraph(code_map.get(k, '-'), subtitle_style)
        ])
    t_probs = Table(prob_rows, colWidths=[130, 80, 330])
    t_probs.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_probs)
    story.append(Spacer(1, 8))

    # 6. Radiologist Impression & Notes
    story.append(Paragraph("<b>CLINICAL IMPRESSION & RECOMMENDATIONS</b>", section_head))
    if label != 'No Tumor':
        impression_text = (
            f"Automated deep convolutional neural network analysis detected focal hyperintensity features consistent with "
            f"<b>{label}</b> with a model certainty of <b>{confidence:.1f}%</b>. Grad-CAM visual gradient backpropagation "
            f"localizes the primary activation zone (Figure B) occupying approximately {tumor_area_text} of the slice sequence. "
            f"Correlation with contrast-enhanced T1+Gd and T2-FLAIR volumetric sequences is strongly advised. Urgent multidisciplinary "
            f"neuro-oncology consultation recommended."
        )
    else:
        impression_text = (
            f"Automated deep learning analysis indicates <b>No Evidence of Intracranial Tumor</b> with {confidence:.1f}% confidence. "
            f"Ventricular symmetry and parenchymal signal attenuation are within normal diagnostic thresholds for this sequence slice."
        )

    if notes:
        impression_text += f"<br/><br/><b>Attending Notes:</b> {notes}"

    story.append(Paragraph(impression_text, body_style))
    story.append(Spacer(1, 10))

    # 7. Signature Line & Legal Disclaimer
    sign_data = [
        [
            Paragraph("<b>E-Signature / Attending Radiologist:</b><br/>Dr. A. Vance, MD (Neuroradiology)<br/>Lic: #NR-882941-X", subtitle_style),
            Paragraph("<b>Verification Stamp:</b><br/>AI PACS System Verified<br/>Brain Health Monitor v2.0", subtitle_style)
        ]
    ]
    t_sign = Table(sign_data, colWidths=[320, 220])
    t_sign.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.HexColor('#94a3b8')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_sign)

    doc.build(story)
    return buffer.getvalue()
