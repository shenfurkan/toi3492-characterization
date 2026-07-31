import os

filepath = r'D:\exoplanet\docs\academic_phrases_detailed.md'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    # Intro
    'İstediğin gibi klasördeki kilit TESS keşif makalelerini (Grunblatt et al., Chontos et al., Wittenmyer et al., Saunders et al., Hey et al. vb.) **tek tek açıp okuyarak**, makalenin her bir alt bölümü için kullanabileceğin "kopyala-yapıştır" formatında akademik kalıpları (boilerplate) çıkardım.': 'By thoroughly reading the key TESS discovery papers in your folder (Grunblatt et al., Chontos et al., Wittenmyer et al., Saunders et al., Hey et al., etc.), I extracted "copy-paste" formatted academic boilerplate phrases tailored for each subsection of your manuscript.',
    'Özellikle TESS fotometrisi, yer tabanlı RV (Dikine Hız) gözlemleri, MCMC tabanlı yörünge modellemesi, sahte pozitif (false-positive) elemesi ve tartışma kısımları gibi standart bölümleri bu kalıpları kullanarak intihal kaygısı olmadan, kendi verilerine göre uyarlayarak yazabilirsin.': 'You can use these templates to draft standard sections—such as TESS photometry, ground-based RV observations, MCMC orbital modeling, false-positive vetting, and discussions—by adapting them to your own data without concerns of plagiarism.',
    
    # Sections 1-6
    '(Özet ve Giriş)': '',
    '**Keşif Sunumu:**': '**Discovery Presentation:**',
    "**Bağlam (Neden Önemli? / TESS'in Rolü):**": "**Context (Significance & TESS's Role):**",
    '(Gözlemler)': '',
    '**TESS Fotometrisi:**': '**TESS Photometry:**',
    '**Yer Tabanlı Fotometri (Örn. LCOGT / PEST vs.):**': '**Ground-Based Photometry (e.g., LCOGT / PEST, etc.):**',
    '**Yüksek Çözünürlüklü Dikine Hız (RV) Gözlemleri:**': '**High-Resolution Radial Velocity (RV) Observations:**',
    '**Yakın Çift Yıldız (Companion) Taraması / Arka Plan Kontrolü:**': '**Close Companion Search / Background Check:**',
    '(Yıldız Analizi)': '',
    '**Tayf Analizi (Spectroscopy):**': '**Spectroscopic Analysis:**',
    '**İzokron Fitleri (Isochrones) ve SED:**': '**Isochrone Fits and SED:**',
    '(Yörünge ve Geçiş Modellemesi)': '',
    '**Ortak (Joint) Transit, RV ve RM Fiti:**': '**Joint Transit, RV, and RM Fit:**',
    '**Priors (Ön Bilgiler) ve Hata Payları:**': '**Priors and Uncertainties:**',
    '(Tartışma)': '',
    '**Atmosferik Gözlem (JWST / TSM) İhtimali:**': '**Atmospheric Characterization Prospects (JWST / TSM):**',
    '**Yörünge Bozunumu (Orbital Decay / Tidal Realignment):**': '**Orbital Decay / Tidal Realignment:**',
    
    # Section 7
    '## 7. Genişletilmiş Makale Kalıpları Arşivi (1700+ Taramadan Detaylı Seçki)': '## 7. Extended Academic Phrases Archive (Detailed Selection from 1700+ Scans)',
    '> *Aşağıdaki kalıplar, klasörünüzdeki PDF\'lerin otomatik taranmasıyla elde edilmiş ve makale yazım aşamalarınızda doğrudan ilham/referans alabilmeniz için son derece detaylı bir şekilde listelenmiştir.*': '> *The phrases below were automatically extracted from the PDFs in your folder, cataloged in detail to provide direct inspiration and reference during your drafting process.*',
    '### 1. Özet ve Giriş (Abstract & Introduction)': '### 1. Abstract & Introduction',
    '### 2. Gözlemler ve Veri (Observations & Data Collection)': '### 2. Observations & Data Collection',
    '### 3. Yöntem ve Analiz (Methods & Analysis)': '### 3. Methods & Analysis',
    '### 4. Bulgular ve Sonuçlar (Results & Findings)': '### 4. Results & Findings',
    '### 5. Tartışma ve Karar (Discussion & Conclusion)': '### 5. Discussion & Conclusion',
    
    # Section 6 (Book)
    '### 6. Kitap ve Teori Anlatımı (Expository & Theoretical Framework)': '### 6. Expository & Theoretical Framework (Books & Theory)',
    '> *Bu kalıplar, "The Exoplanet Handbook (2nd Edition)" kitabının teorik altyapı sunan paragraflarından otomatik olarak çekilmiştir. Makalenizin özellikle giriş (Introduction) bölümünde fiziksel arka planı anlatırken kullanılabilir.*': '> *These phrases were automatically extracted from the theoretical sections of "The Exoplanet Handbook (2nd Edition)". They are particularly useful for explaining physical backgrounds in your Introduction section.*',
    
    # Section 8
    '### 8. TESS Veri İndirgeme ve İstatistiksel Doğrulama (Data Reduction & Validation)': '### 8. TESS Data Reduction & Statistical Validation',
    '> *Özellikle TOI-3492 gibi TESS adaylarının ışık eğrisi analizi (SPOC, PDCSAP), MCMC yörünge modellemesi, Gaussian Process ve False-Positive testleri üzerine makalenize (TOI-3492_characterization) birebir uyumlu olacak özelleştirilmiş kalıplar.*': '> *Customized templates tailored specifically for your manuscript (TOI-3492_characterization), focusing on light curve analysis (SPOC, PDCSAP), MCMC orbital modeling, Gaussian Processes, and False-Positive vetting for TESS candidates.*',
    
    # Section 9
    '## 9. TESS İleri Düzey Makale Şablonları (Context-Aware Paragraph Templates)': '## 9. Advanced TESS Article Templates (Context-Aware Paragraph Templates)',
    'Bu bölüm, `toi3492_characterization.tex` gibi istatistiksel analizlerin, model karışımlarının (model mixtures) ve negatif/kısıtlı sonuçların (null-results) raporlandığı ileri düzey TESS makaleleri için hazırlanmış **paragraf seviyesinde** akademik yapı bloklarıdır.': 'This section contains **paragraph-level** academic building blocks designed for advanced TESS papers, such as `toi3492_characterization.tex`, where statistical analyses, model mixtures, and null-results must be rigorously reported.',
    "Script ile çekilmiş bağlamsız cümlelerin aksine, bu yapı blokları mantıksal geçişler (transitions), savunmacı yazım (defensive writing) ve argüman kurguları içerir. Köşeli parantez içindeki `[Değer]` kısımlarını kendi analizinize göre doldurabilirsiniz.": "Unlike context-free sentences extracted by scripts, these structural blocks include logical transitions, defensive writing, and argument framing. You can fill in the bracketed `[Value]` placeholders according to your own analysis.",
    '### 9.1 Giriş ve "Zorlu" Adayların Sunumu (Introduction & Unvalidated Candidates)': '### 9.1 Introduction & Presentation of "Challenging" Candidates (Unvalidated Candidates)',
    '*Makalenizde, adayın bir türlü doğrulanamaması (unvalidated) durumunu hakeme dürüstçe ama bilimsel bir değer olarak sunmanız gerekir.*': '*In your manuscript, you must present the unvalidated status of the candidate honestly to the referees, while emphasizing its scientific value.*',
    '### 9.2 Veri İndirgeme ve Çoklu Pipeline Karşılaştırması (Multiple Reductions)': '### 9.2 Data Reduction & Multiple Pipeline Comparison (Multiple Reductions)',
    '*Tek bir pipeline (sadece PDCSAP) yerine 4 farklı yöntemi (SAP, TPF vb.) karşılaştırdığınız bölümü savunmak için.*': '*To defend the section where you compare 4 different reduction methods (SAP, TPF, etc.) instead of relying on a single pipeline (PDCSAP).*',
    '### 9.3 MCMC Yörünge Modellemesi ve Hassasiyet Analizi (Sensitivity Analysis)': '### 9.3 MCMC Orbital Modeling & Sensitivity Analysis',
    '*Window size veya baseline polynomial derecelerine göre MCMC sonuçlarının nasıl değiştiğini anlatan, argüman kurucu paragraf yapısı.*': '*An argument-framing paragraph structure explaining how MCMC results vary depending on window size or baseline polynomial degrees.*',
    '### 9.4 Gaussian Process (GP) Kernel Testleri ve Sınır Şartı İhlalleri (Reporting Failures)': '### 9.4 Gaussian Process (GP) Kernel Tests & Boundary Violations (Reporting Failures)',
    '*GP denediğinizi ama istatistiksel sınırları (stationarity, mask-interaction) geçemediğini savunmacı (defensive) bir dille raporlama tekniği.*': '*A defensive reporting technique to explain that although GP was attempted, it failed to pass statistical boundaries (stationarity, mask-interaction).*',
    '### 9.5 Yanlış-Pozitif (False Positive) ve İkincil Tutulma (Secondary Eclipse)': '### 9.5 False Positive & Secondary Eclipse',
    '*Odd/even veya secondary eclipse analizlerinin sonucunun negatif veya yetersiz çıkmasını (inconclusive) profesyonelce ifade etme.*': '*Professionally expressing that the results of odd/even or secondary eclipse analyses were negative or inconclusive.*',
    '### 9.6 Sonuç ve Gelecek Gözlem Çağrısı (Conclusions & Future Work)': '### 9.6 Conclusions & Call for Future Observations (Conclusions & Future Work)',
    '*Makalenin kapanışında, eldeki tüm analizlerin limitlerini belirtip neden daha fazla veriye ihtiyaç duyulduğunu (RV, High-res spectroscopy) savunan yapı.*': '*A concluding structure that outlines the limitations of the current analysis and argues for the necessity of further data (RV, High-res spectroscopy).*'
}

for tr, en in replacements.items():
    content = content.replace(tr, en)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Translation to English complete.")
