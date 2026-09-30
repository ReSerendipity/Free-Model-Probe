import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

names = {
    0: "Qwen3.5-397B-A17B", 1: "Qwen3.6-35B-A3B", 2: "Qwen3-Coder-480B-A35B-Instruct",
    3: "Qwen3-Coder-30B-A3B-Instruct", 4: "DeepSeek-V4-Pro", 5: "DeepSeek-V4-Flash-0731",
    6: "GLM-5.2", 7: "GLM-5", 8: "GLM-4.7", 9: "Kimi-K2.7-Code", 10: "Kimi-K3", 11: "Step-3.7-Flash"
}

def clean(s):
    s = re.sub(r'<[^>]+>', '', s)
    s = s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&#x27;', "'").replace('&quot;', '"')
    return s.strip()

for idx in [0, 1, 4, 5, 6, 7, 8, 9, 10, 11]:
    path = rf"C:\Users\Doro\.openclaw-autoclaw\workspace\.cluster\readme_{idx}.md"
    raw = open(path, encoding='utf-8', errors='replace').read()
    print(f"\n########## {names[idx]} (readme_{idx}) ##########")
    # find tables
    tables = re.findall(r'<table.*?</table>', raw, re.S)
    if not tables:
        # markdown tables
        md_tables = re.findall(r'\|[^\n]+\|\n\|[\s:\-|]+\|\n(?:\|[^\n]+\|\n?)+', raw)
        for t in md_tables:
            print("--- MD TABLE ---")
            print(t)
        # also grep lines with benchmark names
        for kw in ["SWE-bench", "HumanEval", "LiveCodeBench", "Terminal Bench", "Terminal-Bench", "AIME"]:
            for line in raw.split('\n'):
                if kw.lower() in line.lower() and ('|' in line or '%' in line):
                    print(f"LINE: {line.strip()[:300]}")
        continue
    for ti, t in enumerate(tables):
        rows = re.findall(r'<tr.*?</tr>', t, re.S)
        out = []
        for r in rows:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S)
            cells = [clean(c) for c in cells]
            if cells:
                out.append(cells)
        # print only tables that contain benchmark-like keywords
        joined = ' | '.join(str(x) for row in out for x in row)
        if re.search(r'SWE-bench|HumanEval|LiveCodeBench|Terminal|AIME|MCP|Codeforces|Bash', joined, re.I):
            print(f"--- TABLE {ti} ({len(out)} rows) ---")
            for row in out:
                print(' | '.join(row))
