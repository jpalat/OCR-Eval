#!/usr/bin/env python3
"""
OCR Comparison Tool for National Archives Images

Runs Mistral OCR on archive images and compares output against
existing transcriptions, generating HTML comparison reports.
"""

import argparse
import base64
import os
import re
import sys
import json
import difflib
import string
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv
from mistralai import Mistral

# Load environment variables from .env file
load_dotenv()


@dataclass
class CompareOptions:
    """Options for text comparison."""
    ignore_case: bool = False
    ignore_punctuation: bool = False

    def describe(self) -> str:
        """Return a human-readable description of active options."""
        opts = []
        if self.ignore_case:
            opts.append("case-insensitive")
        if self.ignore_punctuation:
            opts.append("ignoring punctuation")
        return ", ".join(opts) if opts else "exact matching"


def normalize_text(text: str, options: CompareOptions) -> str:
    """Normalize text based on comparison options."""
    if options.ignore_case:
        text = text.lower()
    if options.ignore_punctuation:
        # Remove punctuation but keep spaces and alphanumeric
        text = re.sub(r'[^\w\s]', '', text)
    return text


def normalize_word(word: str, options: CompareOptions) -> str:
    """Normalize a single word based on comparison options."""
    if options.ignore_case:
        word = word.lower()
    if options.ignore_punctuation:
        word = word.strip(string.punctuation)
    return word

# Directories
IMAGES_DIR = Path("./images")
TRANSCRIPTIONS_DIR = Path("./transcriptions")
OCR_OUTPUT_DIR = Path("./ocr_output")
COMPARISONS_DIR = Path("./comparisons")

# Create output directories
OCR_OUTPUT_DIR.mkdir(exist_ok=True)
COMPARISONS_DIR.mkdir(exist_ok=True)


def encode_image(file_path: Path) -> str:
    """Encode an image file to base64."""
    with open(file_path, "rb") as img_file:
        return base64.standard_b64encode(img_file.read()).decode("utf-8")


def run_ocr(client: Mistral, image_path: Path) -> str:
    """Run Mistral OCR on an image and return the extracted text."""
    print(f"  Running OCR on {image_path.name}...")

    base64_image = encode_image(image_path)

    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "image_url",
            "image_url": f"data:image/jpeg;base64,{base64_image}"
        }
    )

    # Extract text from OCR response
    text_parts = []
    if hasattr(ocr_response, 'pages') and ocr_response.pages:
        for page in ocr_response.pages:
            if hasattr(page, 'markdown') and page.markdown:
                text_parts.append(page.markdown)
            elif hasattr(page, 'text') and page.text:
                text_parts.append(page.text)

    return "\n".join(text_parts)


