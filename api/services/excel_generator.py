import io
import logging
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from api.models.job import CrawlJob
from api.models.issue import Issue

logger = logging.getLogger(__name__)

def generate_excel_report(
    job: CrawlJob,
    issues: list[Issue],
    summary: dict,
    image_summary: dict = None,
    images: list = None,
) -> bytes:
    """Generate a multi-sheet Excel workbook from crawl data."""
    wb = Workbook()
    
    # ── Summary Sheet ──────────────────────────────────────────────────────
    ws_summary = wb.active
    ws_summary.title = "Summary"
    
    # Styling
    header_font = Font(bold=True, size=14)
    label_font = Font(bold=True)
    
    ws_summary["A1"] = "TalkingToad SEO Audit"
    ws_summary["A1"].font = header_font
    
    ws_summary["A3"] = "Target URL:"
    ws_summary["B3"] = job.target_url
    ws_summary["A3"].font = label_font
    
    ws_summary["A4"] = "Health Score:"
    ws_summary["B4"] = summary.get("health_score", 0)
    ws_summary["A4"].font = label_font
    
    ws_summary["A5"] = "Total Pages:"
    ws_summary["B5"] = summary.get("pages_crawled", 0)
    ws_summary["A5"].font = label_font
    
    ws_summary["A6"] = "Total Issues:"
    ws_summary["B6"] = summary.get("total_issues", 0)
    ws_summary["A6"].font = label_font

    # Category totals table
    ws_summary["A8"] = "Issues by Category"
    ws_summary["A8"].font = Font(bold=True, size=12)
    
    ws_summary.append([]) # spacer
    ws_summary.append(["Category", "Count"])
    # Bold the mini-header
    for cell in ws_summary[ws_summary.max_row]:
        cell.font = label_font
        cell.fill = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")

    for cat, count in summary.get("by_category", {}).items():
        if count > 0:
            ws_summary.append([cat.replace('_', ' ').title(), count])

    # Adjust widths
    ws_summary.column_dimensions['A'].width = 25
    ws_summary.column_dimensions['B'].width = 50

    # ── AI Readiness Sheet ────────────────────────────────────────────────
    ws_ai = wb.create_sheet(title="AI Readiness")
    ws_ai["A1"] = "AI Readiness Report"
    ws_ai["A1"].font = header_font
    
    ws_ai["A3"] = "Live /llms.txt status:"
    ws_ai["A3"].font = label_font
    
    # Check if we have LLMS_TXT_MISSING in issues
    is_missing = any(i.issue_code == "LLMS_TXT_MISSING" for i in issues)
    ws_ai["B3"] = "MISSING" if is_missing else "FOUND"
    
    ws_ai["A5"] = "Proposed /llms.txt Content:"
    ws_ai["A5"].font = label_font
    
    # Put content in a single cell, wrap it
    proposed = job.llms_txt_custom or "Not generated yet."
    ws_ai["A6"] = proposed
    ws_ai["A6"].alignment = Alignment(wrap_text=True, vertical="top")
    ws_ai.merge_cells("A6:E20") # Give it some space
    
    ws_ai.column_dimensions['A'].width = 30
    ws_ai.column_dimensions['B'].width = 50

    # ── Images Sheet ───────────────────────────────────────────────────────
    if image_summary and image_summary.get("total_images", 0) > 0:
        ws_img = wb.create_sheet(title="Images")
        ws_img["A1"] = "Image Health Report"
        ws_img["A1"].font = header_font

        ws_img["A3"] = "Image Health Score:"
        ws_img["B3"] = f"{image_summary.get('image_health_score', 0)}%"
        ws_img["A3"].font = label_font

        ws_img["A4"] = "Total Images:"
        ws_img["B4"] = image_summary.get("total_images", 0)
        ws_img["A4"].font = label_font

        ws_img["A5"] = "Total Size:"
        ws_img["B5"] = f"{image_summary.get('total_size_kb', 0)} KB"
        ws_img["A5"].font = label_font

        ws_img["A6"] = "Avg Load Time:"
        ws_img["B6"] = f"{image_summary.get('avg_load_time_ms', 0)}ms"
        ws_img["A6"].font = label_font

        # Format breakdown
        ws_img["A8"] = "Images by Format"
        ws_img["A8"].font = Font(bold=True, size=12)
        row_num = 9
        for fmt, count in sorted(image_summary.get("by_format", {}).items(), key=lambda x: -x[1]):
            ws_img[f"A{row_num}"] = fmt.upper()
            ws_img[f"B{row_num}"] = count
            row_num += 1

        # Top issues
        row_num += 1
        ws_img[f"A{row_num}"] = "Top Image Issues"
        ws_img[f"A{row_num}"].font = Font(bold=True, size=12)
        row_num += 1
        for code, count in sorted(image_summary.get("by_issue", {}).items(), key=lambda x: -x[1])[:10]:
            ws_img[f"A{row_num}"] = code.replace('IMG_', '').replace('_', ' ').title()
            ws_img[f"B{row_num}"] = count
            row_num += 1

        ws_img.column_dimensions['A'].width = 30
        ws_img.column_dimensions['B'].width = 20

        # Image details sheet
        if images and len(images) > 0:
            ws_img_list = wb.create_sheet(title="Image Details")
            img_headers = ["Score", "Filename", "URL", "Alt Text", "Size (KB)", "Dimensions", "Format", "Load Time (ms)", "Issues"]
            ws_img_list.append(img_headers)

            for cell in ws_img_list[1]:
                cell.font = label_font
                cell.fill = PatternFill(start_color="E5E7EB", end_color="E5E7EB", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")

            for img in images:
                # Normalize to dict if ImageInfo object
                d = img.to_dict() if hasattr(img, 'to_dict') else img if isinstance(img, dict) else {}
                score = d.get('overall_score', 0)
                filename = d.get('filename', '')
                url = d.get('url', '')
                alt = d.get('alt', '')
                size_bytes = d.get('file_size_bytes')
                size_kb = round(size_bytes / 1024, 1) if size_bytes else 0
                width = d.get('width', 0)
                height = d.get('height', 0)
                fmt = d.get('format', '')
                load_time = d.get('load_time_ms', 0)
                issues_list = d.get('issues', [])

                dimensions = f"{width}x{height}" if width and height else ""
                issues_str = ", ".join(issues_list) if issues_list else ""

                ws_img_list.append([
                    round(score) if score else 0,
                    filename or "",
                    url or "",
                    alt or "",
                    size_kb or 0,
                    dimensions,
                    (fmt or "").upper(),
                    load_time or 0,
                    issues_str
                ])

            ws_img_list.column_dimensions['A'].width = 8
            ws_img_list.column_dimensions['B'].width = 30
            ws_img_list.column_dimensions['C'].width = 60
            ws_img_list.column_dimensions['D'].width = 40
            ws_img_list.column_dimensions['E'].width = 12
            ws_img_list.column_dimensions['F'].width = 15
            ws_img_list.column_dimensions['G'].width = 10
            ws_img_list.column_dimensions['H'].width = 15
            ws_img_list.column_dimensions['I'].width = 50

            ws_img_list.auto_filter.ref = ws_img_list.dimensions

    # ── Issue Sheets (by Category) ─────────────────────────────────────────
    # Group issues by category
    from collections import defaultdict
    by_cat = defaultdict(list)
    for i in issues:
        by_cat[i.category].append(i)

    header_fill = PatternFill(start_color="E5E7EB", end_color="E5E7EB", fill_type="solid")
    
    # Sort categories for consistent tab order
    sorted_cats = sorted(by_cat.keys())
    
    for cat in sorted_cats:
        # Excel titles must be < 31 chars
        sheet_name = cat.replace('_', ' ').title()[:30]
        ws = wb.create_sheet(title=sheet_name)
        
        headers = ["Severity", "URL", "Issue Code", "Description", "Recommendation"]
        ws.append(headers)
        
        # Style headers
        for cell in ws[1]:
            cell.font = label_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        for issue in by_cat[cat]:
            ws.append([
                issue.severity.upper(),
                issue.page_url or "Site-wide",
                issue.issue_code,
                issue.description,
                issue.recommendation
            ])

        # Formatting
        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 60
        ws.column_dimensions['C'].width = 25
        ws.column_dimensions['D'].width = 60
        ws.column_dimensions['E'].width = 60
        
        # Add auto-filter
        ws.auto_filter.ref = ws.dimensions

    # ── Output ─────────────────────────────────────────────────────────────
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
