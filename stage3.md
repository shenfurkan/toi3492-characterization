# TOI-3492.01 Üçüncü Aşama Tamamlama Planı

Son güncelleme: 2026-07-24

Belge durumu: `PROTOCOL_ONLY`

Gerçek-veri çalışma yetkisi: `CLOSED`

Kapsam onayı: 2026-07-23 tarihinde kullanıcı “devam et projeye diğer faza
geçelim yavaştan” talimatıyla Stage-3 kapsamını ve aşamalı ilerlemeyi onayladı.
Bu onay S3-00 ile S3-05 arasındaki hazırlık ve sentetik çalışmaları açar. S3-07
gerçek-veri çalışması için S3-06 sonunda ayrıca protokol özeti onayı gerekir.

## 1. Bu belgenin amacı

Bu belge TOI-3492.01 çalışmasının nasıl devam edeceğini somut ve sınırlı biçimde
tanımlar. Amaç eski Faz 6 veya Faz 6R sonucunu değiştirmek, beta sınırını
gevşetmek ya da istenen sonucu bulana kadar model denemek değildir.

Amaç şudur:

> Bu makalede TESS fotometrisinden çıkarılabilecek en kapsamlı ve güvenilir
> sonucu üretmek için, yetersiz kaldığı görülen gürültü-modeli aşamasını tek bir
> kontrollü yöntem-geliştirme süreciyle yeniden kurmak ve ardından makaleyi
> sonucun desteklediği düzeyde tamamlamak.

Bu makalenin tamamlanması, adayın mutlaka doğrulanmış gezegen çıkması demek
değildir. Analiz sonunda nesne hâlâ doğrulanmamış aday olabilir. Tamamlanma
ölçütü, bütün amaçlanan fotometrik kontrollerin geçerli biçimde kapanmasıdır.

## 2. Onay kuralı

Bu dosyanın oluşturulması yeni gerçek-veri fitine izin vermez.

Stage 3 aşağıdaki anlama gelen açık onayla 2026-07-23 tarihinde aktif oldu:

> “Stage 3 kapsamını, tek yöntem-geliştirme hakkını, sentetik kalibrasyon
> zorunluluğunu ve başarısızlık halinde yeni model aramama kuralını onaylıyorum.”

S3-06 ikinci onayından önce yapılabilecekler:

1. Mevcut dosyaları okumak ve hash envanteri çıkarmak.
2. Belge ve durum kayıtlarını eşitlemek.
3. Mevcut Faz 6 sonuçları üzerinde yeni fit içermeyen post-mortem analizi yapmak.
4. Sentetik kalibrasyon yöntemini tasarlamak.
5. Unit test ve saf sayısal test yazmak.

S3-06 ikinci onayından önce yapılamayacaklar:

1. TOI-3492.01 üzerinde yeni optimizer çalıştırmak.
2. Yeni GP/kernel fiti yapmak.
3. Yeni seed veya pencere denemek.
4. Beta sınırını değiştirmek.
5. Faz 7 veya ona bağlı fiziksel zinciri açmak.

## 3. Yetki ve önceki belgelerle ilişki

Yetki sırası:

1. Ham veri ve değişmez artifactler.
2. Sonuç görülmeden dondurulmuş hedefe özgü protokoller.
3. Bu protokollerden üretilmiş doğrulanmış gate artifactleri.
4. `currentproblem.md` içindeki özgün bilimsel kapılar.
5. `currentproblemstage2.md` içindeki Stage-2 planı ve tarihsel uygulama kaydı.
6. Kullanıcı onayından sonra bu Stage-3 kapsam değişikliği.
7. `analiz.md`, canonical makale ve operasyon belgeleri.
8. `EXOPLANET_RELEASE_ROADMAP.md` genel yöntem rehberi.

Bu belge onaylandığında Stage-2'nin geçmiş kaydını silmez. Stage-2'nin Faz 6R
sonrası Yol B kararı, o protokolün doğru tarihsel kapanışı olarak kalır. Stage 3,
bu kapanıştan sonra kullanıcının makalede kapsamlı fotometrik modellemeyi
tamamlama hedefiyle açtığı ayrı yöntem-geliştirme aşamasıdır.

Stage 3 şunları yapamaz:

1. Faz 5'i `PASS` ilan etmek.
2. Faz 6'yı `PASS` ilan etmek.
3. Faz 6R'yi `PASS` ilan etmek.
4. Eski beta sınırını değiştirmek.
5. Faz 6R'yi tam preregistered çalışma gibi yeniden tanımlamak.
6. Eski başarısız veya geçersiz artifactleri silmek.

## 4. Değişmeden korunacak mevcut durum

| Aşama | Değişmez durum | Stage 3 anlamı |
|---|---|---|
| Faz 0 | Güncel TeX büyük ölçüde düzeltildi; final audit bayat | Final TeX yeniden audit edilecek |
| Faz 1 | `PASS` | Ham veri ve zaman envanteri yeniden yapılmayacak |
| Faz 2 | `PASS` | 18 beklenen, 16 kullanılan olay korunacak |
| Faz 3 | `PASS` | Quality/background/pointing sonuçları korunacak |
| Faz 4 | `CONDITIONAL_PASS` | Reduction sistematiği final belirsizliğe bir kez taşınacak |
| Faz 5 | `FAIL` | Tek pencere/baseline modeli seçilmeyecek |
| Faz 5B | `CONDITIONAL_CONTINUE` | 24 dal ve ağırlıkları korunacak |
| Faz 6 | `FAIL_STATIONARITY` | Eski kernel ve V2 gate sonucu değişmeyecek |
| Faz 6R | `FAIL_RESIDUAL_CORRELATION` | K0 modelinin yetersizliği referans başarısızlık olarak kalacak |
| WP-09A | `PASS` | Yalnız formal sektör heterojenliği; neden atanmamış |
| Faz 7 | Kapalı | Yeni Stage-3 gürültü kapısı geçmeden açılmayacak |

Faz 6R'nin değişmez sayısal kaydı:

1. Stationarity: 24/24 geçti.
2. En yüksek ağırlıklı beta: 1.2936064512125263.
3. En yüksek beta zamanı: 80 dakika.
4. Eski beta üst sınırı: 1.2.
5. Sonuç: `FAIL_RESIDUAL_CORRELATION`.

Bu değerler yeni protokolün eşiğini belirlemek için kullanılmayacak. Yalnız
mevcut modelin neden yetersiz kaldığını gösteren bilinen sonuçlardır.

## 5. Stage 3 kapsam kararı

Stage 3'ün hedefi:

> Tam ve dürüst bir TESS fotometrik karakterizasyonu aynı makalede tamamlamak.

Stage 3'ün hedefi olmayanlar:

