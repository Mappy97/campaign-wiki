#!/usr/bin/env python3
"""
Simple Static Site Generator for Obsidian Vault
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path

VAULT_PATH = "/Users/matt/Documents/Obsidian/DND-Campaign"
OUTPUT_PATH = "/Users/matt/Documents/Obsidian/DND-Campaign-site/public"
TEMPLATE_PATH = "/Users/matt/Documents/Obsidian/DND-Campaign-site/templates"

os.makedirs(OUTPUT_PATH, exist_ok=True)
os.makedirs(TEMPLATE_PATH, exist_ok=True)

def parse_frontmatter(content):
    """Extract YAML frontmatter from markdown"""
    if not content.startswith('---'):
        return {}, content
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    
    frontmatter_text = parts[1]
    body = parts[2]
    
    fm = {}
    for line in frontmatter_text.strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            fm[key.strip()] = value.strip().strip('"')
    
    return fm, body

def convert_wikilinks(content):
    """Convert [[links]] to HTML links"""
    # [[Link]] -> <a href="/link">Link</a>
    content = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'<a href="/\1">\2</a>', content)
    content = re.sub(r'\[\[([^\]]+)\]\]', r'<a href="/\1">\1</a>', content)
    return content

def convert_markdown(content):
    """Simple markdown to HTML conversion"""
    content = convert_wikilinks(content)
    
    # Headers
    for i in range(6, 0, -1):
        content = re.sub(r'^' + '#' * i + ' (.+)$', r'<h' + str(i) + r'>\1</h' + str(i) + '>', content, flags=re.MULTILINE)
    
    # Bold
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
    content = re.sub(r'__(.+?)__', r'<strong>\1</strong>', content)
    
    # Italic
    content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
    content = re.sub(r'_(.+?)_', r'<em>\1</em>', content)
    
    # Lists
    content = re.sub(r'^- (.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)
    content = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', content)
    
    # Paragraphs
    content = re.sub(r'\n\n+', '</p><p>', content)
    
    return f'<p>{content}</p>'

def get_all_files():
    """Get all markdown files from vault"""
    files = []
    for root, dirs, filenames in os.walk(VAULT_PATH):
        # Skip certain folders
        dirs[:] = [d for d in dirs if d not in ['.obsidian', 'node_modules', '.git', 'Inbox']]
        
        for filename in filenames:
            if filename.endswith('.md'):
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, VAULT_PATH)
                files.append((full_path, rel_path))
    
    return files

def generate_index_page(files):
    """Generate index page with all files"""
    sections = {}
    
    for full_path, rel_path in files:
        # Determine section
        parts = rel_path.split(os.sep)
        section = parts[0] if len(parts) > 1 else 'Root'
        
        if section not in sections:
            sections[section] = []
        
        # Read file
        with open(full_path, 'r') as f:
            content = f.read()
        
        fm, body = parse_frontmatter(content)
        title = fm.get('title', fm.get('id', parts[-1].replace('.md', '')))
        
        sections[section].append({
            'title': title,
            'path': '/' + rel_path.replace('.md', '').replace(os.sep, '/')
        })
    
    # Generate HTML
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>DND Campaign</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #1a1a1a; color: #e0e0e0; }
        h1 { color: #7c9885; border-bottom: 1px solid #333; padding-bottom: 10px; }
        h2 { color: #9cb09c; margin-top: 30px; }
        a { color: #7c9885; text-decoration: none; }
        a:hover { text-decoration: underline; }
        ul { list-style: none; padding: 0; }
        li { padding: 8px 0; border-bottom: 1px solid #2a2a2a; }
        .section { margin-bottom: 30px; }
    </style>
</head>
<body>
    <h1>🎲 DND Campaign Vault</h1>
    <p>Welcome to the Banana Boys campaign wiki</p>
'''
    
    for section, items in sorted(sections.items()):
        html += f'<div class="section"><h2>{section}</h2><ul>'
        for item in items:
            html += f'<li><a href="{item["path"]}">{item["title"]}</a></li>'
        html += '</ul></div>'
    
    html += '''
    <footer style="margin-top: 50px; color: #666; font-size: 12px;">
        Generated ''' + datetime.now().strftime('%Y-%m-%d %H:%M') + '''
    </footer>
</body>
</html>'''
    
    return html

def generate_page(full_path, rel_path):
    """Generate individual page"""
    with open(full_path, 'r') as f:
        content = f.read()
    
    fm, body = parse_frontmatter(content)
    title = fm.get('title', fm.get('id', rel_path.replace('.md', '').split('/')[-1]))
    html_content = convert_markdown(body)
    
    # Build nav links (simple)
    nav = f'<a href="/">← Home</a>'
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>{title} - DND Campaign</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #1a1a1a; color: #e0e0e0; }}
        h1 {{ color: #7c9885; border-bottom: 1px solid #333; padding-bottom: 10px; }}
        h2, h3 {{ color: #9cb09c; }}
        a {{ color: #7c9885; }}
        .nav {{ margin-bottom: 20px; }}
        pre {{ background: #2a2a2a; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        blockquote {{ border-left: 3px solid #7c9885; margin-left: 0; padding-left: 15px; color: #999; }}
    </style>
</head>
<body>
    <div class="nav">{nav}</div>
    {html_content}
</body>
</html>'''
    
    return html

# Main
print("Generating static site...")

files = get_all_files()
print(f"Found {len(files)} markdown files")

# Generate index
index_html = generate_index_page(files)
with open(os.path.join(OUTPUT_PATH, 'index.html'), 'w') as f:
    f.write(index_html)

# Generate individual pages
for full_path, rel_path in files:
    output_name = rel_path.replace('.md', '.html')
    output_dir = os.path.dirname(os.path.join(OUTPUT_PATH, output_name))
    os.makedirs(output_dir, exist_ok=True)
    
    html = generate_page(full_path, rel_path)
    with open(os.path.join(OUTPUT_PATH, output_name), 'w') as f:
        f.write(html)

print(f"Generated site at: {OUTPUT_PATH}")
print("Run: cd {} && npx serve public".format(os.path.dirname(OUTPUT_PATH)))