# Potansiyel Makale Adayı: TOI-7698

> **Kapsam notu:** Bu belge TOI-7698 ve diğer gelecek hedefler icin ayri bir
> arastirma planidir; TOI-3492.01 makalesinin release, sonuc veya claim-gate
> dokumani degildir. Asagidaki katalog ve rekabet bilgileri 2026-07-12
> tarihindeki anlik durumu yansitir ve uygulanmadan once NASA Exoplanet Archive,
> ExoFOP, arXiv ve Gaia uzerinden yeniden dogrulanmalidir.

Son araştırma tarihi: 2026-07-12 (yeniden doğrulama gerekli)

## Karar

Birinci tercih:

**TOI-7698 / TIC 241577487**

Önerilen çalışma:

> TOI-7698'in üç küçük gezegen adayının bağımsız geri kazanımı,
> TOI-7698.03 periyot alias'ının çözülmesi, kaynak lokalizasyonu, sistem
> mimarisi ve gerekli takip verileri elde edilirse istatistiksel validasyonu.

Validation tamamlanmadan kullanılabilecek makale başlığı:

> Photometric Vetting and Architecture of the Three-Candidate TOI-7698 System

Validation tamamlanırsa kullanılabilecek başlık:

> TOI-7698: A Compact Three-Planet System Straddling the Radius Valley

Bu hedef veya bir makale PhD kabulünü garanti etmez. Ama TOI-3492 çalışmasına
göre daha güçlü bir sistem bilimi, takip gözlemi, yöntem geliştirme ve
işbirliği fırsatı sunmaktadır.

## Katalog Özeti

12 Temmuz 2026 tarihli NASA Exoplanet Archive ve ExoFOP verileri:

| Aday | Periyot | Yarıçap | Transit derinliği | Katalog S/N |
|---|---:|---:|---:|---:|
| TOI-7698.03 | 1.2377157 gün | 1.54 R_Earth | 240 ppm | 17.8 |
| TOI-7698.01 | 4.5701356 gün | 1.67 R_Earth | 341 ppm | 13.9 |
| TOI-7698.02 | 14.7157672 gün | 2.20 R_Earth | 553 ppm | 14.9 |

Yıldız özellikleri:

- TIC: `241577487`
- Gaia DR3: `2505430727869990528`
- TESS magnitude: `9.818`
- Gaia G: `10.282`
- Uzaklık: yaklaşık `108-110 pc`
- Etkin sıcaklık: `5353 K`
- TIC yarıçapı: yaklaşık `1.00 R_Sun`
- TIC kütlesi: yaklaşık `0.93 M_Sun`
- TIC metalikliği: yaklaşık `[Fe/H] = -0.23`
- TIC contamination ratio: `0.00257`
- Güncel disposition: üç sinyal için de `PC`

TESS sektörleri:

- Sector 3
- Sector 30
- Sector 70
- Sector 97

Arşivde 30 dakika, 600 saniye, 200 saniye ve bir sektörde 120 saniye
cadence ürünleri bulunmaktadır. Gözlemler 2018-2025 arasında yaklaşık yedi
yıllık bir taban çizgisi sağlamaktadır.

## Bilimsel Değer

Üç aday aynı yıldız altında farklı yarıçap ve ışınım rejimlerini örneklemektedir:

- `.03`: yaklaşık 1.54 R_Earth, çok sıcak iç gezegen adayı.
- `.01`: yaklaşık 1.67 R_Earth, sıcak süper-Dünya adayı.
- `.02`: yaklaşık 2.20 R_Earth, sıcak sub-Neptün adayı.

Sistem şu konular için kullanılabilir:

- radius valley;
- photoevaporation;
- core-powered mass loss;
- aynı yıldız altında yarıçap-ışınım karşılaştırması;
- kompakt sistem oluşumu ve evrimi;
- ek gezegen araması ve detection completeness;
- uzun taban çizgisinde ephemeris ve transit zamanı kararlılığı.

Bu hikaye, tek bir büyük adayın fotometrik karakterizasyonundan daha güçlüdür.