1. Her koşulda `validated planet` sonucu üretmek.
2. Dış veri olmadan kütle ölçmek.
3. TESS pikselleri yetmiyorsa kaynak yıldızı zorla hedef ilan etmek.
4. Formal FPP için eksik contrast/localization girdilerini simülasyonla ikame
   etmek.
5. Eccentricity'yi makalenin zorunlu sonucu yapmak.
6. Astrosismolojiyi geri getirmek.

Bu makale şu iki biçimde bilimsel olarak tamamlanabilir:

### Sonuç A: Yeni gürültü modeli geçer

Tam doğal-kadans fiziksel zinciri çalıştırılır. Güvenilir final dairesel geometri,
stellar posterior, sektör hiyerarşisi, dilution ve gerekli sağlamlık kontrolleri
üretilir. Eccentricity ve FPP yalnız kendi bağımsız kapıları geçerse eklenir.

### Sonuç B: Yeni gürültü modeli geçmez

Daha fazla model aranmaz. Hassas native-cadence geometri, density ve
eccentricity iddiaları final ölçüm olarak verilmez. Makale, yapılan bütün
kontrolleri ve verinin neden daha hassas sonucu desteklemediğini gösteren tam bir
robustness/candidate-assessment çalışması olarak kapanır.

Her iki sonuçta da çalışma tamamlanabilir.

## 6. Stage 3 genel kuralları

1. Tek bir gerçek-veri yöntem-geliştirme aşaması vardır.
2. Model ailesinde K0 referansı dışında en fazla iki korelasyonlu aday olabilir.
3. Bu adaylar gerçek veri tekrar fit edilmeden önce seçilir ve hashlenir.
4. En fazla bir önceden tanımlı sayısal fallback bulunabilir.
5. Fallback yeni kernel, yeni pencere veya yeni bilimsel model olamaz.
6. Aynı 24 Faz-5B dalı korunur.
7. Aynı 16 fiziksel transit olayı korunur.
8. İki cadence maskesi bağımsız veri gibi çarpılmaz.
9. Dört reduction aynı gözlemin bağımsız kopyaları gibi çarpılmaz.
10. 20-s ve 120-s ürünler bağımsız olay gibi birleştirilmez.
11. Sonuç görüldükten sonra eşik değiştirilmez.
12. Sonuç güzel olmadığı için dal, sektör veya olay çıkarılmaz.
13. Başarısız ve geçersiz denemeler silinmez.
14. Yeni artifactler Stage-3 adı ve yeni schema ile yazılır.
15. Bilimsel freeze olmadan manifest, ZIP, DOI veya arXiv paketi üretilmez.

## 7. Durum kodları

| Kod | Anlam |
|---|---|
| `NOT_STARTED` | Çalışma başlamadı |
| `DRAFT_AWAITING_APPROVAL` | Plan var, kullanıcı onayı yok |
| `PROTOCOL_ONLY` | Protokol donduruldu, gerçek veri çalışmadı |
| `RUNNING` | Dondurulmuş protokol uygulanıyor |
| `PASS` | Bütün bağlayıcı kapılar geçti |
| `CONDITIONAL_PASS_WITH_PROPAGATION` | Sorun belirsizliğe bir kez taşındı |
| `FAIL` | Kapı geçmedi |
| `FAIL_CLAIM_REMOVED` | Kapı geçmedi, bağımlı iddia kaldırıldı |
| `NOT_CLAIMED` | Güçlü iddia hedeflenmiyor |
| `BLOCKED_EXTERNAL` | Dış gözlem olmadan açılamaz |
| `DIAGNOSTIC_ONLY` | Yalnız duyarlılık/provenance amacıyla kullanılabilir |
| `INVALID` | Sayısal, kod veya provenance geçerliliği yok |
| `SUPERSEDED` | Yeni artifact ile değiştirilmiş ama korunuyor |

## 8. Stage 3 çalışma paketleri

### S3-00: Durum ve kapsam senkronizasyonu

Amaç: Yeni hesaplamadan önce bütün aktif belgelerin aynı durumu söylemesini
sağlamak.

Yapılacaklar:

1. `outputs/release_status.json` Faz 6R ve WP-09A ile eşitlenecek.
2. Stage-2 Yol B kapanışı tarihsel kayıt olarak korunacak.
3. Bu Stage-3 belgesinin onay durumu release status içine eklenecek.
4. Canonical TeX'teki “Faz 6R çalışmadı” paragrafı düzeltilecek.
5. Yakınsamayan native-cadence analizden kalan sayısal aralık çıkarılacak veya
   açıkça quarantine edilecek.
6. Eski mathematical audit ve manifestin bayat olduğu korunacak.
7. `docs/todo.md` ve `docs/README.md` Stage-3 durumuyla eşitlenecek.

Üretilecek artifactler:

- güncellenmiş `outputs/release_status.json`;
- TeX iddia değişiklik diff'i;
- `outputs/stage3_scope_audit.json`.

Gate:

- Faz 6/6R sonucu çelişkisi: 0;
- izinsiz güçlü iddia: 0;
- Stage-3 onay durumu bütün aktif kayıtlarda aynı;
- hiçbir eski artifact overwrite edilmemiş.

Gerçek-veri fiti: Yasak.

### S3-01: Değişmez Stage-3 girdi manifesti

Amaç: Stage 3'te kullanılacak girdileri ve eski sonuçları tek hash zincirine
bağlamak.

Manifest en az şunları içerecek:

1. Faz 1 cadence ledger hash'i.
2. Faz 2 olay envanteri hash'i.
3. Faz 3 quality audit hash'i.
4. Faz 4 reduction tablosu ve rapor hash'i.
5. Faz 5 ve Faz 5B protokol/sonuç hash'leri.
6. 24 dal kimliği ve değişmez ağırlıkları.
7. Faz 6 kernel screening ve LOSO artifact hash'leri.
8. Faz 6 V1, V2 ve gate-audit hash'leri.
9. Faz 6R sonuç, checkpoint ve geometri draw hash'leri.
10. WP-09A artifact hash'leri.
11. Kullanılacak script ve ortam kimlikleri.

Üretilecek artifact:

- `data/stage3_input_manifest.json`.

Gate:

- bütün zorunlu dosyalar mevcut;
- hashler hesaplanabilir;
- 24 dal ve ağırlıklar Faz 5B ile tam aynı;
- 16 olay Faz 2 ile tam aynı;
- bilinmeyen veya el ile değiştirilmiş girdi: 0.

Gerçek-veri fiti: Yasak.

### S3-02: Faz 6 post-mortem

Amaç: Yeni model seçmeden önce mevcut sonuçlarda problemin nereden geldiğini
anlamak. Bu paket yalnız mevcut artifactleri okur; yeni transit/noise fiti yapmaz.

Cevaplanacak sorular:

1. OU, Matérn-3/2 ve SHO hangi dal/sektörlerde sınıra dayandı?
2. Boundary davranışı amplitude, timescale veya başka hangi parametrede oluştu?
3. İki maske arasındaki predictive kazanç farkını hangi sektör ve cadence'ler
   sürüklüyor?