def diff_texts(text1: str, text2: str, options: CompareOptions = None) -> tuple:
    """Compare two texts word by word and return stats and differences.

    Args:
        text1: Source/reference text
        text2: OCR output text
        options: Comparison options (ignore_case, ignore_punctuation)

    Returns:
        Tuple of (stats dict, differences list)
    """
    if options is None:
        options = CompareOptions()

    words1_orig = text1.split()
    words2_orig = text2.split()

    # Create normalized versions for comparison
    words1_norm = [normalize_word(w, options) for w in words1_orig]
    words2_norm = [normalize_word(w, options) for w in words2_orig]

    # Filter out empty words (can happen with punctuation-only tokens)
    if options.ignore_punctuation:
        filtered1 = [(orig, norm) for orig, norm in zip(words1_orig, words1_norm) if norm]
        filtered2 = [(orig, norm) for orig, norm in zip(words2_orig, words2_norm) if norm]
        words1_orig = [f[0] for f in filtered1]
        words1_norm = [f[1] for f in filtered1]
        words2_orig = [f[0] for f in filtered2]
        words2_norm = [f[1] for f in filtered2]

    # Use normalized words for matching
    matcher = difflib.SequenceMatcher(None, words1_norm, words2_norm)

    stats = {
        'equal': 0,
        'similar': 0,
        'replaced': 0,
        'deleted': 0,
        'inserted': 0,
        'total_words1': len(words1_norm),
        'total_words2': len(words2_norm),
    }

    differences = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            stats['equal'] += (i2 - i1)
        elif tag == 'replace':
            src_words_orig = words1_orig[i1:i2]
            src_words_norm = words1_norm[i1:i2]
            ocr_words_orig = words2_orig[j1:j2]
            ocr_words_norm = words2_norm[j1:j2]

            if len(src_words_norm) == len(ocr_words_norm):
                for w1_orig, w1_norm, w2_orig, w2_norm in zip(
                    src_words_orig, src_words_norm, ocr_words_orig, ocr_words_norm
                ):
                    ratio = difflib.SequenceMatcher(None, w1_norm, w2_norm).ratio()
                    if ratio > 0.5:
                        stats['similar'] += 1
                        differences.append((w1_orig, w2_orig, 'similar'))
                    else:
                        stats['replaced'] += 1
                        differences.append((w1_orig, w2_orig, 'replaced'))
            else:
                for w in src_words_orig:
                    stats['deleted'] += 1
                    differences.append((w, '', 'deleted'))
                for w in ocr_words_orig:
                    stats['inserted'] += 1
                    differences.append(('', w, 'inserted'))
        elif tag == 'delete':
            for w in words1_orig[i1:i2]:
                stats['deleted'] += 1
                differences.append((w, '', 'deleted'))
        elif tag == 'insert':
            for w in words2_orig[j1:j2]:
                stats['inserted'] += 1
                differences.append(('', w, 'inserted'))

    return stats, differences


