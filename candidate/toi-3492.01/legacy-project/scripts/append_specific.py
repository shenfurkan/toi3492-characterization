import json
import re

input_file = r'D:\exoplanet\outputs\extracted_phrases.json'
target_file = r'D:\exoplanet\docs\academic_phrases_detailed.md'

with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

keywords = ['tess', 'spoc', 'pdcsap', 'mcmc', 'gaussian process', 'false positive', 'bls', 'validation', 'pipeline', 'transit depth', 'light curve']
filtered = []

for item in data:
    text = item['text']
    text_lower = text.lower()
    if 50 < len(text) < 400 and any(k in text_lower for k in keywords):
        filtered.append(text.strip().replace('\n', ' '))

filtered = list(set(filtered))
filtered.sort(key=len)
selected = filtered[:40] if len(filtered) > 40 else filtered

md_content = '\n\n### 8. TESS Veri İndirgeme ve İstatistiksel Doğrulama (Data Reduction & Validation)\n\n'
md_content += '> *Özellikle TOI-3492 gibi TESS adaylarının ışık eğrisi analizi (SPOC, PDCSAP), MCMC yörünge modellemesi, Gaussian Process ve False-Positive testleri üzerine makalenize (TOI-3492_characterization) birebir uyumlu olacak özelleştirilmiş kalıplar.*\n\n'

for s in selected:
    md_content += f'- > "{s}"\n\n'

with open(target_file, 'a', encoding='utf-8') as f:
    f.write(md_content)

print("TESS specific phrases appended.")