4. 60 cadence farkının zaman, sektör, background, quality ve transit penceresi
   dağılımı nedir?
5. Faz 6R beta fazlalığını hangi sektörler ve hangi zaman ölçekleri sürüklüyor?
6. Mevcut ACF ve periodogram artifactleri gerçek bilgi içeriyor mu, yoksa V1/V2
   geçersizliği nedeniyle boş/karantinada mı?
7. Pencere ve polinom baseline'ı korelasyonlu kernel ile aynı yavaş yapıyı
   açıklamak için rekabet ediyor mu?
8. Transit dışı screening ile ortak transit/noise fit arasında model farkı var mı?
9. Reduction ve telemetry kalıntıları red-noise sinyaliyle ilişkili mi?
10. Hangi model bileşeni transit giriş/çıkışını yeme riski taşıyor?

Üretilecek artifactler:

- `outputs/stage3_phase6_postmortem.json`;
- `outputs/stage3_phase6_boundary_map.csv`;
- `outputs/stage3_phase6_mask_influence.csv`;
- `outputs/stage3_phase6_beta_by_sector.csv`;
- `outputs/stage3_phase6_residual_summary.csv`.

Gate:

- 576 screening satırının tamamı hesaba katılmış;
- 24 dalın tamamı hesaba katılmış;
- altı sektörün tamamı hesaba katılmış;
- yeni gerçek-veri fit sayısı: 0;
- her bulgu mevcut artifact satırına bağlanmış;
- “neden kesin budur” yerine desteklenen ve desteklenmeyen açıklamalar ayrılmış.

Başarısızlık kapanışı:

Mevcut artifactler post-mortem için yetersizse eksik tanı yeniden fit yapmadan
üretilebiliyorsa üretilir. Yeni model sonucu gerektiren tanı bu pakete eklenmez.

### S3-03: Sınırlı model mimarisi kararı

Amaç: Post-mortem ve fiziksel gerekçeyle yeni model ailesini gerçek veri tekrar
çalışmadan önce sınırlamak.

Model evreni:

1. K0 white+jitter yalnız başarısız referans model olarak tutulur.
2. En fazla iki korelasyonlu model adayı seçilebilir.
3. Adaylar mevcut OU, Matérn veya SHO'nun aynısı olmak zorunda değildir.
4. Ancak yeni model, post-mortemde belirlenen somut sorunu çözmelidir.
5. “Daha iyi sonuç verir” tek başına model gerekçesi olamaz.

Mimaride dondurulacaklar:

1. Ortak transit parametreleri.
2. Sektöre özgü ve ortak gürültü parametreleri.
3. Partial pooling kullanılıp kullanılmayacağı.
4. Event baseline ve polinom yapısı.
5. Telemetry regressors kullanılacaksa tam listesi.
6. Transit ve gürültü modeli arasındaki ayrım.
7. Kernel parametre dönüşümleri, öncüller ve bounds.
8. 24 dalın model içinde nasıl marginalize edileceği.
9. Faz 4 reduction sistematiğinin tam olarak nerede ve bir kez uygulanacağı.
10. Held-out sektör ve ortak validation support tanımı.

Üretilecek karar artifacti:

- `data/stage3_model_architecture_decision.json`.

Gate:

- korelasyonlu aday sayısı en fazla 2;
- her model bileşeninin fiziksel veya sayısal gerekçesi var;
- 24 dalın hiçbiri sonuç nedeniyle çıkarılmamış;
- K0 başarısızlığı gizlenmemiş;
- gerçek-veri fitinden önce karar dosyası hashlenmiş.

Gerçek-veri fiti: Yasak.

### S3-04: Sentetik kalibrasyon protokolü

Amaç: Gerçek veri sonucuna bakmadan modelin doğru transiti geri bulup bulmadığını
ve hangi eşiklerin ne anlama geldiğini belirlemek.

İki aşamalı protokol kullanılacak:

#### S3-04A: Kalibrasyon kuralını dondurma

Sentetik sonuç görülmeden önce şu kurallar yazılacak:

1. Simülasyon sınıfları.
2. Simülasyon sayısı ve random seedler.
3. Gerçek TESS timestamp/gap yapısının kullanımı.
4. Transit parametre enjeksiyon dağılımı.
5. Gürültü amplitude/timescale dağılımı.
6. Boundary ve zor durum senaryoları.
7. Bias ölçütü.
8. Coverage ölçütü.
9. Yanlış-pozitif model seçimi ölçütü.
10. Eşiklerin sentetik sonuçtan nasıl türetileceği.
11. Başarısız kalibrasyonda stop kuralı.

#### S3-04B: Sentetik çalıştırma

En az şu veri sınıfları bulunacak:

1. Beyaz gürültü ve transit.
2. Korelasyonlu gürültü ve transit.
3. Sektöre göre değişen korelasyon genliği.
4. Sektöre göre değişen timescale.
5. Background veya pointing ile ilişkili sistematik.
6. Transitsiz null veri.
7. Boundary yakınında gürültü parametreleri.
8. Farklı impact parameter ve transit süresi.
9. Gerçek cadence boşluklarına düşen kısmi yapı.

Ölçülecekler:

1. `Rp/Rstar` bias.
2. `a/Rstar` bias.
3. Impact parameter bias.
4. Transit süresi bias.
5. Yüzde 68 ve 95 coverage.
6. Modelin transit giriş/çıkışını gürültüye yedirme oranı.
7. Beyaz veride gereksiz correlated-model seçim oranı.
8. Korelasyonlu veride K0'a yanlış dönüş oranı.
9. Optimizer no-op ve local-mode yakalama oranı.
10. Residual ACF/beta davranışı.

Üretilecek artifactler:

- `data/stage3_synthetic_calibration_protocol.json`;
- `outputs/stage3_synthetic_calibration.csv`;
- `outputs/stage3_synthetic_calibration_summary.json`;
- `outputs/stage3_threshold_calibration.json`.

Gate:

- bütün dondurulmuş simülasyonlar çalışmış;
- missing/invalid simulation açıkça sayılmış;
- bias ve coverage hedefleri geçmiş;
- transit-yeme testi geçmiş;
- optimizer no-op kontrolü geçmiş;
- eşikler önceden tanımlanan kuralla türetilmiş;
- gerçek veri sonucu kullanılmamış.

Başarısızlık kapanışı:

Sentetik kalibrasyon geçmezse model gerçek veriye uygulanmaz. Kod veya
parametreleme düzeltmesi yalnız sentetik alanda yapılır. Sentetik kapı geçmeden
gerçek veri açılmaz.

### S3-05: Sayısal ve kod geçerliliği

Amaç: Yeni likelihood ve optimizer'ın gerçekten çalıştığını gerçek veri öncesinde
kanıtlamak.

