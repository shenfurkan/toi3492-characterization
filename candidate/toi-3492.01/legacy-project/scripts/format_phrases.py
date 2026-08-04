import json
import random

input_file = r"D:\exoplanet\outputs\extracted_phrases.json"
output_file = r"D:\exoplanet\outputs\new_phrases_detailed.md"

categories = {
    "1. Özet ve Giriş (Abstract & Introduction)": ["in this paper", "we present", "we propose", "the objective of", "this study", "here we report"],
    "2. Gözlemler ve Veri (Observations & Data Collection)": ["we observe", "the observations", "we used", "we measure", "we perform", "observations were"],
    "3. Yöntem ve Analiz (Methods & Analysis)": ["we model", "in order to", "we investigate", "we constrain", "we analyzed", "to investigate", "we estimate", "to determine"],
    "4. Bulgular ve Sonuçlar (Results & Findings)": ["we report", "we find that", "the results show", "our results", "we derived", "as shown in", "our analysis"],
    "5. Tartışma ve Karar (Discussion & Conclusion)": ["we conclude", "this suggests", "furthermore", "we note that", "we demonstrate"]
}

try:
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception as e:
    print(f"Error loading JSON: {e}")
    exit(1)

# Group by category
grouped = {k: [] for k in categories.keys()}

for item in data:
    text = item["text"]
    text_lower = text.lower()
    
    # Try to assign to a category
    for cat, starters in categories.items():
        if any(s in text_lower for s in starters):
            # Avoid too short or too long
            if 50 < len(text) < 400:
                grouped[cat].append(text)
            break

# Generate Markdown
md_content = "\n\n## 7. Genişletilmiş Makale Kalıpları Arşivi (1700+ Taramadan Detaylı Seçki)\n\n"
md_content += "> *Aşağıdaki kalıplar, klasörünüzdeki PDF'lerin otomatik taranmasıyla elde edilmiş ve makale yazım aşamalarınızda doğrudan ilham/referans alabilmeniz için son derece detaylı bir şekilde listelenmiştir.*\n\n"

for cat, sentences in grouped.items():
    md_content += f"### {cat}\n\n"
    # deduplicate
    unique_sentences = list(set(sentences))
    
    # Sort them by length to have a nice flow
    unique_sentences.sort(key=len)
    
    # Pick up to 50 best ones for extreme detail
    selected = unique_sentences[:80] if len(unique_sentences) > 80 else unique_sentences
    
    for s in selected:
        # cleanup some common weird artifacts
        s = s.replace("\n", " ").strip()
        md_content += f"- > \"{s}\"\n\n"

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(md_content)

print(f"Detailed formatted markdown saved to {output_file}")

