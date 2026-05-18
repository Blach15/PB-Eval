#!/usr/bin/env zsh

set -e

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

# Activate virtual environment if present
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
fi

echo "Generating LaTeX snippets from analyze.py..."
python analyze.py

PDF_DIR="tex/pdf"
mkdir -p "$PDF_DIR"

echo "Compiling each snippet to PDF..."
for snippet in tex/*.tex; do
    name="${snippet:t:r}"
    wrapper="$PDF_DIR/${name}.tex"

    printf '%s\n' \
        '\documentclass{article}' \
        '\usepackage[margin=1cm,a4paper]{geometry}' \
        '\usepackage{booktabs}' \
        '\usepackage{pgfplots}' \
        '\pgfplotsset{compat=1.18}' \
        '\usepackage{subcaption}' \
        '\usepackage{caption}' \
        '\pagestyle{empty}' \
        '\begin{document}' > "$wrapper"

    cat "$snippet" >> "$wrapper"
    printf '%s\n' '\end{document}' >> "$wrapper"

    echo "  Compiling ${name}..."
    (cd "$PDF_DIR" && pdflatex -interaction=nonstopmode "${name}.tex" > "${name}.log" 2>&1) || true

    if [[ -f "$PDF_DIR/${name}.pdf" ]]; then
        echo "    -> ${PDF_DIR}/${name}.pdf"
        rm -f "$PDF_DIR/${name}.aux" "$PDF_DIR/${name}.tex" "$PDF_DIR/${name}.log"
    else
        echo "    WARNING: ${name} failed — see ${PDF_DIR}/${name}.log"
    fi
done

echo ""
echo "Done. PDFs are in ${PDF_DIR}/"
echo "Use \\input{} lines in your main .tex file:"
for f in tex/*.tex; do
    echo "  \\input{${f}}"
done
