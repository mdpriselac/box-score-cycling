"""Wrap the artifact body fragment into a standalone index.html for Netlify.
Rerun after any rebuild of predictor-architecture.html."""

from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "predictor-architecture.html"
OUT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR.mkdir(exist_ok=True)

body = SRC.read_text()

# The fragment carries its own <meta charset> and <title> for the artifact
# publisher; strip them since the standalone head declares both.
body = body.replace('<meta charset="utf-8">\n', "")
title_line = '<title>How the Cycling Race Predictor Prices a Race</title>\n'
body = body.replace(title_line, "")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How the Cycling Race Predictor Prices a Race</title>
<meta name="description" content="A LightGBM prediction stack for professional cycling: how the model heads work, Tour de France 2026 predictions, and how they compare with the bookmakers.">
<meta property="og:title" content="How the Cycling Race Predictor Prices a Race">
<meta property="og:description" content="Seven model heads, one pricing layer — plus live Tour de France 2026 predictions and a model-vs-bookmaker comparison.">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚴</text></svg>">
<style>
  *,*::before,*::after{{box-sizing:border-box}}
  img,svg{{max-width:100%}}
</style>
</head>
<body>
{body}
</body>
</html>
"""

(OUT_DIR / "index.html").write_text(html)
print(f"Wrote {OUT_DIR / 'index.html'} "
      f"({(OUT_DIR / 'index.html').stat().st_size / 1024:.0f} KB)")