Zorunlu testler:

1. Fiziksel ve dönüştürülmüş koordinat objective eşdeğerliği.
2. Analitik ve sonlu-fark gradient karşılaştırması, uygulanabildiği yerde.
3. Uzak, optimum-yakını ve bound-yakını başlangıçlar.
4. Parametre hareketi kontrolü.
5. Objective düşüşü kontrolü.
6. Bağımsız optimizer uzlaşması.
7. Hessian rank/conditioning kontrolü, kullanılıyorsa.
8. Gap ve düzensiz cadence davranışı.
9. Deterministik paralel sonuç birleştirmesi.
10. Checkpoint ve no-clobber testi.
11. Interrupted-run resume testi.
12. Artifact schema ve hash testi.

Üretilecekler:

- Stage-3 model scriptleri;
- Stage-3 unit testleri;
- `outputs/stage3_numerical_validation.json`.

Gate:

- zorunlu sayısal testlerin tamamı geçer;
- yalnız optimizer `success` biti kapı değildir;
- parametre hareketi ve objective iyileşmesi zorunludur;
- bağımsız solver toleransı sentetik kalibrasyondan gelir;
- gerçek-veri fit sayısı hâlâ 0.

### S3-06: Final gerçek-veri protokolünü dondurma

Amaç: Gerçek-veri çalışmasının bütün ayrıntılarını sonuçtan önce sabitlemek.

Protokol en az şunları içerecek:

1. Stage-3 input manifest hash'i.
2. Post-mortem artifact hashleri.
3. Model architecture decision hash'i.
4. Sentetik kalibrasyon artifact hashleri.
5. Kod ve test hashleri.
6. Aynı 24 dal ve ağırlıkları.
7. Aynı 16 olay kimliği.
8. Tam likelihood.
9. Priors, bounds ve transforms.
10. Optimizer ve sampler.
11. Başlangıç noktaları.
12. Worker ve deterministik birleştirme ayarları.
13. Numerical gates.
14. Predictive gates.
15. Boundary ve mask-interaction gates.
16. Residual ACF/beta/periodogram gates.
17. Geometry-shift gate.
18. Injection/coverage gates.
19. Tek sayısal fallback ve tetikleyicisi.
20. Stop kuralları.
21. Üretilecek artifactlerin tam listesi.
22. Faz 7'yi açma koşulu.

Üretilecek artifact:

- `data/stage3_preregistered_noise_protocol.json`.

Gate:

- protokol schema doğrulaması geçer;
- bütün upstream hashler eşleşir;
- bütün eşikler sayısaldır;
- gerçek-data sonucu görülmeden protokol hashlenmiştir;
- kullanıcı protokol özetini açıkça onaylamıştır.

Bu kapı geçmeden gerçek-veri çalışması yasaktır.

### S3-07: Sınırlı gerçek-veri çalışması

Amaç: Dondurulmuş Stage-3 model ailesini aynı veri evreninde bir kez uygulamak.

Çalışma kuralları:

1. Ana yöntem bir kez çalıştırılır.
2. Yalnız protokoldeki hata sınıfı oluşursa kayıtlı sayısal fallback çalışır.
3. Yeni model, seed, branch, window veya threshold eklenmez.
4. Her branch/start/fold satır düzeyinde checkpointlenir.
5. Kısmi başarısızlıklar silinmez.
6. İki maske ayrı kanıt gibi çarpılmaz.
7. Reduction kolları ayrı kanıt gibi çarpılmaz.
8. Transit ve gürültü posteriorları ortak modelden üretilir.
9. Gerçek-veri sırasında protokol değiştirilemez.

Üretilecek artifactler, kesin adları protokolde dondurulmak üzere:

- joint fit tablosu;
- posterior chainler;
- branch/model ağırlıkları;
- held-out predictive skorlar;
- residual ACF;
- residual beta;
- residual periodogram;
- geometry drawları;
- optimizer/sampler diagnostics;
- run manifest ve checkpoints.

### S3-08: Bağımsız Stage-3 gate audit

Amaç: Sonuç üretici scriptten ayrı olarak geçme/kalma kararını vermek.

Denetim blokları:

1. Source/protocol hash doğrulaması.
2. Bütün dal/start/fold tamlığı.
3. Parametre hareketi ve objective iyileşmesi.
4. Cross-start stationarity.
5. Bağımsız solver uzlaşması.
6. Sampler yakınsaması.
7. Boundary ve identifiability.
8. Held-out predictive performans.
9. Mask/reduction interaction.
10. Residual ACF/beta/periodogram.
11. Sentetik bias ve coverage bağlantısı.
12. Transit-yeme kontrolü.
13. Geometry-shift ve influence.
14. Artifact schema ve provenance.

Üretilecek artifact:

- `outputs/stage3_noise_gate_audit.json`.

Karar:

#### `PASS`

Stage-3 gürültü modeli adopted-candidate durumuna geçer. Faz 7 ve bağlı fiziksel
zincir açılır.

#### `FAIL`

Yeni kernel, seed, pencere veya eşik aranmaz. Hassas native-cadence geometri,
density ve eccentricity iddiaları kapatılır. Makale tam candidate-assessment
kapsamında tamamlanır.

#### `INVALID`

Yalnız belgelenmiş kod/uygulama hatası varsa, bilimsel model değişmeden bir kod
düzeltme amendment'i yapılabilir. Bu amendment yeni bilimsel model arama hakkı
vermez.

## 9. Stage-3 gürültü kapısı geçerse devam zinciri

### S3-09: Aktivite, flare ve timing

Eski Faz 7-8 kapsamı uygulanır:

1. Aktivite ve rotation alias denetimi.
2. Flare ve spot-crossing kontrolü.
3. Olay bazlı transit zamanları.
4. Doğrusal ephemeris ve cycle-count denetimi.
5. Timing smear etkisi.

Gate geçmezse ilgili aktivite/TTV iddiası kaldırılır; timing belirsizliği final
geometriye taşınır.

### S3-10: Sektör ve olay hiyerarşisi

WP-09A'nın formal heterojenliği hiyerarşik modele taşınır:

1. Ortak derinlik.
2. Sektör excess scatter.
3. Olay excess scatter.
4. Reduction etkisi.
5. Outlier modeli.
6. Posterior predictive ve simulation-based calibration.

Formal heterojenliğin nedeni kanıt olmadan astrofiziksel ilan edilmez.

### S3-11: Stellar posterior ve limb darkening

Transit zincirinden bağımsız hazırlanabilir ve paralel yürüyebilir:

1. Passband-integrated atmosphere/SED modeli.
2. Parallax ve extinction.
3. Isochrone/evolution gridleri.
4. Bilinmeyen metallicity marjinalizasyonu.
5. Tek-yıldız ve mümkünse unresolved-companion dalları.
6. Mass-radius-age-metallicity covariance.
7. Limb-darkening drawları.