def generate_comparison_html(
    item_name: str,
    image_path: Path,
    source_text: str,
    ocr_text: str,
    stats: dict,
    differences: list,
    output_file: Path,
    options: CompareOptions = None
):
    """Generate an HTML comparison report."""
    if options is None:
        options = CompareOptions()

    words1 = source_text.split()
    words2 = ocr_text.split()

    # Normalize for matching (same as diff_texts)
    words1_norm = [normalize_word(w, options) for w in words1]
    words2_norm = [normalize_word(w, options) for w in words2]

    if options.ignore_punctuation:
        filtered1 = [(orig, norm) for orig, norm in zip(words1, words1_norm) if norm]
        filtered2 = [(orig, norm) for orig, norm in zip(words2, words2_norm) if norm]
        words1 = [f[0] for f in filtered1]
        words1_norm = [f[1] for f in filtered1]
        words2 = [f[0] for f in filtered2]
        words2_norm = [f[1] for f in filtered2]

    matcher = difflib.SequenceMatcher(None, words1_norm, words2_norm)

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
    for i, (src, ocr, diff_type) in enumerate(differences[:100], 1):  # Limit to 100
        src_escaped = src.replace('<', '&lt;').replace('>', '&gt;')
        ocr_escaped = ocr.replace('<', '&lt;').replace('>', '&gt;')
        if diff_type == 'similar':
            diff_rows.append(f'<tr class="similar"><td>{i}</td><td>{src_escaped}</td><td>→</td><td>{ocr_escaped}</td></tr>')
        elif diff_type == 'replaced':
            diff_rows.append(f'<tr class="replaced"><td>{i}</td><td>{src_escaped}</td><td>→</td><td>{ocr_escaped}</td></tr>')
        elif diff_type == 'deleted':
            diff_rows.append(f'<tr class="deleted"><td>{i}</td><td>{src_escaped}</td><td>→</td><td>(deleted)</td></tr>')
        elif diff_type == 'inserted':
            diff_rows.append(f'<tr class="inserted"><td>{i}</td><td>(none)</td><td>→</td><td>{ocr_escaped}</td></tr>')

    if len(differences) > 100:
        diff_rows.append(f'<tr><td colspan="4"><em>... and {len(differences) - 100} more differences</em></td></tr>')

    accuracy = (stats['equal'] / stats['total_words1'] * 100) if stats['total_words1'] > 0 else 0
    total_errors = stats['similar'] + stats['replaced'] + stats['deleted'] + stats['inserted']

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OCR Comparison - {item_name}</title>
    <style>
        body {{ font-family: Georgia, serif; margin: 20px; background: #f5f5f5; line-height: 1.6; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #333; text-align: center; }}
        h2 {{ color: #555; }}
        .panel {{ background: white; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .panel h2 {{ margin-top: 0; color: #444; border-bottom: 2px solid #007acc; padding-bottom: 10px; }}
        .text {{ line-height: 2; font-size: 16px; white-space: pre-wrap; }}
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
        .image-preview {{ max-width: 100%; max-height: 400px; border: 1px solid #ddd; }}
        .side-by-side {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        @media (max-width: 900px) {{ .side-by-side {{ grid-template-columns: 1fr; }} }}
        .nav {{ text-align: center; margin: 20px 0; }}
        .nav a {{ margin: 0 10px; color: #007acc; text-decoration: none; }}
        .nav a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="nav">
            <a href="summary_report.html">← Back to Summary</a>
        </div>

        <h1>OCR Comparison: {item_name}</h1>

        <div class="panel">
            <h2>Comparison Mode</h2>
            <p><strong>Options:</strong> {options.describe()}</p>
            {'<p><em>Case differences are ignored in accuracy calculations.</em></p>' if options.ignore_case else ''}
            {'<p><em>Punctuation is ignored in accuracy calculations.</em></p>' if options.ignore_punctuation else ''}
        </div>

        <div class="panel">
            <h2>Source Image</h2>
            <img src="../images/{image_path.name}" alt="{item_name}" class="image-preview">
        </div>

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
                <div class="stat-box {'good' if accuracy >= 80 else 'warn'}">
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

        <div class="side-by-side">
            <div class="panel">
                <h2>Source Transcription</h2>
                <div class="text">{' '.join(html_text1)}</div>
            </div>

            <div class="panel">
                <h2>Mistral OCR Output</h2>
                <div class="text">{' '.join(html_text2)}</div>
            </div>
        </div>

        <div class="panel">
            <h2>Differences List ({len(differences)} items)</h2>
            <table>
                <tr><th>#</th><th>Source</th><th></th><th>OCR</th></tr>
                {''.join(diff_rows) if diff_rows else '<tr><td colspan="4">No differences found!</td></tr>'}
            </table>
        </div>

        <div class="nav">
            <a href="summary_report.html">← Back to Summary</a>
        </div>
    </div>
</body>
</html>"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def generate_summary_report(results: list, output_file: Path, options: CompareOptions = None):
    """Generate a summary HTML report for all items."""
    if options is None:
        options = CompareOptions()
    total_source_words = sum(r['stats']['total_words1'] for r in results)
    total_ocr_words = sum(r['stats']['total_words2'] for r in results)
    total_matches = sum(r['stats']['equal'] for r in results)
    total_errors = sum(
        r['stats']['similar'] + r['stats']['replaced'] +
        r['stats']['deleted'] + r['stats']['inserted']
        for r in results
    )
    overall_accuracy = (total_matches / total_source_words * 100) if total_source_words > 0 else 0

    # Generate table rows
    table_rows = []
    for r in results:
        accuracy = (r['stats']['equal'] / r['stats']['total_words1'] * 100) if r['stats']['total_words1'] > 0 else 0
        errors = r['stats']['similar'] + r['stats']['replaced'] + r['stats']['deleted'] + r['stats']['inserted']
        accuracy_class = 'good' if accuracy >= 80 else 'warn' if accuracy >= 50 else 'bad'
        table_rows.append(f"""
            <tr>
                <td><a href="{r['comparison_file']}">{r['item_name']}</a></td>
                <td>{r['stats']['total_words1']}</td>
                <td>{r['stats']['total_words2']}</td>
                <td>{r['stats']['equal']}</td>
                <td>{errors}</td>
                <td class="{accuracy_class}">{accuracy:.1f}%</td>
            </tr>
        """)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OCR Comparison Summary Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; text-align: center; margin-bottom: 10px; }}
        .subtitle {{ text-align: center; color: #666; margin-bottom: 30px; }}
        .panel {{ background: white; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .panel h2 {{ margin-top: 0; color: #444; border-bottom: 2px solid #007acc; padding-bottom: 10px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; }}
        .stat-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 8px; text-align: center; }}
        .stat-box.good {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
        .stat-box.warn {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .stat-box .value {{ font-size: 36px; font-weight: bold; }}
        .stat-box .label {{ font-size: 14px; opacity: 0.9; text-transform: uppercase; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        tr:hover {{ background: #f8f9fa; }}
        td a {{ color: #007acc; text-decoration: none; }}
        td a:hover {{ text-decoration: underline; }}
        td.good {{ color: #155724; font-weight: bold; }}
        td.warn {{ color: #856404; font-weight: bold; }}
        td.bad {{ color: #721c24; font-weight: bold; }}
        .meta {{ text-align: center; color: #888; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OCR Comparison Summary Report</h1>
        <p class="subtitle">Mistral OCR vs. NARA Transcriptions for NAID 54928953</p>

        <div class="panel">
            <h2>Overall Statistics</h2>
            <div class="stats">
                <div class="stat-box">
                    <div class="value">{len(results)}</div>
                    <div class="label">Documents Processed</div>
                </div>
                <div class="stat-box">
                    <div class="value">{total_source_words:,}</div>
                    <div class="label">Total Source Words</div>
                </div>
                <div class="stat-box">
                    <div class="value">{total_ocr_words:,}</div>
                    <div class="label">Total OCR Words</div>
                </div>
                <div class="stat-box good">
                    <div class="value">{total_matches:,}</div>
                    <div class="label">Exact Matches</div>
                </div>
                <div class="stat-box warn">
                    <div class="value">{total_errors:,}</div>
                    <div class="label">Total Errors</div>
                </div>
                <div class="stat-box {'good' if overall_accuracy >= 80 else 'warn'}">
                    <div class="value">{overall_accuracy:.1f}%</div>
                    <div class="label">Overall Accuracy</div>
                </div>
            </div>
        </div>

        <div class="panel">
            <h2>Individual Document Results</h2>
            <table>
                <tr>
                    <th>Document</th>
                    <th>Source Words</th>
                    <th>OCR Words</th>
                    <th>Matches</th>
                    <th>Errors</th>
                    <th>Accuracy</th>
                </tr>
                {''.join(table_rows)}
            </table>
        </div>

        <div class="panel">
            <h2>About This Report</h2>
            <p>This report compares Mistral OCR output against community-contributed transcriptions
            from the National Archives Catalog for Revolutionary War Pension Application File S. 7026
            (John Hough, Va.).</p>
            <p><strong>Source:</strong> <a href="https://catalog.archives.gov/id/54928953" target="_blank">
            https://catalog.archives.gov/id/54928953</a></p>
            <p><strong>OCR Model:</strong> mistral-ocr-latest</p>
            <p><strong>Comparison Mode:</strong> {options.describe()}</p>
        </div>

        <p class="meta">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
</body>
</html>"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Run OCR comparison on archive images',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Exact matching (default)
  %(prog)s --ignore-case             # Case-insensitive comparison
  %(prog)s --ignore-punctuation      # Ignore punctuation differences
  %(prog)s -i -p                     # Both options combined
  %(prog)s --no-ocr                  # Skip OCR, compare only (use cached)
        """
    )
    parser.add_argument(
        '-i', '--ignore-case',
        action='store_true',
        help='Ignore case differences when comparing'
    )
    parser.add_argument(
        '-p', '--ignore-punctuation',
        action='store_true',
        help='Ignore punctuation differences when comparing'
    )
    parser.add_argument(
        '--no-ocr',
        action='store_true',
        help='Skip OCR processing, use cached results only'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=COMPARISONS_DIR,
        help=f'Output directory for reports (default: {COMPARISONS_DIR})'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Build comparison options
    options = CompareOptions(
        ignore_case=args.ignore_case,
        ignore_punctuation=args.ignore_punctuation
    )

    print(f"Comparison mode: {options.describe()}")

    # Check for API key (only needed if running OCR)
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key and not args.no_ocr:
        print("Error: MISTRAL_API_KEY environment variable not set")
        print("Use --no-ocr to skip OCR and use cached results only")
        sys.exit(1)

    # Initialize Mistral client if needed
    client = Mistral(api_key=api_key) if api_key and not args.no_ocr else None

    # Create output directory
    output_dir = args.output_dir
    output_dir.mkdir(exist_ok=True)

    # Get list of images
    image_files = sorted(IMAGES_DIR.glob("item_*.jpg"))
    print(f"Found {len(image_files)} images to process")

    results = []

    for image_path in image_files:
        item_name = image_path.stem  # e.g., item_01_54928954
        print(f"\nProcessing {item_name}...")

        # Find corresponding transcription
        trans_path = TRANSCRIPTIONS_DIR / f"{item_name}.txt"
        if not trans_path.exists():
            print(f"  Warning: No transcription found for {item_name}")
            continue

        # Read source transcription
        with open(trans_path, 'r', encoding='utf-8') as f:
            source_text = f.read().strip()

        # Check for cached OCR output
        ocr_output_path = OCR_OUTPUT_DIR / f"{item_name}_ocr.txt"

        if ocr_output_path.exists():
            print(f"  Using cached OCR output")
            with open(ocr_output_path, 'r', encoding='utf-8') as f:
                ocr_text = f.read().strip()
        elif args.no_ocr:
            print(f"  No cached OCR output found, skipping (--no-ocr mode)")
            continue
        else:
            # Run OCR
            try:
                ocr_text = run_ocr(client, image_path)
                # Save OCR output
                with open(ocr_output_path, 'w', encoding='utf-8') as f:
                    f.write(ocr_text)
                print(f"  OCR complete, saved to {ocr_output_path}")
            except Exception as e:
                print(f"  Error running OCR: {e}")
                continue

        # Compare texts
        stats, differences = diff_texts(source_text, ocr_text, options)

        accuracy = (stats['equal'] / stats['total_words1'] * 100) if stats['total_words1'] > 0 else 0
        print(f"  Accuracy: {accuracy:.1f}% ({stats['equal']}/{stats['total_words1']} words)")

        # Generate HTML comparison
        comparison_file = f"{item_name}_comparison.html"
        comparison_path = output_dir / comparison_file
        generate_comparison_html(
            item_name, image_path, source_text, ocr_text,
            stats, differences, comparison_path, options
        )
        print(f"  Comparison saved to {comparison_path}")

        results.append({
            'item_name': item_name,
            'image_path': image_path,
            'stats': stats,
            'differences': differences,
            'comparison_file': comparison_file
        })

    # Generate summary report
    summary_path = output_dir / "summary_report.html"
    generate_summary_report(results, summary_path, options)
    print(f"\n{'='*50}")
    print(f"Comparison mode: {options.describe()}")
    print(f"Summary report saved to: {summary_path}")
    print(f"Individual comparisons saved to: {output_dir}/")
    print(f"OCR outputs saved to: {OCR_OUTPUT_DIR}/")

    # Save JSON results
    json_results = {
        'options': {
            'ignore_case': options.ignore_case,
            'ignore_punctuation': options.ignore_punctuation,
        },
        'results': []
    }
    for r in results:
        json_results['results'].append({
            'item_name': r['item_name'],
            'stats': r['stats'],
            'comparison_file': r['comparison_file']
        })

    with open(output_dir / "results.json", 'w') as f:
        json.dump(json_results, f, indent=2)


if __name__ == "__main__":
    main()
