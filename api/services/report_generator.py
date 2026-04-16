import logging
import io
from datetime import datetime
from fpdf import FPDF
from api.models.job import CrawlJob
from api.models.issue import Issue

logger = logging.getLogger(__name__)

# Standard Professional Colors
COLOR_CRITICAL = (220, 38, 38)
COLOR_WARNING = (217, 119, 6)
COLOR_INFO = (37, 99, 235)
COLOR_GRAY_800 = (31, 41, 55)
COLOR_GRAY_600 = (75, 85, 99)
COLOR_GRAY_500 = (107, 114, 128)
COLOR_GRAY_100 = (243, 244, 246)
COLOR_TOAD_GREEN = (22, 163, 74)
COLOR_BLUE_BG = (239, 246, 255) # Light blue help box
COLOR_BLUE_TEXT = (30, 58, 138) # Dark blue help labels

# Constants for 8.5 x 11 (Letter) in mm
# Width: 215.9mm
# Left/Right Margin: 25.4mm
# Effective Width: 165.1mm
W = 165.1 

class TalkingToadReport(FPDF):
    def __init__(self):
        # 8.5 x 11 inches (Letter size)
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.set_margins(25.4, 25.4, 25.4) 
        self.set_auto_page_break(auto=True, margin=25.4)

    def clean_text(self, text):
        if not text: return ""
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    def header(self):
        if self.page_no() > 1:
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(*COLOR_GRAY_500)
            date_str = datetime.now().strftime("%Y-%m-%d")
            self.set_x(25.4)
            self.cell(W, 10, self.clean_text(f'TalkingToad SEO Audit - {date_str}'), align='R', new_x="LMARGIN", new_y="NEXT")

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(*COLOR_GRAY_500)
        self.set_x(25.4)
        self.cell(W, 10, self.clean_text(f'Page {self.page_no()}/{{nb}}'), align='C')

    def chapter_title(self, title, size=18):
        self.set_x(25.4)
        self.ln(5)
        self.set_font('helvetica', 'B', size)
        self.set_text_color(*COLOR_GRAY_800)
        self.multi_cell(W, 10, self.clean_text(title))
        self.ln(2)

    def draw_help_box(self, what, impact, how):
        self.set_x(25.4)
        if self.get_y() > 200:
            self.add_page()

        self.set_fill_color(*COLOR_BLUE_BG)
        
        for label, content in [("WHAT IT IS", what), ("IMPACT", impact), ("HOW TO FIX", how)]:
            self.set_x(25.4)
            self.set_font('helvetica', 'B', 9)
            self.set_text_color(*COLOR_BLUE_TEXT)
            
            full_text = f"{label} - {content}"
            self.multi_cell(W, 6, self.clean_text(full_text), fill=True)
            self.ln(0.5)
        
        self.ln(2)