Transit yoğunluğu stellar prior olarak kullanılıp sonra bağımsız kanıt gibi
karşılaştırılamaz.

### S3-12: Kaynak, dilution ve alternatif host

1. Güncel Gaia alanı.
2. Difference-image ve pixel-light-curve denetimi.
3. Kalibre PRF likelihood, mümkünse.
4. Aperture/source branchleri.
5. Residual dilution.
6. Alternatif host senaryoları.

Kalibre localization geçmezse `on-target` iddiası açılmaz. Fiziksel radius host
koşullu verilir.

### S3-13: Uçtan uca enjeksiyon kampanyası

Final pipeline ailesi dondurulduktan sonra transitler aperture, detrending,
masking, fitting ve seçim zincirinin tamamından geçirilir.

Ölçülecekler:

1. Depth bias.
2. Duration bias.
3. Geometry bias.
4. Timing bias.
5. Coverage.
6. Detection completeness.
7. False-alarm davranışı.

### S3-14: Final 120-s dairesel posterior

Final model şunları birlikte taşır:

1. Reduction belirsizliği.
2. Window/baseline model belirsizliği.
3. Correlated noise.
4. Timing.
5. Sektör/olay hiyerarşisi.
6. Limb darkening.
7. Stellar covariance.
8. Dilution ve host dalları.

Final zincirler R-hat, ESS, MCSE, autocorrelation ve mode/bound kontrollerini
geçmeden tabloya sayı giremez.

### S3-15: 20-s cadence kontrolü

S90, S99 ve S100 20-s ürünleri final 120-s modelinin çözünürlük kontrolüdür.
Bağımsız olay veya ikinci kanıt gibi çarpılmaz.

### S3-16: Eccentricity kararı

Eccentricity zorunlu sonuç değildir.

Yalnız şu girdiler hazırsa açılır:

1. Adopted final dairesel posterior.
2. Coherent stellar posterior.
3. Full uncertainty propagation.
4. Converged eccentric sampler.
5. Prior ve model-selection duyarlılığı.
6. Eccentric phase secondary taraması.

Bu kapılar geçmezse eccentricity `NOT_CLAIMED` olur.

### S3-17: Posterior predictive ve influence

1. Leave-one-event-out.
2. Leave-one-sector-out.
3. Leave-one-reduction-family-out.
4. Prior/bound sensitivity.
5. Branch influence.
6. Posterior predictive transit ve residual kontrolleri.

Tek bir sektör, olay veya branch merkezi sonucu kayıtlı toleranstan fazla
sürüklüyorsa iddia zayıflatılır veya belirsizlik taşınır.

### S3-18: Fotometrik false-positive kontrolleri

1. Odd/even.
2. Secondary eclipse, eccentric fazlar dahil uygulanabildiği ölçüde.
3. Phase harmonics.
4. Model-shift/uniqueness.
5. Yakın kaynak ve aperture kontrolleri.
6. Sensitivity-calibrated upper limits.

Nondetection, injection sensitivity olmadan güçlü upper limit sayılmaz.

### S3-19: FPP, validation ve confirmation kararı

Formal FPP yalnız eksiksiz ve kalibre girdiler varsa hesaplanır:

1. Stellar posterior.
2. Source localization.
3. Contrast curve.
4. Host/dilution dalları.
5. Eksiksiz scenario seti.
6. Monte Carlo convergence.

Bu girdiler yoksa FPP `NOT_CLAIMED` veya `BLOCKED_EXTERNAL` olur. Bu durum
fotometrik makalenin tamamlanmasını engellemez.

Mass ve confirmation yalnız gerçek hedefe özgü RV veya eşdeğer bağımsız dinamik
kanıtla açılır.

### S3-20: Fiziksel nicelikler

Yarıçap, density, duration, inclination, irradiation ve benzeri değerler
draw-by-draw hesaplanır. Covariance korunur. Area ratio ile limb-darkened model
depth ayrı verilir. 2.6 gibi oranlar sigma diye yazılmaz.

## 10. Gürültü kapısından bağımsız paralel işler

Stage-3 onayından sonra şu işler gerçek transit/noise fitinden bağımsız
yürüyebilir:

1. S3-00 durum senkronizasyonu.
2. S3-01 input manifesti.
3. S3-02 post-mortem.
4. S3-11 stellar protocol ve sentetik hazırlığı.
5. Gaia/PRF input hazırlığı; final localization iddiası değil.
6. Final AASTeX bölüm iskeleti; final sayılar eklenmeden.
7. Claim matrix ve forbidden-word listesi.
8. Follow-up requirement tablosu.

Paralel işler Faz 7'yi veya final geometriyi açmaz.

## 11. Bağımlılık grafiği

```text
Stage-3 açık kullanıcı onayı
  -> S3-00 durum senkronizasyonu
  -> S3-01 değişmez input manifesti
  -> S3-02 mevcut-artifact post-mortemi
  -> S3-03 sınırlı model mimarisi
  -> S3-04 sentetik kalibrasyon
  -> S3-05 sayısal/kod geçerliliği
  -> S3-06 final protokol ve ikinci kullanıcı onayı
  -> S3-07 tek sınırlı gerçek-veri çalışması
  -> S3-08 bağımsız gate audit
       -> PASS: S3-09 ... S3-20 tam fiziksel zincir
       -> FAIL: güçlü fiziksel iddiaları kapat, tam candidate paper
  -> S3-21 makale freeze
  -> S3-22 release doğrulama

Paralel:
  S3-11 stellar hazırlığı
  Gaia/PRF hazırlığı
  manuscript iskeleti
```

## 12. Makale tamamlama paketi

### S3-21: Bilimsel freeze ve makale

Final makale yolu gürültü gate sonucuna göre seçilir.

Her iki yolda da:

1. Başlık kanıt düzeyini aşmaz.
2. Abstract yalnız adopted sonuçları içerir.
3. Diagnostic folded fit açıkça diagnostic kalır.
4. Yakınsamayan aralık sayısı 0 olur.
5. Kaynaksız sayı sayısı 0 olur.
6. Gizli informative prior/bound sayısı 0 olur.
7. Her final sayı tek adopted artifacte bağlı olur.
8. Failed ve nonadopted analizler doğru etiketlenir.
9. İkinci okuyucu claim audit yapılır.
10. Final TeX hash'i üzerinde mathematical audit yapılır.

Stage-3 gate geçerse:

- final native-cadence geometri verilebilir;
- physical radius host/stellar koşullarıyla verilir;
- density yalnız coherent stellar posteriorla karşılaştırılır;
- eccentricity/FPP/mass yalnız kendi kapıları geçerse eklenir.

Stage-3 gate geçmezse:

