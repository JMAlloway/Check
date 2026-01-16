#!/usr/bin/env python3
"""Convert Markdown technical guide to PDF."""

import markdown
from weasyprint import HTML, CSS
from pathlib import Path

# Read the markdown file
md_path = Path(__file__).parent / "CHECK_REVIEW_CONSOLE_TECHNICAL_GUIDE.md"
md_content = md_path.read_text()

# Convert markdown to HTML
md_extensions = [
    'tables',
    'fenced_code',
    'codehilite',
    'toc',
    'nl2br',
]

html_content = markdown.markdown(md_content, extensions=md_extensions)

# CSS for professional PDF styling
css = CSS(string='''
@page {
    size: letter;
    margin: 1in;
    @top-center {
        content: "Check Review Console - Technical Guide";
        font-size: 9pt;
        color: #666;
    }
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #666;
    }
}

body {
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #333;
}

h1 {
    color: #1a365d;
    font-size: 24pt;
    border-bottom: 3px solid #c9a227;
    padding-bottom: 10px;
    margin-top: 40px;
    page-break-before: always;
}

h1:first-of-type {
    page-break-before: avoid;
}

h2 {
    color: #2c5282;
    font-size: 18pt;
    margin-top: 30px;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 5px;
}

h3 {
    color: #2d3748;
    font-size: 14pt;
    margin-top: 20px;
}

h4 {
    color: #4a5568;
    font-size: 12pt;
    margin-top: 15px;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
    font-size: 10pt;
}

th {
    background-color: #1a365d;
    color: white;
    padding: 10px;
    text-align: left;
    font-weight: bold;
}

td {
    padding: 8px 10px;
    border-bottom: 1px solid #e2e8f0;
}

tr:nth-child(even) {
    background-color: #f7fafc;
}

code {
    background-color: #edf2f7;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "Monaco", "Consolas", monospace;
    font-size: 9pt;
}

pre {
    background-color: #1a202c;
    color: #e2e8f0;
    padding: 15px;
    border-radius: 5px;
    overflow-x: auto;
    font-size: 9pt;
    line-height: 1.4;
    margin: 15px 0;
}

pre code {
    background-color: transparent;
    padding: 0;
    color: inherit;
}

blockquote {
    border-left: 4px solid #c9a227;
    padding-left: 15px;
    margin-left: 0;
    color: #4a5568;
    font-style: italic;
}

ul, ol {
    margin: 10px 0;
    padding-left: 25px;
}

li {
    margin: 5px 0;
}

strong {
    color: #1a365d;
}

hr {
    border: none;
    border-top: 2px solid #e2e8f0;
    margin: 30px 0;
}

a {
    color: #2b6cb0;
    text-decoration: none;
}

/* Cover page styling */
body > h1:first-of-type {
    text-align: center;
    font-size: 36pt;
    border-bottom: none;
    margin-top: 200px;
}

body > h1:first-of-type + h2 {
    text-align: center;
    border-bottom: none;
    color: #4a5568;
    margin-bottom: 100px;
}

/* Keep sections together where possible */
h2, h3, h4 {
    page-break-after: avoid;
}

table, pre {
    page-break-inside: avoid;
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

print(f"PDF generated successfully: {pdf_path}")
print(f"File size: {pdf_path.stat().st_size / 1024:.1f} KB")
