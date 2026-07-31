import os

target_file = r'D:\exoplanet\docs\academic_phrases_detailed.md'

md_content = """

## 9. TESS İleri Düzey Makale Şablonları (Context-Aware Paragraph Templates)

Bu bölüm, `toi3492_characterization.tex` gibi istatistiksel analizlerin, model karışımlarının (model mixtures) ve negatif/kısıtlı sonuçların (null-results) raporlandığı ileri düzey TESS makaleleri için hazırlanmış **paragraf seviyesinde** akademik yapı bloklarıdır. 

Script ile çekilmiş bağlamsız cümlelerin aksine, bu yapı blokları mantıksal geçişler (transitions), savunmacı yazım (defensive writing) ve argüman kurguları içerir. Köşeli parantez içindeki `[Değer]` kısımlarını kendi analizinize göre doldurabilirsiniz.

### 9.1 Giriş ve "Zorlu" Adayların Sunumu (Introduction & Unvalidated Candidates)

*Makalenizde, adayın bir türlü doğrulanamaması (unvalidated) durumunu hakeme dürüstçe ama bilimsel bir değer olarak sunmanız gerekir.*

> "The Transiting Exoplanet Survey Satellite (TESS) has fundamentally transformed our understanding of short-period exoplanets. However, robust validation of transit-like signals around evolved host stars remains a persistent challenge due to [Reason, e.g., elevated stellar jitter or blend scenarios]. In this work, we present a comprehensive photometric characterization of [Target Name], an unconfirmed transit-like candidate. Although a deep transit-like signal is unambiguously detected across [Number] TESS sectors, rigorous statistical and photometric screening—including [Method 1] and [Method 2]—reveals systematic sensitivities that currently preclude dynamical confirmation or statistical validation. We report these diagnostics to guide future high-resolution imaging and radial velocity follow-up efforts."

### 9.2 Veri İndirgeme ve Çoklu Pipeline Karşılaştırması (Multiple Reductions)

*Tek bir pipeline (sadece PDCSAP) yerine 4 farklı yöntemi (SAP, TPF vb.) karşılaştırdığınız bölümü savunmak için.*

> "To quantify the sensitivity of the transit geometry to the choice of flux extraction and systematics correction, we reduced the identical TESS observations through [Number] independent pipelines: [List Pipelines, e.g., PDCSAP, SAP+CBV, and TPF optimal-aperture]. Each reduction branch was independently required to satisfy strict acceptance gates, including [Requirement 1, e.g., $\geq 3\sigma$ per-sector depth significance] and [Requirement 2]. While all branches recovered the signal, we observed a [X]$\sigma$ geometric dispersion between the derived radii. Rather than arbitrarily selecting a single reduction, we preserve this between-reduction dispersion as a systematic uncertainty and propagate it in quadrature into our final model mixture."

### 9.3 MCMC Yörünge Modellemesi ve Hassasiyet Analizi (Sensitivity Analysis)

*Window size veya baseline polynomial derecelerine göre MCMC sonuçlarının nasıl değiştiğini anlatan, argüman kurucu paragraf yapısı.*

> "We employed a Markov Chain Monte Carlo (MCMC) framework using `emcee` to simultaneously constrain the transit geometry. To characterize the sensitivity of the derived parameters to our out-of-transit baseline assumptions, we constructed a preregistered grid exploring [Number] total-window durations crossed with [Number] baseline polynomial degrees. Under a strict model-adoption criterion—requiring any competing model to be excluded by at least [X] standard errors—no single window-and-polynomial combination emerged as uniquely favored. Consequently, we constructed a [X]-branch discrete model universe. This approach ensures that the full sensitivity to window duration, baseline polynomial, and cadence-mask choices is rigorously carried forward into our downstream analysis rather than being artificially collapsed."

### 9.4 Gaussian Process (GP) Kernel Testleri ve Sınır Şartı İhlalleri (Reporting Failures)

*GP denediğinizi ama istatistiksel sınırları (stationarity, mask-interaction) geçemediğini savunmacı (defensive) bir dille raporlama tekniği.*

> "Residual temporal correlation in the out-of-transit light curve can significantly bias transit parameter estimation if treated purely as white noise. To mitigate this, we evaluated [Number] Gaussian-process (GP) kernel families—specifically [Kernel 1, Kernel 2, and Kernel 3]—using a leave-one-sector-out (LOSO) cross-validation scheme. All correlated-noise kernels yielded strict predictive improvements over the white-noise baseline ($\Delta\mathrm{ELPD} = [Value] \pm [Value]$). However, despite this predictive gain, none of the kernels simultaneously satisfied all preregistered predictive, boundary-stability, and mask-interaction gates. As a result, the correlated-kernel screening concludes with a stationarity failure, compelling us to rely on a heavily diagnosed white-noise joint fit while explicitly acknowledging its limitations at the transit ingress/egress timescales."

### 9.5 Yanlış-Pozitif (False Positive) ve İkincil Tutulma (Secondary Eclipse)

*Odd/even veya secondary eclipse analizlerinin sonucunun negatif veya yetersiz çıkmasını (inconclusive) profesyonelce ifade etme.*

> "We executed a suite of diagnostic tests to identify obvious false-positive scenarios, including odd/even transit depth consistency and secondary eclipse searches. Independent robust median measurements of the odd and even transits yielded depths of $[Value] \pm [Error]$ ppm and $[Value] \pm [Error]$ ppm, respectively, showing no statistically significant discrepancy ($[X]\sigma$). Similarly, a fixed-duration search at orbital phase 0.5 revealed no significant secondary eclipse feature ($[X]\sigma$). While these metrics do not identify a clear false-positive source, we stress that they do not constitute a full statistical validation, as calibrated relative-depth sensitivity limits under a fully marginalized noise model remain unavailable for this target."

### 9.6 Sonuç ve Gelecek Gözlem Çağrısı (Conclusions & Future Work)

*Makalenin kapanışında, eldeki tüm analizlerin limitlerini belirtip neden daha fazla veriye ihtiyaç duyulduğunu (RV, High-res spectroscopy) savunan yapı.*

> "In summary, TOI-[XXXX] presents a persistent and deep transit-like signal across multiple TESS sectors. Our exhaustive photometric characterization demonstrates that the signal withstands basic false-positive vetting and is recovered across multiple independent extraction pipelines. Nevertheless, formal sector-depth heterogeneity and the inability of stationary correlated-noise models to fully capture the transit-timescale systematics preclude us from adopting a definitive native-cadence posterior. TOI-[XXXX] thus remains an unvalidated candidate. Unlocking its true nature will unequivocally require [Method 1, e.g., PRF-level localization], [Method 2, e.g., high-resolution adaptive optics imaging], and dedicated epoch radial velocity monitoring to overcome the current photometric ambiguities."
"""

with open(target_file, 'a', encoding='utf-8') as f:
    f.write(md_content)

print("Intelligent templates appended successfully.")