- native-cadence geometri final ölçüm olarak verilmez;
- density/eccentricity merkezi anlatı olmaz;
- formal FPP, validation, mass ve confirmation iddiası olmaz;
- bütün yapılan gürültü ve sağlamlık çalışması açıkça raporlanır;
- makale yine tamamlanır.

### S3-22: Release doğrulama

Bilimsel freeze sonrasında sıralama:

1. Claim audit.
2. Mathematical audit.
3. Canonical PDF derleme.
4. Sayfa sayfa görsel inceleme.
5. Tam pytest.
6. Yeni release manifesti.
7. Boş staging dizininde arXiv paketi.
8. Boş staging dizininde reproducibility paketi.
9. ZIP CRC ve embedded hash doğrulaması.
10. Paketi başka boş dizine çıkarıp offline test.
11. Staged arXiv kaynağını bibliography cycle ile derleme.
12. Whole-archive SHA-256 sidecar.
13. Zenodo upload.
14. Public dosyaları tekrar indirip hash doğrulama.
15. DOI yalnız çözüldükten ve dosyalar doğrulandıktan sonra metadata'ya ekleme.

## 13. Artifact adlandırma ve provenance kuralları

1. Bütün yeni dosyalar `stage3_` öneki veya Stage-3 schema kimliği taşır.
2. Eski Faz 5/6/6R dosyalarının üzerine yazılmaz.
3. Her JSON `schema_version`, `generated_utc`, `status` ve upstream hashleri
   içerir.
4. Her CSV satırı branch, sector, event, start/fold ve protocol hashini taşır.
5. Random seedler protocol artifactinde dondurulur.
6. Worker sayısı ve paralel birleştirme yöntemi kaydedilir.
7. Checkpointler deterministik ve no-clobber olur.
8. Invalid veya failed artifactler silinmez.
9. Manifest bilimsel fazlarda değil, yalnız freeze/release milestone'unda
   yenilenir.
10. Her adopted artifact için bağımsız verifier bulunur.

## 14. Kesinlikle yapılmayacaklar

1. K0 modelini farklı seedlerle tekrar tekrar çalıştırmak.
2. Beta sınırını 1.2936 sonucuna göre yükseltmek.
3. En iyi sonucu veren pencereyi seçmek.
4. En iyi sonucu veren reduction'ı seçmek.
5. W26_P1 veya başka bir dalı sonuç nedeniyle çıkarmak.
6. 20-s ve 120-s veriyi bağımsız kanıt gibi çarpmak.
7. Aynı reduction/model sistematiğini iki kez eklemek.
8. Optimizer `success` bitini tek geçme ölçütü yapmak.
9. Sentetik kapı geçmeden gerçek veri çalıştırmak.
10. Gerçek veri çalıştıktan sonra protokolü değiştirmek.
11. Ana yöntem ve fallback sonrası üçüncü yöntem aramak.
12. Faz 6/6R başarısızlığını gizlemek.
13. Sektör heterojenliğini doğrudan astrofiziksel ilan etmek.
14. Kalibre localization olmadan `on-target` yazmak.
15. Contrast/localization girdileri olmadan formal FPP yazmak.
16. RV olmadan mass/confirmation yazmak.
17. Bilimsel freeze olmadan paket/DOI üretmek.

## 15. Stop kuralları

### Stop 1: Stage-3 onayı yok

Yeni gerçek-veri fit yok.

### Stop 2: Post-mortem tamamlanamıyor

Model mimarisi seçilmez. Eksik mevcut-artifact tanıları tamamlanır veya kapsam
daraltılır.

### Stop 3: Sentetik kalibrasyon geçmiyor

Gerçek veri açılmaz. Yalnız sentetik alanda kod/model düzeltmesi yapılabilir.

### Stop 4: Sayısal doğrulama geçmiyor

Gerçek veri açılmaz.

### Stop 5: Final protokol kullanıcı onayı almıyor

Gerçek veri açılmaz.

### Stop 6: Gerçek-veri Stage-3 gate geçmiyor

Yeni kernel/seed/pencere/eşik aranmaz. Güçlü fiziksel iddialar kapatılır ve
makale candidate-assessment olarak tamamlanır.

### Stop 7: Dış veri yok

İlgili iddia `BLOCKED_EXTERNAL` veya `NOT_CLAIMED` olur. Simülasyon dış gözlemin
yerine geçmez.

## 16. İlk çalışma oturumunda yapılacaklar

Stage 3 kullanıcı tarafından onaylandıktan sonraki ilk oturum:

1. `outputs/release_status.json` senkronizasyon diff'i hazırlanır.
2. Canonical TeX'in bayat Faz 6R paragrafı düzeltilir.
3. Yakınsamayan kalan sayısal aralık kaldırılır/quarantine edilir.
4. `data/stage3_input_manifest.json` oluşturulur.
5. Post-mortem scripti yalnız mevcut artifactleri okuyacak şekilde tasarlanır.
6. 576 LOSO satırında boundary haritası çıkarılır.
7. 60 cadence mask farkı olay/sektör/telemetry ile eşlenir.
8. Faz 6R beta sektör katkıları çıkarılır.
9. Post-mortem artifactleri üretilir.
10. Hiçbir yeni gerçek-data fit çalıştırılmaz.

İlk oturumun başarı ölçütü yeni fiziksel sonuç değildir. Başarı ölçütü, problemin
hangi veri/model bileşenlerinden geldiğini izlenebilir biçimde haritalamaktır.

## 17. Tahmini çalışma süresi

| Paket | Tahmini aktif süre |
|---|---:|
| S3-00 ve S3-01 | 1-2 gün |
| S3-02 post-mortem | 1-3 gün |
| S3-03 model kararı ve S3-04 protokol | 1-3 gün |
| Sentetik kodlama ve kalibrasyon | 3-10 gün |
| Sayısal doğrulama ve protocol freeze | 2-5 gün |
| Gerçek-veri fit ve gate audit | 2-7 gün |
| PASS sonrası fiziksel zincir | 1-3 hafta |
| Makale, audit ve release | 4-10 gün |

Toplam süre modelin ve mevcut kodun yeniden kullanımına bağlıdır. Odaklı çalışma
için yaklaşık 3-6 hafta gerçekçi mertebedir. Bu takvim bilimsel sonucu garanti
etmez.

## 18. Stage 3 tamamlanma tanımı

Stage 3 şu durumda tamamlanır:

1. Eski Faz 6 ve 6R sonuçları değişmeden korunmuştur.
2. Stage-3 yöntemi gerçek veri öncesi protokol ve sentetik kalibrasyona bağlıdır.
3. Tek sınırlı gerçek-veri çalışma ve kayıtlı fallback kuralına uyulmuştur.
4. Yeni sonuç `PASS`, `FAIL` veya `INVALID` olarak bağımsız audit edilmiştir.
5. `PASS` ise bağımlı fiziksel zincir tamamlanmıştır.
6. `FAIL` ise güçlü iddialar kapatılmış ve yeni sonuç aranmamıştır.
7. Bütün hedeflenen claims geçerli kapanış durumuna sahiptir.
8. Final makale yalnız adopted sonuçları kullanır.
9. Final TeX, PDF, audit, test ve release hashleri birbiriyle uyumludur.
10. Nesnenin validation/confirmation durumu kanıt düzeyine uygun yazılmıştır.

