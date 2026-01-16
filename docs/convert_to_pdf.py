#!/usr/bin/env python3
"""Convert Markdown technical guide to PDF."""

import markdown2
from weasyprint import HTML, CSS
from pathlib import Path

# Read the markdown file
md_path = Path(__file__).parent / "CHECK_REVIEW_CONSOLE_TECHNICAL_GUIDE.md"
md_content = md_path.read_text()

# Convert markdown to HTML using markdown2 with extras
html_content = markdown2.markdown(
    md_content,
    extras=[
        'tables',
        'fenced-code-blocks',
        'code-friendly',
        'cuddled-lists',
        'header-ids',
        'break-on-newline',
    ]
)

print(f"Markdown: {len(md_content)} chars, {md_content.count(chr(10))} lines")
print(f"HTML: {len(html_content)} chars")
print(f"H1 tags: {html_content.count('<h1')}")
print(f"H2 tags: {html_content.count('<h2')}")
print(f"H3 tags: {html_content.count('<h3')}")
print(f"Tables: {html_content.count('<table>')}")

# CSS for professional PDF styling
css = CSS(string='''
@page {
    size: letter;
    margin: 0.75in 0.75in 1in 0.75in;
    @top-center {
        content: "Check Review Console - Technical Guide";
        font-size: 8pt;
        color: #666;
        padding-top: 0.25in;
    }
    @bottom-center {
        content: "Page " counter(page);
        font-size: 8pt;
        color: #666;
    }
}

@page :first {
    @top-center { content: none; }
    @bottom-center { content: none; }
}

body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.4;
    color: #333;
}

h1 {
    color: #1a365d;
    font-size: 20pt;
    font-weight: bold;
    border-bottom: 2px solid #c9a227;
    padding-bottom: 8px;
    margin-top: 30px;
    margin-bottom: 15px;
    page-break-before: always;
}

/* First H1 should not break */
body > h1:first-child {
    page-break-before: avoid;
    text-align: center;
    font-size: 28pt;
    border-bottom: none;
    margin-top: 2in;
}

/* Second element (subtitle) */
body > h1:first-child + h2 {
    text-align: center;
    border-bottom: none;
    color: #4a5568;
    font-size: 16pt;
    margin-bottom: 1in;
    page-break-before: avoid;
    page-break-after: always;
}

h2 {
    color: #2c5282;
    font-size: 14pt;
    font-weight: bold;
    margin-top: 25px;
    margin-bottom: 10px;
    border-bottom: 1px solid #cbd5e0;
    padding-bottom: 5px;
    page-break-before: auto;
}

h3 {
    color: #2d3748;
    font-size: 12pt;
    font-weight: bold;
    margin-top: 18px;
    margin-bottom: 8px;
}

h4 {
    color: #4a5568;
    font-size: 11pt;
    font-weight: bold;
    margin-top: 12px;
    margin-bottom: 6px;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 9pt;
    page-break-inside: avoid;
}

th {
    background-color: #1a365d;
    color: white;
    padding: 8px 6px;
    text-align: left;
    font-weight: bold;
    font-size: 9pt;
}

td {
    padding: 6px;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
}

tr:nth-child(even) {
    background-color: #f7fafc;
}

code {
    background-color: #edf2f7;
    padding: 1px 4px;
    border-radius: 2px;
    font-family: "Monaco", "Consolas", "Courier New", monospace;
    font-size: 8.5pt;
}

pre {
    background-color: #1a202c;
    color: #e2e8f0;
    padding: 12px;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 8pt;
    line-height: 1.3;
    margin: 12px 0;
    page-break-inside: avoid;
    white-space: pre-wrap;
    word-wrap: break-word;
}

pre code {
    background-color: transparent;
    padding: 0;
    color: inherit;
    font-size: 8pt;
}

blockquote {
    border-left: 3px solid #c9a227;
    padding-left: 12px;
    margin-left: 0;
    color: #4a5568;
    font-style: italic;
}

ul, ol {
    margin: 8px 0;
    padding-left: 20px;
}

li {
    margin: 4px 0;
}

strong {
    color: #1a365d;
}

hr {
    border: none;
    border-top: 1px solid #cbd5e0;
    margin: 20px 0;
}

a {
    color: #2b6cb0;
    text-decoration: none;
}

p {
    margin: 8px 0;
}

/* Prevent orphans and widows */
p, li {
    orphans: 3;
    widows: 3;
}

/* Keep headers with following content */
h1, h2, h3, h4 {
    page-break-after: avoid;
}
''')

# Wrap HTML content
full_html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Check Review Console - Technical Guide</title>
</head>
<body>
{html_content}
</body>
</html>
'''

# Generate PDF
pdf_path = Path(__file__).parent / "CHECK_REVIEW_CONSOLE_TECHNICAL_GUIDE.pdf"
HTML(string=full_html).write_pdf(pdf_path, stylesheets=[css])

print(f"\nPDF generated: {pdf_path}")
print(f"File size: {pdf_path.stat().st_size / 1024:.1f} KB")
