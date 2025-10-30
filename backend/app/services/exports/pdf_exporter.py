"""
PDF Export Service

Professional PDF generation using ReportLab with tables, charts, and branding.
Supports landscape/portrait orientation, custom headers/footers, and multi-page tables.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from io import BytesIO
import logging

from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


logger = logging.getLogger(__name__)


class PDFExporter:
    """
    Professional PDF exporter with ReportLab.

    Features:
    - Automatic table pagination across multiple pages
    - Custom headers and footers
    - Professional styling with alternating row colors
    - Support for landscape/portrait orientation
    - Metadata embedding (title, author, subject)
    """

    def __init__(
        self,
        title: str,
        orientation: str = "portrait",
        page_size: str = "letter"
    ):
        """
        Initialize PDF exporter.

        Args:
            title: Document title
            orientation: "portrait" or "landscape"
            page_size: "letter" or "A4"
        """
        self.title = title
        self.orientation = orientation
        self.page_size = self._get_page_size(page_size, orientation)

        # Initialize styles
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()

    def _get_page_size(self, size: str, orientation: str):
        """Get page size tuple"""
        base_size = letter if size.lower() == "letter" else A4

        if orientation.lower() == "landscape":
            return landscape(base_size)
        return base_size

    def _add_custom_styles(self):
        """Add custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#6b7280'),
            spaceAfter=12,
            alignment=TA_CENTER
        ))

        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceBefore=12,
            spaceAfter=6
        ))

        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#9ca3af'),
            alignment=TA_CENTER
        ))

    def export_data_table(
        self,
        data: List[Dict[str, Any]],
        columns: List[str],
        subtitle: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> BytesIO:
        """
        Export data as a PDF table.

        Args:
            data: List of dictionaries containing row data
            columns: List of column names to include
            subtitle: Optional subtitle text
            metadata: Optional metadata (author, subject, keywords)

        Returns:
            BytesIO object containing the PDF
        """
        buffer = BytesIO()

        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
            title=self.title,
            author=metadata.get('author', 'Sales Agent System') if metadata else 'Sales Agent System',
            subject=metadata.get('subject', 'Analytics Report') if metadata else 'Analytics Report'
        )

        # Build document content
        story = []

        # Add title
        story.append(Paragraph(self.title, self.styles['CustomTitle']))

        # Add subtitle if provided
        if subtitle:
            story.append(Paragraph(subtitle, self.styles['CustomSubtitle']))

        # Add metadata section
        story.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            self.styles['CustomSubtitle']
        ))
        story.append(Spacer(1, 0.3 * inch))

        # Prepare table data
        table_data = self._prepare_table_data(data, columns)

        if table_data:
            # Create table
            table = Table(table_data, repeatRows=1)

            # Apply table styling
            table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

                # Data rows
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1f2937')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),

                # Padding
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))

            story.append(table)
        else:
            story.append(Paragraph("No data available", self.styles['Normal']))

        # Add footer spacer
        story.append(Spacer(1, 0.5 * inch))

        # Add summary information
        story.append(Paragraph(
            f"Total Records: {len(data)}",
            self.styles['SectionHeader']
        ))

        # Build PDF
        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)

        buffer.seek(0)
        return buffer

    def _prepare_table_data(
        self,
        data: List[Dict[str, Any]],
        columns: List[str]
    ) -> List[List[str]]:
        """
        Prepare data for table creation.

        Args:
            data: List of dictionaries
            columns: Column names

        Returns:
            List of lists for ReportLab Table
        """
        if not data:
            return []

        # Header row (capitalize and format column names)
        headers = [self._format_column_name(col) for col in columns]
        table_data = [headers]

        # Data rows
        for row in data:
            formatted_row = []
            for col in columns:
                value = row.get(col, '')

                # Format value based on type
                if isinstance(value, (int, float)):
                    if isinstance(value, float):
                        formatted_value = f"{value:.2f}"
                    else:
                        formatted_value = str(value)
                elif isinstance(value, datetime):
                    formatted_value = value.strftime('%Y-%m-%d %H:%M')
                elif value is None:
                    formatted_value = 'N/A'
                else:
                    formatted_value = str(value)

                # Truncate long strings
                if len(formatted_value) > 100:
                    formatted_value = formatted_value[:97] + '...'

                formatted_row.append(formatted_value)

            table_data.append(formatted_row)

        return table_data

    def _format_column_name(self, column: str) -> str:
        """Format column name for display"""
        # Replace underscores with spaces and capitalize
        formatted = column.replace('_', ' ').title()
        return formatted

    def _add_page_number(self, canvas, doc):
        """
        Add page numbers to footer.

        This callback is called for each page.
        """
        page_num = canvas.getPageNumber()

        # Save state
        canvas.saveState()

        # Add page number
        footer_text = f"Page {page_num} | Sales Agent Analytics Report"
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#9ca3af'))

        # Center footer
        text_width = canvas.stringWidth(footer_text, 'Helvetica', 8)
        canvas.drawString(
            (self.page_size[0] - text_width) / 2,
            0.5 * inch,
            footer_text
        )

        # Restore state
        canvas.restoreState()

    def export_multi_table_report(
        self,
        sections: List[Dict[str, Any]],
        metadata: Optional[Dict[str, str]] = None
    ) -> BytesIO:
        """
        Export multiple tables/sections in a single PDF.

        Args:
            sections: List of section dictionaries with:
                - title: Section title
                - data: List of dictionaries
                - columns: List of column names
                - description: Optional description
            metadata: Optional metadata

        Returns:
            BytesIO object containing the PDF
        """
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
            title=self.title,
            author=metadata.get('author', 'Sales Agent System') if metadata else 'Sales Agent System',
            subject=metadata.get('subject', 'Analytics Report') if metadata else 'Analytics Report'
        )

        story = []

        # Add main title
        story.append(Paragraph(self.title, self.styles['CustomTitle']))
        story.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            self.styles['CustomSubtitle']
        ))
        story.append(Spacer(1, 0.5 * inch))

        # Add each section
        for i, section in enumerate(sections):
            # Section title
            story.append(Paragraph(section['title'], self.styles['SectionHeader']))

            # Section description if provided
            if section.get('description'):
                story.append(Paragraph(section['description'], self.styles['Normal']))
                story.append(Spacer(1, 0.1 * inch))

            # Section table
            table_data = self._prepare_table_data(section['data'], section['columns'])

            if table_data:
                table = Table(table_data, repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 1), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ]))
                story.append(table)
                story.append(Spacer(1, 0.3 * inch))
            else:
                story.append(Paragraph("No data available", self.styles['Normal']))

            # Add page break between sections (except last)
            if i < len(sections) - 1:
                story.append(PageBreak())

        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)

        buffer.seek(0)
        return buffer


# Convenience function for simple exports
def export_to_pdf(
    data: List[Dict[str, Any]],
    columns: List[str],
    title: str,
    subtitle: Optional[str] = None,
    orientation: str = "portrait"
) -> BytesIO:
    """
    Quick export function for simple PDF generation.

    Args:
        data: Data to export
        columns: Column names
        title: Document title
        subtitle: Optional subtitle
        orientation: Page orientation

    Returns:
        BytesIO containing PDF
    """
    exporter = PDFExporter(title=title, orientation=orientation)
    return exporter.export_data_table(data, columns, subtitle=subtitle)
