# tools/tokenize_colors.py
import re
import sys
from collections import Counter

MAP = {
    "#1e2328": "var(--bg)",
    "#252b33": "var(--surface)",
    "#2d343e": "var(--surface-raised)",
    "#1f252c": "var(--surface-sunken)",
    "#22272e": "var(--surface-sunken)",
    "#1c2128": "var(--surface-sunken)",
    "#2f3640": "var(--border)",
    "#3d454d": "var(--border)",
    "#3a414c": "var(--border)",
    "#4a5568": "var(--border)",
    "#4a5563": "var(--border)",
    "#e6edf3": "var(--text)",
    "#c9d1d9": "var(--text)",
    "#8b949e": "var(--text-muted)",
    "#6e7681": "var(--text-muted)",
    "#c4c3c3": "var(--text-muted)",
    "#a79f9f": "var(--text-muted)",
    "#8b3d4a": "var(--primary)",
    "#7a3540": "var(--primary-hover)",
    "#f85149": "var(--danger)",
    "#dc2626": "var(--danger)",
    "#6edb8f": "var(--success)",
    "#16a34a": "var(--success)",
    "#122a1a": "var(--success-bg)",
    "#0d201a": "var(--success-bg)",
    "#153027": "var(--success-bg)",
    "#60b8f0": "var(--info)",
    "#0d2035": "var(--info-bg)",
    "#f0c060": "var(--warning)",
    "#3d3320": "var(--warning-bg)",
    "#30291c": "var(--warning-bg)",
    "#fb8500": "var(--orange)",
    "#d29fe2": "var(--purple)",
}

# 6-digit hex only; the lookbehind skips HTML entities like &#128269;
HEX = re.compile(r"(?<!&)#[0-9a-fA-F]{6}\b")


def main(paths):
    leftover = Counter()
    for path in paths:
        with open(path, encoding="utf-8") as f:
            src = f.read()

        def sub(m):
            key = m.group(0).lower()
            if key in MAP:
                return MAP[key]
            leftover[key] += 1
            return m.group(0)

        out = HEX.sub(sub, src)
        with open(path + ".bak", "w", encoding="utf-8") as f:
            f.write(src)
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"updated {path}")

    print("\nStill hard-coded (review manually):")
    for color, n in leftover.most_common():
        print(f"{n:4}  {color}")


if __name__ == "__main__":
    main(sys.argv[1:])