## Görünür Özgünlük ve Rekabet

2026-07-12 tarihinde yapılan kontroller:

- ExoFOP'ta imaging kaydı: `0`
- ExoFOP'ta spectroscopy kaydı: `0`
- ExoFOP'ta ground time-series kaydı: `0`
- ExoFOP'ta uploaded file: `0`
- ExoFOP'ta CTOI: `0`
- ArXiv `TOI-7698` tam metin araması: sonuç yok
- ArXiv `TIC 241577487` tam metin araması: sonuç yok
- OpenAlex başlık/özet araması: sonuç yok

Bu kontroller yalnız görünür ve indekslenmiş bir makale bulunmadığını gösterir.
Başka bir grubun devam eden veya henüz açıklanmamış bir çalışması olmadığını
garanti etmez. Büyük emek harcamadan önce TESS/TFOP topluluğuyla koordinasyon
kurulmalıdır.

## Ana Özgün Problem: TOI-7698.03 Periyot Alias'ı

ExoFOP notu:

> period could be 2x; odd events clearer than even; low SNR

Test edilecek iki temel hipotez:

- `P = 1.2377157 gün`
- `P = 2.4754313 gün`

Gerekli analizler:

1. Her sektörde bağımsız BLS ve TLS araması.
2. Odd/even olayların ayrı modellenmesi.
3. `P` ve `2P` modellerinin likelihood veya evidence karşılaştırması.
4. Her olayın piksel ve aperture düzeyinde doğrulanması.
5. Transit süreleri ile stellar-density tutarlılığının karşılaştırılması.
6. Her iki periyotta beklenen fakat gözlenmeyen olayların kontrolü.
7. Sector 97 200-s verisiyle ingress/egress karşılaştırması.
8. Difference-image kaynak lokalizasyonu.
9. Gerekirse CHEOPS veya yeni transit gözlemiyle alias'ın kesin çözümü.

Alias'ın güvenilir biçimde çözülmesi tek başına özgün ve yayımlanabilir bir
sonuç olabilir, fakat diğer iki adayın vetting'iyle sistem makalesine
dönüştürülmelidir.

## Kritik Gaia Uyarısı

Gaia DR3 değerleri:

- RUWE: `0.863`
- `non_single_star = 0`
- `duplicated_source = false`
- `ipd_frac_multi_peak = 0`
- RV transit sayısı: `27`
- RV zaman tabanı: yaklaşık `912 gün`
- `rv_amplitude_robust = 4.234 km/s`
- RV sabitliği p-değeri: `0.0094`

`rv_amplitude_robust` bir yörünge yarı-genliği veya tek başına ikili yıldız
kanıtı değildir. Ancak aday gezegenler için beklenen RV genlikleri yalnızca
yaklaşık `1.4-1.9 m/s` olduğundan bu değer önemli bir uyarıdır.

İlk dış gözlem iki veya üç epoch reconnaissance spectrum olmalıdır. Amaç:

- SB1 veya SB2 sistemini dışlamak;
- km/s ölçeğinde RV değişimini kontrol etmek;
- `Teff`, `log g`, `[Fe/H]` ve `v sin i` ölçmek;
- yıldız aktivitesini değerlendirmek.

Yeni spektrumlarda km/s değişimi veya çift çizgi doğrulanırsa klasik küçük
gezegen validation projesi durdurulmalı veya hiyerarşik sistem çalışmasına
dönüştürülmelidir.

## Gaia Alanı ve Kontaminasyon

Hedefin Gaia astrometrisi genel olarak temizdir. Yaklaşık 1 arcmin içindeki en
parlak katalog komşusu hedefe göre yaklaşık 10 magnitude daha sönüktür. Buna
rağmen transit derinlikleri yalnızca 240-553 ppm olduğu için düşük katalog
contamination değeri resmi kaynak lokalizasyonunun yerini tutmaz.

Gerekli kontroller:

