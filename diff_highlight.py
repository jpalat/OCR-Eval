#!/usr/bin/env python3
"""
Text diff highlighting tool for comparing OCR output against source text.
Highlights word-level and character-level differences with colors.
"""

import argparse
import difflib
import sys


class Color:
    """ANSI color codes for terminal output."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'


def char_diff_highlight(word1, word2):
    """Show character-level diff between two similar words."""
    matcher = difflib.SequenceMatcher(None, word1, word2)
    result1_parts = []
    result2_parts = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            result1_parts.append(word1[i1:i2])
            result2_parts.append(word2[j1:j2])
        elif tag == 'replace':
            result1_parts.append(f"{Color.BG_RED}{Color.BOLD}{word1[i1:i2]}{Color.RESET}")
            result2_parts.append(f"{Color.BG_GREEN}{Color.BOLD}{word2[j1:j2]}{Color.RESET}")
        elif tag == 'delete':
            result1_parts.append(f"{Color.BG_RED}{Color.BOLD}{word1[i1:i2]}{Color.RESET}")
        elif tag == 'insert':
            result2_parts.append(f"{Color.BG_GREEN}{Color.BOLD}{word2[j1:j2]}{Color.RESET}")

    return ''.join(result1_parts), ''.join(result2_parts)


def diff_texts(text1, text2):
    """
    Compare two texts word by word and return highlighted versions.
    """
    words1 = text1.split()
    words2 = text2.split()

    matcher = difflib.SequenceMatcher(None, words1, words2)

    result1 = []
    result2 = []

    stats = {
        'equal': 0,
        'similar': 0,
        'replaced': 0,
        'deleted': 0,
        'inserted': 0,
        'total_words1': len(words1),
        'total_words2': len(words2),
    }

    differences = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            result1.extend(words1[i1:i2])
            result2.extend(words2[j1:j2])
            stats['equal'] += (i2 - i1)

        elif tag == 'replace':
            # Check if words are similar (possible OCR errors)
            src_words = words1[i1:i2]
            ocr_words = words2[j1:j2]

            if len(src_words) == len(ocr_words):
                # One-to-one replacement - show char-level diff
                for w1, w2 in zip(src_words, ocr_words):
                    ratio = difflib.SequenceMatcher(None, w1, w2).ratio()
                    if ratio > 0.5:  # Similar words - show char diff
                        h1, h2 = char_diff_highlight(w1, w2)
                        result1.append(h1)
                        result2.append(h2)
                        stats['similar'] += 1
                        differences.append((w1, w2, 'similar'))
                    else:  # Very different - highlight whole word
                        result1.append(f"{Color.RED}{Color.UNDERLINE}{w1}{Color.RESET}")
                        result2.append(f"{Color.GREEN}{Color.UNDERLINE}{w2}{Color.RESET}")
                        stats['replaced'] += 1
                        differences.append((w1, w2, 'replaced'))
            else:
                # Different number of words - highlight chunks
                for w in src_words:
                    result1.append(f"{Color.RED}{Color.UNDERLINE}{w}{Color.RESET}")
                    stats['deleted'] += 1
                    differences.append((w, '', 'deleted'))
                for w in ocr_words:
                    result2.append(f"{Color.GREEN}{Color.UNDERLINE}{w}{Color.RESET}")
                    stats['inserted'] += 1
                    differences.append(('', w, 'inserted'))

        elif tag == 'delete':
            for w in words1[i1:i2]:
                result1.append(f"{Color.RED}{Color.BOLD}[{w}]{Color.RESET}")
                stats['deleted'] += 1
                differences.append((w, '', 'deleted'))

        elif tag == 'insert':
            for w in words2[j1:j2]:
                result2.append(f"{Color.GREEN}{Color.BOLD}[{w}]{Color.RESET}")
                stats['inserted'] += 1
                differences.append(('', w, 'inserted'))

    return ' '.join(result1), ' '.join(result2), stats, differences


def print_legend():
    """Print color legend."""
    print(f"{Color.BOLD}{Color.CYAN}═══ LEGEND ═══{Color.RESET}")
    print(f"  {Color.BG_RED}text{Color.RESET} = Characters in source but wrong/missing in OCR")
    print(f"  {Color.BG_GREEN}text{Color.RESET} = Characters in OCR that differ from source")
    print(f"  {Color.RED}[text]{Color.RESET} = Words deleted from source")
    print(f"  {Color.GREEN}[text]{Color.RESET} = Words inserted in OCR")
    print()


def print_differences_list(differences):
    """Print a numbered list of all differences."""
    if not differences:
        print(f"{Color.GREEN}No differences found!{Color.RESET}")
        return

    print(f"{Color.BOLD}{Color.CYAN}═══ DIFFERENCES LIST ═══{Color.RESET}")
    for i, (src, ocr, diff_type) in enumerate(differences, 1):
        if diff_type == 'similar':
            print(f"  {i:3}. {Color.YELLOW}'{src}'{Color.RESET} → {Color.YELLOW}'{ocr}'{Color.RESET}")
        elif diff_type == 'replaced':
            print(f"  {i:3}. {Color.RED}'{src}'{Color.RESET} → {Color.GREEN}'{ocr}'{Color.RESET}")
        elif diff_type == 'deleted':
            print(f"  {i:3}. {Color.RED}DELETED: '{src}'{Color.RESET}")
        elif diff_type == 'inserted':
            print(f"  {i:3}. {Color.GREEN}INSERTED: '{ocr}'{Color.RESET}")
    print()


def print_output(text1, text2, stats, differences, show_list=True):
    """Print inline diff with summary."""
    print_legend()

    print(f"{Color.BOLD}{Color.CYAN}═══ SOURCE TEXT (with errors marked) ═══{Color.RESET}")
    print(text1)
    print()

    print(f"{Color.BOLD}{Color.CYAN}═══ OCR OUTPUT (with errors marked) ═══{Color.RESET}")
    print(text2)
    print()

    if show_list:
        print_differences_list(differences)

    # Statistics
    total_errors = stats['similar'] + stats['replaced'] + stats['deleted'] + stats['inserted']
    accuracy = (stats['equal'] / stats['total_words1'] * 100) if stats['total_words1'] > 0 else 0

    print(f"{Color.BOLD}{Color.CYAN}═══ STATISTICS ═══{Color.RESET}")
    print(f"  Source words:      {stats['total_words1']}")
    print(f"  OCR words:         {stats['total_words2']}")
    print(f"  {Color.GREEN}Exact matches:     {stats['equal']}{Color.RESET}")
    print(f"  {Color.YELLOW}Similar (OCR err): {stats['similar']}{Color.RESET}")
    print(f"  {Color.MAGENTA}Replaced:          {stats['replaced']}{Color.RESET}")
    print(f"  {Color.RED}Deleted:           {stats['deleted']}{Color.RESET}")
    print(f"  {Color.GREEN}Inserted:          {stats['inserted']}{Color.RESET}")
    print(f"  Total errors:      {total_errors}")
    print(f"  {Color.BOLD}Word accuracy:     {accuracy:.1f}%{Color.RESET}")


def generate_html(text1_raw, text2_raw, stats, differences, output_file):
    """Generate an HTML file with highlighted differences."""
    # Re-process for HTML output
    words1 = text1_raw.split()
    words2 = text2_raw.split()
    matcher = difflib.SequenceMatcher(None, words1, words2)

    html_text1 = []
    html_text2 = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            html_text1.extend(words1[i1:i2])
            html_text2.extend(words2[j1:j2])
        elif tag == 'replace':
            src_words = words1[i1:i2]
            ocr_words = words2[j1:j2]
            if len(src_words) == len(ocr_words):
                for w1, w2 in zip(src_words, ocr_words):
                    html_text1.append(f'<span class="error" title="OCR: {w2}">{w1}</span>')
                    html_text2.append(f'<span class="error" title="Source: {w1}">{w2}</span>')
            else:
                for w in src_words:
                    html_text1.append(f'<span class="deleted">{w}</span>')
                for w in ocr_words:
                    html_text2.append(f'<span class="inserted">{w}</span>')
        elif tag == 'delete':
            for w in words1[i1:i2]:
                html_text1.append(f'<span class="deleted">{w}</span>')
        elif tag == 'insert':
            for w in words2[j1:j2]:
                html_text2.append(f'<span class="inserted">{w}</span>')

    # Generate differences table
    diff_rows = []
    for i, (src, ocr, diff_type) in enumerate(differences, 1):
        if diff_type == 'similar':
            diff_rows.append(f'<tr class="similar"><td>{i}</td><td>{src}</td><td>→</td><td>{ocr}</td></tr>')
        elif diff_type == 'replaced':
            diff_rows.append(f'<tr class="replaced"><td>{i}</td><td>{src}</td><td>→</td><td>{ocr}</td></tr>')
        elif diff_type == 'deleted':
            diff_rows.append(f'<tr class="deleted"><td>{i}</td><td>{src}</td><td>→</td><td>(deleted)</td></tr>')
        elif diff_type == 'inserted':
            diff_rows.append(f'<tr class="inserted"><td>{i}</td><td>(none)</td><td>→</td><td>{ocr}</td></tr>')

    accuracy = (stats['equal'] / stats['total_words1'] * 100) if stats['total_words1'] > 0 else 0
    total_errors = stats['similar'] + stats['replaced'] + stats['deleted'] + stats['inserted']

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OCR Diff Comparison</title>
    <style>
        body {{ font-family: Georgia, serif; margin: 20px; background: #f5f5f5; line-height: 1.6; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #333; text-align: center; }}
        .panel {{ background: white; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .panel h2 {{ margin-top: 0; color: #444; border-bottom: 2px solid #007acc; padding-bottom: 10px; }}
        .text {{ line-height: 2; font-size: 16px; }}
        .error {{ background: #fff3cd; border-bottom: 2px solid #ffc107; cursor: help; }}
        .deleted {{ background: #f8d7da; text-decoration: line-through; color: #721c24; }}
        .inserted {{ background: #d4edda; color: #155724; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; }}
        .stat-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-box.good {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
        .stat-box.warn {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .stat-box .value {{ font-size: 28px; font-weight: bold; }}
        .stat-box .label {{ font-size: 12px; opacity: 0.9; text-transform: uppercase; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; }}
        tr.similar td {{ background: #fff3cd; }}
        tr.replaced td {{ background: #ffe6e6; }}
        tr.deleted td {{ background: #f8d7da; }}
        tr.inserted td {{ background: #d4edda; }}
        .legend {{ display: flex; gap: 20px; flex-wrap: wrap; padding: 10px; background: #f8f9fa; border-radius: 5px; }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; }}
        .legend-color {{ width: 20px; height: 20px; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OCR Diff Comparison</h1>

        <div class="panel">
            <h2>Statistics</h2>
            <div class="stats">
                <div class="stat-box">
                    <div class="value">{stats['total_words1']}</div>
                    <div class="label">Source Words</div>
                </div>
                <div class="stat-box">
                    <div class="value">{stats['total_words2']}</div>
                    <div class="label">OCR Words</div>
                </div>
                <div class="stat-box good">
                    <div class="value">{stats['equal']}</div>
                    <div class="label">Exact Matches</div>
                </div>
                <div class="stat-box warn">
                    <div class="value">{total_errors}</div>
                    <div class="label">Total Errors</div>
                </div>
                <div class="stat-box good">
                    <div class="value">{accuracy:.1f}%</div>
                    <div class="label">Word Accuracy</div>
                </div>
            </div>
        </div>

        <div class="panel">
            <h2>Legend</h2>
            <div class="legend">
                <div class="legend-item"><span class="legend-color" style="background:#fff3cd;border:1px solid #ffc107;"></span> OCR Error (hover for details)</div>
                <div class="legend-item"><span class="legend-color" style="background:#f8d7da;"></span> Deleted from source</div>
                <div class="legend-item"><span class="legend-color" style="background:#d4edda;"></span> Inserted in OCR</div>
            </div>
        </div>

        <div class="panel">
            <h2>Source Text</h2>
            <div class="text">{' '.join(html_text1)}</div>
        </div>

        <div class="panel">
            <h2>OCR Output</h2>
            <div class="text">{' '.join(html_text2)}</div>
        </div>

        <div class="panel">
            <h2>Differences List ({len(differences)} items)</h2>
            <table>
                <tr><th>#</th><th>Source</th><th></th><th>OCR</th></tr>
                {''.join(diff_rows)}
            </table>
        </div>
    </div>
</body>
</html>"""

    with open(output_file, 'w') as f:
        f.write(html)
    print(f"{Color.GREEN}HTML output saved to: {output_file}{Color.RESET}")


def main():
    parser = argparse.ArgumentParser(
        description='Highlight differences between two text files (OCR comparison)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s source.txt ocr_output.txt
  %(prog)s source.txt ocr_output.txt --html report.html
  %(prog)s source.txt ocr_output.txt --no-list
        """
    )
    parser.add_argument('file1', help='Source/reference text file')
    parser.add_argument('file2', help='OCR output/comparison text file')
    parser.add_argument('--html', metavar='FILE', help='Generate HTML output to FILE')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')
    parser.add_argument('--no-list', action='store_true', help='Hide the differences list')

    args = parser.parse_args()

    # Disable colors if requested or if not a TTY
    if args.no_color or not sys.stdout.isatty():
        for attr in dir(Color):
            if not attr.startswith('_'):
                setattr(Color, attr, '')

    try:
        with open(args.file1, 'r') as f:
            text1 = f.read().strip()
        with open(args.file2, 'r') as f:
            text2 = f.read().strip()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    highlighted1, highlighted2, stats, differences = diff_texts(text1, text2)

    if args.html:
        generate_html(text1, text2, stats, differences, args.html)

    print_output(highlighted1, highlighted2, stats, differences, not args.no_list)


if __name__ == '__main__':
    main()
