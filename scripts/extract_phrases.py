import os
import sys
import re
import json
import traceback

sys.stdout.reconfigure(encoding='utf-8')

try:
    from pypdf import PdfReader
except ImportError:
    print("pypdf not found. Please install it using: pip install pypdf")
    exit(1)

# Directories to scan
TARGET_DIRS = [
    r"D:\exoplanet\literature",
    r"D:\exoplanet\papers"
]

OUTPUT_FILE = r"D:\exoplanet\outputs\extracted_phrases.json"

# Keywords/patterns indicating typical academic boilerplate
PHRASE_STARTERS = [
    r"in this paper\b", r"we present\b", r"we report\b", r"we find that\b",
    r"we observe\b", r"we conclude\b", r"the results show\b", r"our results\b",
    r"this suggests\b", r"furthermore\b", r"we model\b", r"the observations\b",
    r"in order to\b", r"we investigate\b", r"we constrain\b", r"we analyzed\b",
    r"we used\b", r"our analysis\b", r"this study\b", r"to investigate\b",
    r"we derived\b", r"as shown in\b", r"we propose\b", r"we demonstrate\b",
    r"the objective of\b", r"we note that\b", r"here we report\b",
    r"we perform\b", r"we estimate\b", r"we measure\b", r"to determine\b"
]

pattern = re.compile(r'(' + '|'.join(PHRASE_STARTERS) + r')', re.IGNORECASE)

def clean_text(text):
    # Remove excessive whitespace and linebreaks
    text = re.sub(r'\s+', ' ', text)
    # Remove citations like (Author et al. 2020)
    text = re.sub(r'\([A-Za-z\s\.,&]+ \d{4}[a-z]?\)', '', text)
    # Basic cleanup for formatting artifacts
    text = text.strip()
    return text

def extract_phrases():
    extracted = []
    
    for directory in TARGET_DIRS:
        if not os.path.exists(directory):
            print(f"Directory not found: {directory}")
            continue
            
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_path = os.path.join(root, file)
                    print(f"Processing: {pdf_path}")
                    try:
                        reader = PdfReader(pdf_path)
                        # Scanning up to 15 pages per paper to avoid going out of memory and to focus on main text
                        num_pages = len(reader.pages)
                        pages_to_scan = list(range(min(15, num_pages)))
                        if num_pages > 15:
                            pages_to_scan += [num_pages-2, num_pages-1]
                        
                        text = ""
                        for i in set(pages_to_scan):
                            try:
                                page_text = reader.pages[i].extract_text()
                                if page_text:
                                    text += page_text + " "
                            except Exception as e:
                                pass
                        
                        text = clean_text(text)
                        
                        sentences = re.split(r'(?<=[.!?])\s+', text)
                        
                        for sentence in sentences:
                            if len(sentence) > 30 and len(sentence) < 400: # reasonable sentence length
                                if pattern.search(sentence):
                                    extracted.append({
                                        "source": file,
                                        "text": sentence.strip()
                                    })
                                    
                    except Exception as e:
                        print(f"Failed to process {file}: {e}")
    
    # Save to JSON
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(extracted, f, indent=4, ensure_ascii=False)
        
    print(f"Extraction complete! Found {len(extracted)} phrases. Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    extract_phrases()