- bütün Gaia kaynakları için renk-bağımlı TESS flux ratio;
- kaynak bazında gereken eclipse depth;
- her sektör için gerçek aperture maskesi;
- difference-image centroid posterioru;
- TESS PRF likelihood;
- proper-motion ve eski survey görüntüleri;
- speckle veya AO contrast curve.

## Makale Seviyeleri

### Seviye A: Yalnız Public Data

Ürünler:

- dört sektörün bağımsız ekstraksiyonu;
- üç sinyalin sektör bazlı geri kazanımı;
- `.03` alias çözümü;
- difference-image ve Gaia kaynak analizi;
- stellar SED/isochrone posterioru;
- ortak transit modeli;
- event-level transit zamanları;
- dinamical stability;
- injection/recovery ile ek gezegen araması;
- machine-readable candidate status ve reproducibility release.

Bu seviye aday-mimarisi preprint'i üretebilir. Validation veya confirmation
iddiası desteklemez.

### Seviye B: Imaging ve Reconnaissance Spectrum

Ek gereksinimler:

- speckle veya AO contrast curve;
- en az 2-3 epoch reconnaissance spectroscopy;
- calibrated PRF localization;
- multiplicity-aware population FPP;
- Gaia ve archival-imaging proper-motion analizi;
- bütün adaylar için aynı yıldız üzerinde transit tutarlılığı.

Bu seviye başarılı olursa istatistiksel validation makalesi mümkün olabilir.
PhD başvurusu açısından hedeflenen minimum güçlü seviye budur.

### Seviye C: Hassas RV veya CHEOPS

Ek hedefler:

- yaklaşık `1.4-1.9 m/s` sinyaller için HARPS-N, ESPRESSO veya eşdeğer RV;
- `.03` alias ve transit şekli için CHEOPS fotometrisi;
- kütle, yarıçap ve bulk-density sonuçları;
- aynı sistem içinde radius-valley karşılaştırması.

Bu seviye yüksek bilimsel etkili bir sistem makalesine dönüşebilir, ancak
güçlü bir gözlemevi işbirliği gerektirir.

## İlk Yedi Günlük Kill Testi

Büyük projeye başlamadan önce:

1. QLP, SPOC ve TESS-SPOC ürünlerini envanterle.
2. TESSCut ile dört sektörün piksel küplerini indir.
3. Üç sinyali her sektörde bağımsız ara.
4. Birden fazla aperture ve detrending yöntemi dene.
5. `.03` için `P` ve `2P` karşılaştırması yap.
6. Odd/even, secondary, centroid ve difference-image testlerini çalıştır.
7. Gaia komşuları için gereken eclipse depth'i hesapla.
8. Event-level transit zamanlarını çıkar.
9. Stellar SED ve isochrone ön analizini yap.
10. Tek sayfalık go/no-go raporu üret.

## Durdurma Koşulları

Şunlardan biri çıkarsa hedefe aylar harcanmamalıdır:

- Sinyaller yalnız sector 97'de görünüyorsa.
- Sinyal aperture veya detrending seçimine güçlü biçimde bağımlıysa.
- Difference image başka bir Gaia kaynağına gidiyorsa.
- `.03` odd/even ayrımı eclipsing binary gösteriyorsa.
- Transit süreleri ortak yıldız yoğunluğuyla bağdaşmıyorsa.
- Gaia RV değişimi yeni spektrumlarda km/s seviyesinde doğrulanıyorsa.
- Aynı hedef üzerinde yayıma yakın aktif bir ekip bulunuyorsa.
- Contrast imaging ve reconnaissance spectrum işbirliği bulunamıyorsa.

## Yedek Aday: TOI-7715

Kimlik:

- TOI-7715 / TIC 200001699
- Uzaklık: yaklaşık `57 pc`
- TESS magnitude: `10.640`
- Yıldız sıcaklığı: yaklaşık `4006 K`

Adaylar:

| Aday | Periyot | Yarıçap | Transit derinliği |
|---|---:|---:|---:|
| TOI-7715.01 | 0.3236317 gün | 1.54 R_Earth | 488 ppm |
| TOI-7715.02 | 6.8896201 gün | 3.16 R_Earth | 2203 ppm |