async def generate_pdf_report(
    job: CrawlJob,
    issues: list[Issue],
    summary: dict,
    include_help: bool = True,
    include_pages: bool = True,
    top_pages: list[dict] = None,
    image_summary: dict = None,
    top_images: list = None,
) -> bytes:
    pdf = TalkingToadReport()
    pdf.alias_nb_pages()
    
    # ── Page 1: Title ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_y(80)
    pdf.set_font('helvetica', 'B', 48)
    pdf.set_text_color(*COLOR_TOAD_GREEN)
    pdf.set_x(25.4)
    pdf.cell(W, 25, "TalkingToad", align='C', new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font('helvetica', 'B', 24)
    pdf.set_text_color(*COLOR_GRAY_800)
    pdf.set_x(25.4)
    pdf.cell(W, 15, "SEO Audit Report", align='C', new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(30)
    pdf.set_font('helvetica', '', 14)
    pdf.set_text_color(*COLOR_GRAY_500)
    pdf.set_x(25.4)
    
    # Use custom names if provided, fallback to URL
    prepared_for = job.settings.client_name if job.settings and job.settings.client_name else job.target_url
    pdf.multi_cell(W, 10, f"Prepared for: {pdf.clean_text(prepared_for)}", align='C')
    
    if job.settings and job.settings.prepared_by:
        pdf.set_x(25.4)
        pdf.cell(W, 10, f"Prepared by: {pdf.clean_text(job.settings.prepared_by)}", align='C', new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(25.4)
    pdf.cell(W, 10, f"Generated on: {datetime.now().strftime('%B %d, %Y')}", align='C', new_x="LMARGIN", new_y="NEXT")
    
    # ── Page 2: Dashboard Summary ─────────────────────────────────────────
    pdf.add_page()
    pdf.chapter_title("Dashboard Summary")
    
    stats = [
        ("Health Score", summary.get("health_score", 0), COLOR_TOAD_GREEN),
        ("Pages Crawled", summary.get("pages_crawled", 0), COLOR_GRAY_800),
        ("Total Issues Found", summary.get("total_issues", 0), COLOR_GRAY_800),
        ("Critical Issues", summary.get("by_severity", {}).get("critical", 0), COLOR_CRITICAL),
        ("Warnings", summary.get("by_severity", {}).get("warning", 0), COLOR_WARNING),
        ("Info Notices", summary.get("by_severity", {}).get("info", 0), COLOR_INFO),
    ]
    
    for label, val, color in stats:
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(*COLOR_GRAY_500)
        pdf.cell(60, 10, pdf.clean_text(label + ":"))
        pdf.set_font('helvetica', 'B', 14)
        pdf.set_text_color(*color)
        pdf.cell(W - 60, 10, str(val), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)
    pdf.set_x(25.4)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(*COLOR_GRAY_800)
    pdf.cell(W, 10, "Issues by Category", new_x="LMARGIN", new_y="NEXT")
    
    cat_list = [
        ("Broken Links", "broken_link"), ("Metadata", "metadata"),
        ("Headings", "heading"), ("Redirects", "redirect"),
        ("Crawlability", "crawlability"), ("Duplicates", "duplicate"),
        ("Sitemap", "sitemap"), ("Security", "security"),
        ("URL Structure", "url_structure"), ("Images", "image"),
        ("AI Readiness", "ai_readiness"),
    ]
    
    for label, key in cat_list:
        count = summary.get("by_category", {}).get(key, 0)
        pdf.set_x(25.4)
        pdf.set_font('helvetica', '', 11)
        pdf.set_text_color(*COLOR_GRAY_600)
        pdf.cell(60, 8, pdf.clean_text(label + ":"))
        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.cell(W - 60, 8, str(count), new_x="LMARGIN", new_y="NEXT")

    # ── Page 3: Top 10 Pages ──────────────────────────────────────────────
    if top_pages:
        pdf.add_page()
        pdf.chapter_title("Top 10 Pages to Fix First")
        pdf.set_font('helvetica', '', 10)
        pdf.set_text_color(*COLOR_GRAY_600)
        pdf.set_x(25.4)
        pdf.multi_cell(W, 5, "These pages have the highest concentration of issues and should be prioritized.")
        pdf.ln(5)
        
        for p in top_pages:
            url = p.get("url", "")
            counts = p.get("issue_counts", {})
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 10)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.multi_cell(W, 6, pdf.clean_text(url))
            
            pdf.multi_cell(W, 5, f"Issues: {counts.get('critical')} Critical, {counts.get('warning')} Warnings, {counts.get('info')} Info")
            pdf.ln(2)

    # ── Page 4: AI Readiness (llms.txt) ───────────────────────────────────
    pdf.add_page()
    pdf.chapter_title("AI Readiness: llms.txt Status")
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.set_x(25.4)
    pdf.multi_cell(W, 5, "An llms.txt file is a machine-readable index that helps AI agents (like Gemini and ChatGPT) navigate your most important content.")
    pdf.ln(5)

    # 1. Existing file status
    pdf.set_x(25.4)
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(*COLOR_GRAY_800)
    pdf.cell(W, 8, "Status of live /llms.txt file:", new_x="LMARGIN", new_y="NEXT")
    
    existing_issue = next((i for i in issues if i.issue_code == "LLMS_TXT_MISSING"), None)
    pdf.set_x(25.4)
    if existing_issue:
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(*COLOR_CRITICAL)
        pdf.cell(W, 8, "MISSING - No /llms.txt file was detected during the crawl.", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(*COLOR_TOAD_GREEN)
        pdf.cell(W, 8, "FOUND - A file exists at your root domain.", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # 2. Proposed content
    pdf.set_x(25.4)
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(*COLOR_GRAY_800)
    pdf.cell(W, 8, "Proposed /llms.txt content (Machine-readable):", new_x="LMARGIN", new_y="NEXT")
    
    proposed_content = job.llms_txt_custom or "No proposed content has been saved yet. Use the TalkingToad dashboard to generate and save your optimized llms.txt file."
    
    pdf.set_x(25.4)
    pdf.set_fill_color(*COLOR_GRAY_100)
    pdf.set_font('courier', '', 8)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(W, 4, pdf.clean_text(proposed_content), fill=True, border=1)
    
    pdf.ln(10)

    # ── Image Health Summary ──────────────────────────────────────────────
    if image_summary and image_summary.get("total_images", 0) > 0:
        pdf.add_page()
        pdf.chapter_title("Image Health Summary")
        pdf.set_font('helvetica', '', 10)
        pdf.set_text_color(*COLOR_GRAY_600)
        pdf.set_x(25.4)
        pdf.multi_cell(W, 5, "Analysis of all images found during the crawl, including accessibility, performance, and optimization metrics.")
        pdf.ln(5)

        # Image stats
        img_stats = [
            ("Image Health Score", f"{image_summary.get('image_health_score', 0)}%",
             COLOR_TOAD_GREEN if image_summary.get('image_health_score', 0) >= 80 else
             COLOR_WARNING if image_summary.get('image_health_score', 0) >= 60 else COLOR_CRITICAL),
            ("Total Images", str(image_summary.get('total_images', 0)), COLOR_GRAY_800),
            ("Total Size", f"{image_summary.get('total_size_kb', 0)} KB", COLOR_GRAY_800),
            ("Avg Load Time", f"{image_summary.get('avg_load_time_ms', 0)}ms",
             COLOR_WARNING if image_summary.get('avg_load_time_ms', 0) > 500 else COLOR_GRAY_800),
        ]

        for label, val, color in img_stats:
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(*COLOR_GRAY_500)
            pdf.cell(60, 10, pdf.clean_text(label + ":"))
            pdf.set_font('helvetica', 'B', 14)
            pdf.set_text_color(*color)
            pdf.cell(W - 60, 10, val, new_x="LMARGIN", new_y="NEXT")

        # Format breakdown
        by_format = image_summary.get("by_format", {})
        if by_format:
            pdf.ln(5)
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.cell(W, 8, "Images by Format:", new_x="LMARGIN", new_y="NEXT")

            for fmt, count in sorted(by_format.items(), key=lambda x: -x[1]):
                pdf.set_x(25.4)
                pdf.set_font('helvetica', '', 11)
                pdf.set_text_color(*COLOR_GRAY_600)
                pdf.cell(60, 8, pdf.clean_text(fmt.upper() + ":"))
                pdf.set_font('helvetica', 'B', 11)
                pdf.set_text_color(*COLOR_GRAY_800)
                pdf.cell(W - 60, 8, str(count), new_x="LMARGIN", new_y="NEXT")

        # Top issue counts
        by_issue = image_summary.get("by_issue", {})
        if by_issue:
            pdf.ln(5)
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.cell(W, 8, "Top Image Issues:", new_x="LMARGIN", new_y="NEXT")

            for code, count in sorted(by_issue.items(), key=lambda x: -x[1])[:8]:
                pdf.set_x(25.4)
                pdf.set_font('helvetica', '', 11)
                pdf.set_text_color(*COLOR_GRAY_600)
                display_code = code.replace('IMG_', '').replace('_', ' ').title()
                pdf.cell(80, 8, pdf.clean_text(display_code + ":"))
                pdf.set_font('helvetica', 'B', 11)
                pdf.set_text_color(*COLOR_GRAY_800)
                pdf.cell(W - 80, 8, f"{count} image{'s' if count != 1 else ''}", new_x="LMARGIN", new_y="NEXT")

        # Top problematic images
        if top_images and len(top_images) > 0:
            pdf.ln(5)
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.cell(W, 8, "Images Needing Attention:", new_x="LMARGIN", new_y="NEXT")

            for img in top_images[:10]:
                if pdf.get_y() > 230:
                    pdf.add_page()

                score = img.overall_score if hasattr(img, 'overall_score') else img.get('overall_score', 0)
                filename = img.filename if hasattr(img, 'filename') else img.get('filename', 'Unknown')
                issues_list = img.issues if hasattr(img, 'issues') else img.get('issues', [])

                score_color = COLOR_TOAD_GREEN if score >= 80 else COLOR_WARNING if score >= 60 else COLOR_CRITICAL

                pdf.set_x(25.4)
                pdf.set_font('helvetica', 'B', 10)
                pdf.set_text_color(*score_color)
                pdf.cell(15, 6, str(round(score)))
                pdf.set_text_color(*COLOR_GRAY_800)
                pdf.cell(W - 15, 6, pdf.clean_text(filename[:60]), new_x="LMARGIN", new_y="NEXT")

                if issues_list:
                    pdf.set_x(40)
                    pdf.set_font('helvetica', '', 9)
                    pdf.set_text_color(*COLOR_GRAY_500)
                    issue_text = ", ".join([c.replace('IMG_', '') for c in issues_list[:4]])
                    if len(issues_list) > 4:
                        issue_text += f" +{len(issues_list) - 4} more"
                    pdf.cell(W - 15, 5, pdf.clean_text(issue_text), new_x="LMARGIN", new_y="NEXT")

    # ── Detailed Issues by Category ──────────────────────────────────────
    from collections import defaultdict
    groups = defaultdict(lambda: defaultdict(list))
    for i in issues:
        groups[i.category][i.issue_code].append(i)
        
    for cat_slug in sorted(groups.keys()):
        pdf.add_page()
        pdf.chapter_title(cat_slug.replace('_', ' ').title() + " Details", size=22)
        
        for code in sorted(groups[cat_slug].keys()):
            if pdf.get_y() > 220:
                pdf.add_page()
                
            examples = groups[cat_slug][code]
            first = examples[0]
            
            # Subcategory Name - SEVERITY
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 14)
            pdf.set_text_color(*COLOR_GRAY_800)
            
            title_line = f"{first.human_description or code} - {first.severity.upper()}"
            pdf.multi_cell(W, 10, pdf.clean_text(title_line))
            
            pdf.ln(1)
            
            if include_help:
                what = first.what_it_is or first.description
                impact = first.impact_desc or f"This issue has an impact score of {first.impact}/10."
                how = first.how_to_fix or first.recommendation
                pdf.draw_help_box(what, impact, how)
            
            if include_pages:
                pdf.set_x(25.4)
                pdf.set_font('helvetica', 'B', 10)
                pdf.set_text_color(*COLOR_GRAY_600)
                urls = sorted(list(set([str(i.page_url) for i in examples if i.page_url])))
                pdf.cell(W, 8, f"Affected URLs ({len(urls)}):", new_x="LMARGIN", new_y="NEXT")
                
                pdf.set_font('helvetica', '', 9)
                pdf.set_text_color(*COLOR_GRAY_800)
                for url in urls[:20]:
                    pdf.set_x(30) # Further indent URLs
                    pdf.multi_cell(W - 5, 5, pdf.clean_text(f"- {url}"))
                
                if len(urls) > 20:
                    pdf.set_x(30)
                    pdf.set_font('helvetica', 'I', 9)
                    pdf.cell(W - 5, 6, f"... and {len(urls)-20} more. See spreadsheet for full list.", new_x="LMARGIN", new_y="NEXT")
                
                pdf.ln(5)
                pdf.set_draw_color(229, 231, 235)
                pdf.set_x(25.4)
                pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + W, pdf.get_y())
                pdf.ln(5)

    pdf.set_x(25.4)
    pdf.ln(10)
    pdf.set_font('helvetica', 'I', 8)
    pdf.set_text_color(156, 163, 175)
    pdf.multi_cell(W, 4, "Disclaimer: TalkingToad is an automated tool. Please verify critical findings manually.")
    
    return pdf.output()