## 19. S3-00 uygulama kaydı: 2026-07-23

Tamamlanan işler:

1. Kullanıcının aşamalı devam talimatı Stage-3 kapsam onayı olarak kaydedildi.
2. Stage 3 `PROTOCOL_ONLY` durumuna alındı.
3. Yeni gerçek-veri fit yetkisi kapalı tutuldu.
4. `outputs/release_status.json`, Faz 6R ve WP-09A gerçekleriyle eşitlendi.
5. Stage-2 Yol B kapanışı tarihsel kayıt olarak korundu.
6. Canonical TeX'teki yanlış “Faz 6R çalışmadı” anlatısı düzeltildi.
7. Yakınsamayan native-cadence sektör yarıçap-oranı aralığı TeX'ten çıkarıldı.
8. Stage-3 scope audit scripti ve regresyon testleri eklendi.
9. `outputs/stage3_scope_audit.json` `PASS` üretti.
10. Yeni optimizer, GP, kernel, seed, pencere veya gerçek-veri fiti çalıştırılmadı.

S3-00 sonucu: `PASS`.

## 20. S3-01 uygulama kaydı: 2026-07-23

Tamamlanan işler:

1. Stage-3 bilimsel girdileri 10 mantıksal gruba ayrıldı.
2. Toplam 55 zorunlu dosyanın varlığı, boyutu ve SHA-256 değeri kaydedildi.
3. Faz 2'deki 16 kullanılan olay kimliği değişmeden donduruldu.
4. İki gap olayı ayrıca korundu.
5. Faz 5B'deki 24 model dalı ve dal ağırlıkları birebir donduruldu.
6. `raw_valid` için 11, `reference_included` için 13 dal doğrulandı.
7. İki maskenin toplam ağırlıkları 0.5/0.5 olarak doğrulandı.
8. Faz 5, Faz 6 ve Faz 6R başarısızlık durumları manifestte korundu.
9. Faz 6R standalone protocol eksikliği açık provenance sınırlaması olarak
   kaydedildi.
10. `data/stage3_input_manifest.json` üretildi ve `PASS` verdi.
11. Manifest üretici, `--verify-only` yolu ve regresyon testleri eklendi.
12. Yeni gerçek-veri fiti çalıştırılmadı ve Faz 7 açılmadı.

S3-01 sonucu: `PASS`.

## 21. S3-02 uygulama kaydı: 2026-07-23

Tamamlanan işler:

1. S3-01 manifestindeki bütün kullanılan kaynak hashleri yeniden doğrulandı.
2. Faz 6'daki 576 screening satırı ve 6480 parametre-boundary tanısı hesaba
   katıldı.
3. Toplam 144 boundary bayrağı bulundu: OU için 87, Matérn-3/2 için 37 ve SHO
   için 20. Bayrakların tamamı ortak timescale parametresinin üst sınırındadır;
   amplitude veya jitter boundary bayrağı yoktur.
4. Üç kompleks kernel için iki maske arasındaki predictive etkileşim altı held
   sektöre ayrıldı. Mutlak etkileşimi en çok sektör 64, 100 ve 37 fold'ları
   taşıdı.
5. 60 raw-only cadence'in sektör, zaman, quality, background, pointing ve transit
   penceresi dağılımı kaydedildi. Noktasal predictive katkı artifactlerde
   bulunmadığı ve iki maskenin model evreni farklı olduğu için tekil cadence
   nedenselliği atanmadı.
6. Faz 6R'nin 24 dondurulmuş MAP uç noktasından optimizer veya yeni draw
   çalıştırmadan residual kuruldu. 864 dal-sektör-timescale beta satırı ve 144
   dal-sektör residual özeti üretildi.
7. Faz 6R'nin altı resmi weighted beta değeri birebir yeniden üretildi. Maksimum
   değer yine 80 dakikada 1.2936064512125263'tür.
8. 80 dakikalık fazlalığı en çok sektör 37; 160-320 dakikayı sektör 100 ve 37;
   360 dakikayı sektör 64 sürükledi. Bu dağılım tek bir sektör veya tek bir beyaz
   scatter fazlalığı açıklamasını desteklemez.
9. V1 ACF, beta ve periodogram dosyalarının dolu fakat sayısal no-op nedeniyle
   karantinada olduğu; V2 dosyalarının stationarity kapısında durduğu için boş
   olduğu doğrulandı.
10. Frozen residual-telemetry ilişkileri yalnız betimleyici olarak hesaplandı.
    En büyük weighted ilişki sektör 90 background Spearman katsayısı -0.13576
    oldu; instrumental veya astrofiziksel neden atanmadı.
11. `outputs/stage3_phase6_postmortem.json` ile dört bağlı CSV artifacti,
    no-clobber üretici, `--verify-only` yolu ve regresyon testleri eklendi.
12. Yeni gerçek-veri fiti, optimizer çağrısı, seed, threshold, pencere veya model
    seçimi yapılmadı; Faz 7 kapalı kaldı.

S3-02 sonucu: `PASS`.

## 22. S3-03 uygulama kaydı: 2026-07-23

Tamamlanan işler:

1. S3-02 post-mortemindeki 144 boundary bayrağının tamamının ortak timescale üst
   sınırında olduğu ve beta fazlasının sektör bağımlı olduğu tespit edildi.