Avantajları:

- Bir ultra-short-period aday ve bir sub-Neptün adayı.
- Yakın yıldız.
- Tahmini RV genlikleri yaklaşık `3.8` ve `4.6 m/s`.
- Dış adayın 2203 ppm transiti yer fotometrisine daha uygundur.
- ExoFOP'ta henüz imaging, spectroscopy veya time-series görünmemektedir.

Riskleri:

- Yalnız sector 98 mevcuttur.
- `.02` için olası odd/even problemi not edilmiştir.
- RUWE yaklaşık `1.49`.
- Yaklaşık 10 arcsec çevresinde transit sinyalini etkileyebilecek Gaia
  kaynakları vardır.
- Gaia `rv_amplitude_robust` yaklaşık `6.08 km/s`, ancak sabitlik testi
  `p = 0.117` olduğundan tek başına anlamlı değildir.

TOI-7698 ilk feasibility turunda elenirse TOI-7715 ikinci hedef olarak
değerlendirilmelidir.

## Elenen veya İşbirliği Gerektiren Hedefler

- **TOI-6650:** Dört sinyalli, bilimsel olarak güçlü sistem; ExoFOP'ta 107
  dosya, 31 spectroscopy, 5 imaging ve 6 time-series kaydı nedeniyle aktif
  ekip rekabeti çok yüksek.
- **TOI-5952:** 121 dosya, 50 spectroscopy ve 13 time-series kaydı; bağımsız
  sahiplenme yerine mevcut ekiple işbirliği gerekir.
- **TOI-2411:** TOI-2411 b zaten valide edilmiştir ve sistem üzerine 2022 ve
  2024 yayınları bulunmaktadır.
- **TOI-4296:** Yeni adaylar ilginç olsa da 53 dosya ve aktif takip izi vardır;
  eski `.01` sinyali false alarm olarak işaretlidir.
- **TOI-7665:** Mevcut imaging ve daha eski CTOI katkısı vardır; katkı sahipleri
  ile işbirliği kurulmadan yürütülmemelidir.

## PhD Başvurusuna Katkı İçin Başarı Tanımı

En güçlü çıktı kombinasyonu:

- birinci yazar hakemli makale;
- açık, test edilmiş ve tekrar kullanılabilir pipeline;
- telescope proposal veya observing request yazarlığı;
- spectroscopy/imaging ekibiyle gerçek işbirliği;
- ExoFOP'a belgelenmiş takip katkısı;
- kişisel katkının makalede ve referans mektuplarında açık olması;
- uygun araştırma grubundan güçlü referans mektubu.

Bir arXiv preprint tek başına kabul garantisi sağlamaz. TOI-7698 ancak public
data egzersizinin ötesine geçip takip gözlemleri içeren sistem çalışmasına
dönüştürülürse başvuru açısından yüksek değer üretir.

## Resmi Kaynaklar

- TOI-7698 ExoFOP:
  https://exofop.ipac.caltech.edu/tess/target.php?toi=7698
- TOI-7698 ExoFOP JSON:
  https://exofop.ipac.caltech.edu/tess/target.php?id=241577487&json
- TOI-7715 ExoFOP:
  https://exofop.ipac.caltech.edu/tess/target.php?toi=7715
- NASA Exoplanet Archive TOI tablosu:
  https://exoplanetarchive.ipac.caltech.edu/cgi-bin/TblView/nph-tblView?app=ExoTbls&config=TOI
- NASA TOI kolon tanımları:
  https://exoplanetarchive.ipac.caltech.edu/docs/API_TOI_columns.html
- MAST TESS arşivi:
  https://archive.stsci.edu/missions-and-data/tess
- Gaia Archive:
  https://gea.esac.esa.int/archive/
- ArXiv:
  https://arxiv.org/

## Durum

**Seçim:** TOI-7698 birinci tercih.
**Yedek:** TOI-7715.
**Sonraki kapı:** Yedi günlük public-data feasibility ve kill testi.
**Validation için zorunlu dış kapı:** Reconnaissance spectroscopy ve contrast
imaging.
