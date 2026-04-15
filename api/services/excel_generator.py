import io
import logging
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from api.models.job import CrawlJob
from api.models.issue import Issue

logger = logging.getLogger(__name__)

def generate_excel_report(job: CrawlJob, issues: list[Issue], summary: dict) -> bytes:
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