2. Mimaride tek bir korelasyonlu aday seçildi: Matern-3/2 (`Matern32Term`,
   eps=0.01). OU (87 boundary, pürüzlü, transit yeme riski yüksek) ve SHO
   (sabit Q'lu osilatör fiziği kanıtsız) dışlandı.
3. Timescale için sektör bazlı kısmi havuzlama (`partial pooling`) benimsendi:
   `log(τ_s) = μ_τ + δ_{τ,s}`, `δ ~ N(0, 0.75²)`. Alt sınır 4 dakika, üst sınır
   780 dakika (en kısa branch penceresi 13 saatten türetilmiş destek sınırı).
4. Jitter ve amplitude hiyerarşisi, mevcut sınırlar ve öncüller aynen korundu.
5. Transit koruması için 0.75*T14 OOT maskı aynen korundu. Held-sector
   integrasyonu 3 boyutlu (jitter, amplitude ve timescale ofsetleri), düğüm
   başına 5 Gauss-Hermite noktasıyla (125 değerlendirme) yapılacak.
6. Ortak transit parametreleri (rp_rs, a_rs, impact), periyot, epoch, limb
   darkening, exposure geometri sınırları aynen korundu.
7. Event baseline (multiplicative polinom, derece branch'a bağlı, N(0,0.01²)
   prior) aynen korundu.
8. 24 dal, ağırlıklar ve iki maske evreni değişmeden donduruldu.
9. Faz 4 reduction sistematiği dal karışımı sonrası bir kez, likelihood veya
   beta içinde değil, nihai aralıklarda uygulanacak.
10. K0 white+jitter yalnız başarısız referans olarak tutuldu; sentetik
    ablasyon ve false-selection kalibrasyonunda kullanılacak, asla
    benimsenmeyecek.
11. Telemetry regressor eklenmedi; residual-telemetry ilişkileri betimleyici
    ve nedensel değil.
12. Karar `POST_RESULT_PROTOCOL_FROZEN_BEFORE_SYNTHETIC_AND_REAL_DATA` olarak
    işaretlendi; kör preregistration olarak sunulmadı.
13. Bütün provisional sayısal eşikler S3-04 sentetik kalibrasyonunda test
    edilmek üzere `uncalibrated` olarak işaretlendi.
14. `data/stage3_model_architecture_decision.json`, no-clobber üretici,
    `--verify-only` yolu ve regresyon testleri eklendi.
15. Yeni gerçek-veri fiti, optimizer çağrısı veya model seçimi yapılmadı;
    Faz 7 kapalı kaldı.

S3-03 sonucu: `PASS`.

## 23. S3-04A uygulama kaydı: 2026-07-23

Tamamlanan işler:

1. S3-03'teki tek Matern-3/2 adayı için 12 simülasyon sınıfı tanımlandı (C01-C12).
2. Toplam 210 gerçekleme: C01 ve C02 icin 30'ar; C03 ve C04 icin 20'ser;
   C05-C10 icin 15'er; C11-C12 icin 10'ar gercekleme. Kesin sinif tanimlari
   `data/stage3_synthetic_calibration_protocol.json` dosyasindadir.
3. Determinist seed scheme: `349204 + sinif_index*10000 + gercekleme*100`.
   Transit random ise `rng.integers(1, 2**32, size=n_transits)` ile ayrı seed.
4. Esik, bias, coverage, transit-koruma ve model-secim kurallari sentetik
   calismadan ONCE donduruldu; authoritative tanim JSON protokolundedir.
5. Nihai gate kriterleri: false-M1 <= %10, true-M1 >= %70, coverage,
   transit-koruma, null-transit ve optimizer/boundary kontrolleridir.
6. `data/stage3_synthetic_calibration_protocol.json` uretildi.
7. Protokol uretici, `--verify-only` yolu ve 14 regresyon testi eklendi.
8. Yeni gercek-veri fiti calistirilmadi.

S3-04A sonucu: `PASS`.

## 24. S3-04B uygulama kaydı: 2026-07-24

Tamamlanan işler:

1. `scripts/stage3_noise_core.py` oluşturuldu: K3_MATERN32_SECTOR kernel,
   sektor-bazli timescale ofsetli `parameter_layout()`, 3D quadrature
   (jitter+amplitude+timescale) ile `held_sector_joint_log_predictive_density`,
   K2 warm-start ile `_fit_pooled_map`, `_accumulate`/`_finalize` logsumexp
   helperlari.
2. `scripts/stage3_synthetic_generator.py` oluşturuldu: gercek TESS
   timestamp'leri uzerinde deterministik GP simulasyonu. GP generasyonu
   her sektorun TUM noktalari icin ayri ayri jitter+amplitude+timescale
   degerleriyle calisiyor.
3. `scripts/run_stage3_feasibility_check.py` oluşturuldu: multiprocessing
   (4 worker), tqdm progress bar, 10 beyaz + 10 M1-160 gercekleme,
   tek dal (W16_P1), tek held sektor (S37).
4. Ilk hizli smoke-test sonucu (KARANTINADA):
   - C01_white (beyaz gurultu): M1=5/10 K0=5/10 → false-M1 %50
   - C02_M1_160 (Matern-3/2 160dk): M1=8/10 K0=2/10 → true-M1 %80
   - C01 deltalari cogunlukla sifira yakin (4/5 M1 galibiyetinde delta<2);
     C02 deltalari cok buyuk (8/8 M1 galibiyetinde delta 200-1200).
    - Bu CSV artik formal sonuc degildir: GP draw'lari recorded seed ile
      yeniden uretilebilir degildi ve kosu tam branch/mask/fold evrenini
      kapsamadı.
5. Qualitative observation only: M1 kod yolu en az bir GP senaryosunda sinyal
   duyarliligi gosterdi; bu model-adoption veya gate sonucu degildir.
6. `tests/test_stage3_noise_core.py`: 44 test (parameter_layout, objective,
   optimizer, held prediction, accumulation, delegation, edge cases).
7. Tam test suite: 165 passed (121 existing + 44 new).
8. Yeni gercek-veri fiti yapilmadi. Synthetic OOT optimizer cagrilari yapildi;
   bunlar formal kalibrasyon sonucu olarak kullanilmayacak.

S3-04B sonucu: `SMOKE_TEST_INVALID_FOR_FORMAL_CALIBRATION`. Duzeltilmis,
deterministik ve protokol-tam kalibrasyon gereklidir.

## 25. Bugünkü güvenli durma noktası

S3-04B hızlı fizibilite sonrasında proje durumu:

```text
Faz 1-3 PASS
  -> Faz 4 CONDITIONAL_PASS
  -> Faz 5 FAIL
  -> Faz 5B CONDITIONAL_CONTINUE
  -> Faz 6 FAIL_STATIONARITY
  -> Faz 6R FAIL_RESIDUAL_CORRELATION
  -> Stage-2 Yol B tarihsel kapanışı
  -> Stage 3 kapsam onayı verildi
  -> S3-00 durum senkronizasyonu PASS
  -> S3-01 değişmez input manifesti PASS
  -> S3-02 mevcut-artifact post-mortemi PASS
  -> S3-03 sınırlı model mimarisi kararı PASS
  -> S3-04A sentetik kalibrasyon protokolü PASS
  -> S3-04B smoke-test formal kalibrasyon icin INVALID
  -> sıradaki paket S3-04B deterministik tam sentetik kalibrasyon
  -> S3-06 ikinci protokol onayı henüz yok
  -> yeni gerçek-veri fit sayısı: 0
  -> Faz 7 kapalı
  -> test sayısı: 165 passed
```

Doğru sonraki işlem: deterministik GP draw, fiziksel timescale sınırı, tüm
12 sinif/210 seed/24 branch/iki maske/alti fold ve transit recovery iceren
S3-04B tam ölçekli sentetik çalıştırmadır. Mevcut smoke-test sayıları esik
kalibrasyonu veya model benimseme için kullanılamaz.
