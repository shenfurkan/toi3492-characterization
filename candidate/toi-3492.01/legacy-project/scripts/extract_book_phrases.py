import os
import sys
import re
import json
import random

sys.stdout.reconfigure(encoding='utf-8')

try:
    from pypdf import PdfReader
except ImportError:
    print("pypdf not found.")
    exit(1)

TARGET_FILE = r"D:\exoplanet\AstrophysicsResources\The Exoplanet Handbook, 2nd Edition -- Perryman, Michael (author) -- 2, 2018 aug 25 -- New York _ Cambridge University Press -- 9781108304160 -- 4e2c538aeb60b60e0a28bb093c2ea3bc -- Anna’s Archive.pdf"
OUTPUT_FILE = r"D:\exoplanet\outputs\book_phrases.md"

# Textbook/theoretical style phrase starters
PHRASE_STARTERS = [
    r"it is evident that\b", r"this implies that\b", r"as derived in\b", 
    r"the fundamental principle\b", r"can be expressed as\b", r"yields the following\b", 
    r"provides a theoretical framework\b", r"in the context of\b", r"it can be shown that\b",
    r"can be written as\b", r"where we have assumed\b", r"this leads to\b",
    r"a straightforward consequence\b", r"by substituting\b", r"assuming that\b",
    r"it follows that\b", r"we can define\b", r"this approach allows\b",
    r"the underlying mechanism\b", r"can be approximated by\b"
]

pattern = re.compile(r'(' + '|'.join(PHRASE_STARTERS) + r')', re.IGNORECASE)

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\([A-Za-z\s\.,&]+ \d{4}[a-z]?\)', '', text)
    text = text.strip()
    return text

def extract_book_phrases():
    extracted = []
    
    if not os.path.exists(TARGET_FILE):
        print(f"File not found: {TARGET_FILE}")
        return
        
    print(f"Processing handbook: {TARGET_FILE}")
    try:
        reader = PdfReader(TARGET_FILE)
        num_pages = len(reader.pages)
        # Scan every 3rd page to speed up and avoid huge memory usage, up to 900 pages
        pages_to_scan = list(range(10, num_pages, 3))
        
        text = ""
        for i in pages_to_scan:
            try:
                page_text = reader.pages[i].extract_text()
                if page_text:
                    text += page_text + " "
            except Exception:
                pass
                
        text = clean_text(text)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        for sentence in sentences:
            if 50 < len(sentence) < 400:
                if pattern.search(sentence):
                    extracted.append(sentence.strip().replace("\n", " "))
                    
    except Exception as e:
        print(f"Failed to process book: {e}")
        return

    # Deduplicate
    unique_sentences = list(set(extracted))
    unique_sentences.sort(key=len)
    
    # Generate Markdown
    md_content = "\n\n### 6. Kitap ve Teori Anlatımı (Expository & Theoretical Framework)\n\n"
    md_content += "> *Bu kalıplar, \"The Exoplanet Handbook (2nd Edition)\" kitabının teorik altyapı sunan paragraflarından otomatik olarak çekilmiştir. Makalenizin özellikle giriş (Introduction) bölümünde fiziksel arka planı anlatırken kullanılabilir.*\n\n"

    # Select best 50
    selected = unique_sentences[:60] if len(unique_sentences) > 60 else unique_sentences
    for s in selected:
        md_content += f"- > \"{s}\"\n\n"

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    print(f"Extraction complete! Found {len(extracted)} valid theoretical phrases. Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    extract_book_phrases()
