# TOI-3492.01 İkinci Aşama Bilimsel Kurtarma ve Tamamlama Planı

Son güncelleme: 2026-07-23

## 1. Belgenin amacı ve yetkisi

Bu belge, `currentproblem.md` içindeki Faz 0-30 bilimsel denetim planını
değiştirmeden, Faz 6'nın yetkili `FAIL_STATIONARITY` sonucundan sonra projenin
nasıl ilerleyeceğini uygulama düzeyinde tanımlar. Amaç faz numaralarını kör
biçimde sırayla çalıştırmak değil; bağımlılıkları, bilimsel iddia düzeyini,
sayısal kapıları, dış gözlem gereksinimlerini ve makale etkisini birlikte
yönetmektir.

Bu belge:

- Faz 5, Faz 5B veya Faz 6 sonuçlarını geriye dönük değiştirmez.
- Yeni bir Faz 6R çalışmasının bilimsel sınırlarını tanımlar; tek başına Faz 6R
  optimizer protokolü yerine geçmez.
- Her yeni hesaplamadan önce ayrıca makine-okunur ve hash-bağlı protokol
  dondurulmasını gerektirir.
- Bütün fazların `PASS` vermesini değil, her bilimsel iddianın geçerli bir
  analiz, açık bir sınırlama, kaldırma veya `NOT_CLAIMED` kararıyla kapanmasını
  hedefler.
- Yayın paketi, ZIP, DOI, arXiv ve release manifesti işlerini bilimsel çalışma
  paketlerinden ayırır.

Yetki sırası:

1. Ham veri ve değişmez artifactler.
2. Sonuç görülmeden dondurulmuş faz protokolleri.
3. `currentproblem.md` içindeki bilimsel kapılar.
4. Bu ikinci-aşama uygulama planı.
5. README, todo, release ve yayın belgeleri.

Bir çelişkide üst sıradaki kaynak geçerlidir. Eski release veya arXiv
checklistlerindeki `PASS` kayıtları güncel bilimsel kapıların yerine geçmez.

## 2. Değişmez başlangıç durumu

### 2.1 Faz özeti

| Faz | Yetkili durum | İkinci aşamaya etkisi |
|---|---|---|
| Faz 0 | Makale kapısı `FAIL` | Güçlü iddialar ve eski final aralıklar kaldırılmalı |
| Faz 1 | `PASS` | Ham ürün ve zaman standardı kullanılabilir |
| Faz 2 | `PASS` | 18 olay envanteri ve 16 kullanılabilir olay korunur |
| Faz 3 | `PASS` | Quality/background/pointing denetimi kullanılabilir |
| Faz 4 | `CONDITIONAL_PASS` | Reduction sistematiği sonraki belirsizliğe taşınmalı |
| Faz 5 | `FAIL` | Tek pencere/polinom modeli benimsenemez |
| Faz 5B | `CONDITIONAL_CONTINUE` | 24 ayrık dalın tamamı Faz 6 ve sonrasına taşınır |
| Faz 6 | `FAIL_STATIONARITY` | Adopted gürültü modeli ve Faz 7 bağımlı zinciri kapalı |

### 2.2 Faz 5B'den değişmeden taşınacak yapı

- `raw_valid` maskesinde 11 dal vardır.
- `reference_included` maskesinde 13 dal vardır.
- Toplam 24 `mask x window x polynomial` dalı vardır.
- İki maskenin öncül ağırlıkları `0.5/0.5` olarak korunur.
- Maske-içi dondurulmuş dal ağırlıkları değiştirilmez.
- `W26_P1` dahil tutulmuş hiçbir dal sonuç lehine çıkarılamaz.
- Tek `W16_P1` veya başka bir hücre kanonik model yapılamaz.
- Aynı TESS piksellerinden türetilmiş kollar bağımsız gözlemler gibi
  çarpılamaz.
- Faz 5 model saçılımı mixture içinde taşındığından ikinci kez quadrature
  padding yapılamaz.

### 2.3 Faz 6'da gerçekten yapılan iş

- Dört kernel karşılaştırıldı: K0 white+jitter, OU, yaklaşık Matérn-3/2 ve SHO.
- 24 dal, 4 kernel ve 6 held-out sektör ile 576 LOSO fitin 576'sı da sayısal
  olarak tamamlandı.
- OU, Matérn-3/2 ve SHO, K0'a karşı ham predictive iyileşme gösterdi.
- Üçü de mask-interaction ve/veya hiperparametre sınır kapılarını geçemedi.
- Karmaşık kernel aday sayısı sıfırdır.
- İlk K0 joint denemesi 72/72 başlangıçta başlangıç noktasından hareket etmediği
  için geçersizdir.
- İlk denemedeki `beta=1.2935` bilimsel sonuç değildir.
- V2 ölçekli optimizasyonda bütün dallar objective düşürdü ve başlangıçtan
  hareket etti.
- 24 dalın 22'si ön kayıtlı stationarity kapısını geçti.
- `raw_valid::W20_P0` ve `reference_included::W32_P2` dallarında üç başlangıçtan
  biri `ABNORMAL_TERMINATION_IN_LNSRCH` verdi.
- Her iki başarısız başlangıç da diğer çözümlerle yaklaşık aynı optimuma geldi;
  sorun farklı bilimsel moddan çok yakın-optimum line-search durumudur.
- Buna rağmen ön kayıtlı kural üç başlangıcın üçünün de başarılı olmasını
  istediğinden V2 geriye dönük geçirilemez.
- Yetkili karar `outputs/faz6_gate_audit.json` içindeki
  `FAIL_STATIONARITY` sonucudur.

### 2.4 Bugün yazılabilecek en güçlü bilimsel statü

TOI-3492.01 altı 120-s TESS sektöründe kalıcı transit-benzeri sinyal gösteren,
kaynağı kesin yerelleştirilmemiş, istatistiksel olarak doğrulanmamış ve dinamik
olarak teyit edilmemiş bir adaydır. Yarıçap yalnız olay gezegensel, hedef üzerinde
ve stellar/dilution varsayımları doğruysa koşullu olarak verilebilir.

Şu ifadeler yasaktır:

- `validated planet`
- `confirmed planet`
- `on-target transit`
- `measured mass`
- `measured eccentricity`
- `robust 4.3-sigma density discrepancy`
- `2.6 sigma`; 2.6 yalnız model-koşullu yoğunluk oranıdır
- Faz 6'nın residual-correlation kapısını geçtiği
- OU, Matérn-3/2 veya SHO'nun benimsenmiş kernel olduğu

## 3. Neden gürültü modeli Faz 6'dadır

Gürültü modeli ilk hesap değildir, fakat nihai fiziksel çıkarımdan önce çözülmesi
gereken erken bir model kapısıdır. Önce geçerli cadence'ler, olaylar, quality
maskeleri, background/pointing etkileri, reduction ve transit çevresi baseline
seçenekleri belirlenmelidir. Aksi halde bir GP veya başka korelasyon modeli:

- transit ingress/egress yapısını,
- yanlış baseline eğrisini,
- background veya pointing sistematiğini,
- reduction farkını

gürültü olarak soğurabilir. Doğru sıra şudur:

```text
ham veri ve zaman denetimi
  -> olay ve cadence seçimi
  -> instrumental sistematikler
  -> reduction ailesi
  -> pencere ve baseline ailesi
  -> gürültü modeli
  -> aktivite ve timing
  -> hiyerarşik ve fiziksel final model
```

Faz 16'daki doğal-kadans nihai transit fiti henüz yapılmadığından hatalı bir
gürültü modeli üzerinden final parametre üretilmiş değildir.

## 4. İkinci aşamanın iki bilimsel yolu

### 4.1 Yol A: tam native-cadence çalışma

Amaç, Faz 6'yı ayrı bir sayısal remediation ile geçmek ve timing, aktivite,
sektör hiyerarşisi, stellar posterior, limb darkening, PRF, dilution,
enjeksiyon, yakınsama ve etki analizleriyle tam doğal-kadans posterior üretmektir.

Yol A yalnız şu durumda seçilir:

- Native-cadence geometri makalenin ana sonucu olacaksa.
- Yoğunluk oranı bilimsel tartışmanın merkezinde kalacaksa.
- Faz 6R için bir ana çalışma ve aynı ilk protokolde önceden tanımlı en fazla bir
  fallback yapmaya karar verildiyse.
- Faz 6R başarısız olursa Yol B'ye geçileceği baştan kabul edildiyse.

### 4.2 Yol B: dar kapsamlı aday makalesi

Yol B, Faz 6'yı geçmiş saymaz. Makalenin iddia uzayını mevcut kanıt düzeyine
indirir:

- Native-cadence geometri ve yoğunluk nihai ölçüm olarak verilmez.
- Katlanmış/binlenmiş fit yalnız betimleyici referans olur.
- Yakınsamamış 120-s ve 20-s aralıklar final tablodan çıkarılır.
- Eksantriklik, formal FPP, validation, kütle ve confirmation iddiaları kaldırılır.
- Faz 4-6 duyarlılıkları açık sınırlama olarak raporlanır.
- Astrosismoloji tamamen çıkarılır.
- Odd/even, secondary ve phase-curve sonuçları yalnız mevcut duyarlılıklarıyla
  sınırlı tanısal kontroller olarak sunulur.

### 4.3 Bu planın önerdiği karar

Yalnız K0 joint fitin sayısal geçerliliğini hedefleyen bir ana Faz 6R çalışması
önerilir. En fazla bir maddi olarak farklı fallback'in yöntemi, tetikleyicisi ve
eşikleri ana çalışma başlamadan aynı protokolde dondurulmalıdır. Bağımsız solver
doğrulaması aynı çalışma içindeki sertifikadır ve ayrı sonuç-arama denemesi
sayılmaz. Ana çalışma ve kayıtlı fallback başarısızsa optimizer, seed, pencere
veya dal araması durdurulur ve Yol B uygulanır.

## 5. Durum kodları

Her çalışma paketi aşağıdaki durumlardan birini taşımalıdır:

| Kod | Anlam |
|---|---|
| `NOT_STARTED` | Protokolü bile dondurulmamış |
| `PROTOCOL_ONLY` | Yöntem dondurulmuş, veri sonucu üretilmemiş |
| `RUNNING` | Dondurulmuş protokol uygulanıyor |
| `PASS` | Bütün bağlayıcı kapılar geçti |
| `CONDITIONAL_PASS_WITH_PROPAGATION` | Sorun belirsizliğe açıkça aktarıldı |
| `FAIL` | Kapı geçmedi; aşağı akış iddiası bloklu |
| `FAIL_CLAIM_REMOVED` | Kapı geçmedi, ilgili iddia makaleden kaldırıldı |
| `NOT_CLAIMED` | İlgili güçlü sonuç hedeflenmiyor |
| `REMOVED` | Bölüm veya analiz canonical makaleden çıkarıldı |
| `BLOCKED_EXTERNAL` | Dış gözlem olmadan ilgili iddia açılamaz |
| `DIAGNOSTIC_ONLY` | Sonuç yalnız provenance/duyarlılık içindir |
| `READY_PARALLEL` | Bağımlı kritik yoldan bağımsız başlanabilir planlama durumu |
| `PARTIAL_READY` | Yalnız hazırlık veya bağımsız alt parça yürütülebilir |
| `NOT_ADOPTED` | Üretilmiş sonuç final bilimsel posterior olarak benimsenmemiştir |

`REMOVED_INSUFFICIENT_SENSITIVITY` gibi ayrıntılar ana durum değil, `REMOVED`
durumuna bağlı `reason_code` olmalıdır. `READY_PARALLEL` ve `PARTIAL_READY` nihai
kapanış değildir. `PENDING` de tek başına nihai kapanış durumu değildir.

## 6. WP-00: kapsam ve iddia triage'ı

### Amaç

Pahalı analizlerden önce makalenin hangi sonuçları gerçekten hedeflediğini
dondurmak ve başarısız kapılardan güçlü iddia sızmasını önlemek.

### Girdiler

- Faz 0 iddia matrisi.
- `toi3492_characterization.tex`.
- `outputs/release_status.json`.
- Faz 4-6 yetkili sonuçları.
- Yol A/Yol B kararı.

### Yapılacaklar

1. Her iddiayı `required`, `optional`, `not_claimed`, `removed` veya
   `blocked_external` olarak etiketle.
2. 4.3-sigma yoğunluk ifadesini kaldır.
3. Yakınsamamış native-cadence aralıkları final sonuç statüsünden çıkar.
4. Aşağıdaki iddialar için ayrı durum belirle:
   - kalıcı transit-benzeri sinyal;
   - native-cadence geometri;
   - fiziksel yarıçap;
   - kaynak yerelleştirmesi;
   - stellar posterior;
   - yoğunluk oranı;
   - eksantriklik;
   - FPP/validation;
   - kütle/confirmation;
   - astrosismoloji.
5. Başlık, özet, sonuç, ana tablo ve şekiller için yasak ifadeler listesi üret.

### Kapı

- Faz 6 geçmeden adopted native-cadence sayı sayısı sıfır olmalı.
- İzinsiz `validated`, `confirmed`, `on-target`, `measured eccentricity` ve
  `measured mass` ifadesi sıfır olmalı.
- Yol A/Yol B seçimi kaydedilmeli.

### Başarısızlık yolu

İddia kapsamı dondurulamazsa yeni pahalı çalışma başlatılmaz. Varsayılan karar
daha zayıf iddiadır.

## 7. WP-06R: Faz 6 sayısal remediation

### 7.1 Amaç ve sınır

Faz 6R'nin amacı karmaşık kernel aramak veya V2'yi yeniden etiketlemek değildir.
Tek amaç, dondurulmuş K0 white+jitter joint modelinin 24 Faz 5B dalının tamamında
sayısal stationarity sertifikası üretip üretemediğini test etmektir.

Faz 6R kör değildir. Yeni protokol açıkça şu sonuçların önceden görüldüğünü
yazmalıdır:

- Faz 5 ve Faz 5B sonuçları.
- 576-fold kernel screening sonucu.
- V1'deki 72 no-op optimizer denemesi.
- Geçersiz V1 beta değeri.
- V2'deki iki line-search başarısızlığı.
- V2 objective ve parametre uzlaşma değerleri.

### 7.2 Ön kayıt dosyası

Yeni gerçek-data çalışmasından önce
`data/faz6r_numerical_remediation_protocol.json` oluşturulmalıdır. En az şunları
içermelidir:

- upstream dosya yolları ve SHA-256 değerleri;
- 24 dal kimliği ve değişmez ağırlıkları;
- kullanılan cadence ve 16 olay kimlikleri;
- K0 likelihood, bounds, öncüller ve baseline modeli;
- parametre dönüşümleri;
- optimizer ve bağımsız doğrulayıcı;
- başlangıç noktaları;
- gradient/KKT/Hessian hesapları;
- bütün toleranslar;
- tek fallback kuralı;
- no-clobber ve checkpoint davranışı;
- başarısızlık halinde hangi artifactlerin üretilmeyeceği;
- Phase 7 açma koşulu.

Bu JSON yazıldıktan ve hash'i kaydedildikten sonra gerçek-data sonucu görülerek
değiştirilemez. Ana yöntem, fallback yöntemi ve fallback'i açan hata sınıfları
aynı ilk protokolde bulunmalıdır. Gerçek-data çalışmasından sonraki yeni sürüm
yalnız provenance veya kod-hatası düzeltme kaydı olabilir; üçüncü bir gerçek-data
denemesi açamaz ve eski sürüm silinmez.

### 7.3 Önce sentetik sayısal kalibrasyon

Gerçek 24 dal çalıştırılmadan önce:

1. K0 objective sentetik küçük problemlerde doğrulanır.
2. Unit-cube ve fiziksel koordinat objective eşdeğerliği sınanır.
3. Jitter yeniden parametreleştirmesi kullanılırsa eski ve yeni objective,
   penalty, feasible bölge ve Jacobian eşdeğerliği gösterilir.
4. Uzak başlangıç, optimum yakını ve bound-yakını sentetik durumlar kullanılır.
5. En az iki sonlu-fark adımıyla gradient kararlılığı incelenir.
6. `success=True` fakat stationarity-invalid çözümün reddedildiği test edilir.
7. `success=False` fakat aynı optimuma gelen çözümün nasıl sınıflanacağı sonuçtan
   önce açıkça tanımlanır.
8. KKT/Newton eşikleri sentetik kalibrasyondan sonra dondurulur.

Sentetik eşdeğerlik geçmezse durum `INVALID_NUMERICAL_REMEDIATION` olur ve gerçek
veri çalıştırılmaz.

### 7.4 Önerilen ana optimizer yaklaşımı

En küçük bilimsel değişiklik tercih edilmelidir:

- Aynı model, veri, öncül, bounds ve unit-cube ölçekleme korunur.
- Aynı üç kayıtlı başlangıç bütün 24 dalda kullanılır.
- L-BFGS-B için daha dayanıklı fakat önceden dondurulmuş ayarlar kullanılır.
- Başlangıç önerisi `maxiter=2000`, `maxls=100`, `ftol=1e-12`, `gtol=1e-7`
  olsa da bunlar V2 sonucu görüldükten sonra önerilmiş remediation adaylarıdır;
  özgün kör eşikler değildir.
- Bu ayarlar dahil optimizer toleransları sentetik calibration gridinde seçilir,
  seçim kuralı belgelenir ve gerçek 24-dal sonucu görülmeden dondurulur.
- Dondurulan değerler gerçek sonuçlara göre taranmaz.
- SciPy `success` biti tek başına kabul veya ret ölçütü olmaz.
- Bütün finite başlangıçlar full-start spread hesabına girer.
- Bağımsız KKT/projected-gradient ve yerel eğrilik sertifikası uygulanır.
- Bounded Powell veya trust-region yöntemi yalnız önceden tanımlı bağımsız
  doğrulayıcı olabilir; istenen sonucu veren solver seçilemez.

### 7.5 Bütün 24 dalın yeniden çalıştırılması

- Yalnız iki başarısız dal tekrar edilmez; 24 dalın tamamı aynı yeni protokolle
  baştan çalıştırılır.
- Hiçbir dal çıkarılmaz veya ağırlığı sıfırlanmaz.
- Pencere, polinom, maske, olay, cadence, jitter öncülü, baseline öncülü,
  transit modeli, sabit `P/T0/LD` veya pozlama entegrasyonu değiştirilmez.
- V2 endpointleri ana optimizer başlangıcı değildir. İstenirse yeni fit bittikten
  sonra bütün 24 dalda aynı şekilde objective/parametre uzlaşması için tanısal
  referans olabilir; yeni optimizerın hareket ve iyileşme kapısına girmez.
- Paralel çalışma sonuç sırasını veya seedleri değiştirmemelidir.
- Her branch/start sonucu atomik checkpoint ile yazılmalıdır.

### 7.6 Stationarity kapısı

Her dal için asgari koşullar:

- bütün kayıtlı başlangıçların finite objective üretmesi;
- başlangıçtan ölçülebilir parametre hareketi;
- objective iyileşmesi;
- bütün finite başlangıçlarda objective spread `<=1e-3`;
- bütün finite başlangıçlarda maksimum unit-parametre spread `<=1e-3`;
- bounds ihlali ve NaN olmaması;
- dondurulmuş KKT/projected-gradient sertifikası;
- dondurulmuş yerel eğrilik veya Newton-decrement sertifikası;
- bağımsız doğrulayıcı ile protokolde sayısallaştırılmış objective ve parametre
  uzlaşması.

KKT/Newton, bağımsız solver uzlaşması, gradient-adım kararlılığı ve bound
mesafeleri için mutlak toleranslar gerçek veriye bakmadan sentetik kalibrasyon
sonunda protokole yazılmalıdır. Tek bir dal başarısızsa:

- durum `FAIL_STATIONARITY` olur;
- residual beta yetkili sonuç olarak hesaplanmaz;
- geometri mixture adopted artifact olarak üretilmez;
- Faz 7 açılmaz.

### 7.7 Hessian ve conditional geometri kapısı

Yalnız 24/24 stationarity geçerse:

- Her dalın geometry Hessian'ı hesaplanır.
- Cholesky/pozitif tanımlılık geçmelidir.
- Kovaryans ve standart hatalar finite olmalıdır.
- En az iki sonlu-fark adımında geometry standart hataları ön kayıtlı toleransta
  uyuşmalıdır.
- Dal başına deterministik conditional Laplace çekilişleri üretilebilir.

Bu çekilişler Faz 16 MCMC posterioru değildir. Hessian kapısı başarısızsa durum
`FAIL_GEOMETRY_HESSIAN` olur ve residual/final mixture aşamasına geçilmez.

### 7.8 Değişmeden uygulanacak residual kapısı

Yalnız stationarity ve Hessian kapıları geçerse:

- ACF, `CADENCENO` tabanlı ve gap-aware hesaplanır.
- ACF aralığı 0-360 dakikadır.
- Beta ölçekleri 20, 40, 80, 160, 320 ve 360 dakikadır.
- Her sektörde en az üç dolu bin gerekir.
- Her ölçekte en az dört uygun sektör gerekir.
- Önce dal içinde eşit-sektör özeti, sonra dondurulmuş Faz 5B joint ağırlıkları
  uygulanır.
- Karar istatistiği altı ölçekte maksimum weighted beta'dır.
- Kapı `max beta <=1.2` olarak değişmeden korunur.
- Periodogram yalnız tanısaldır ve kernel seçimini geriye dönük değiştirmez.

Olası sonuçlar:

| Sonuç | Anlam | Phase 7 |
|---|---|---|
| `PASS_K0_WHITE` | 24/24 sayısal kapı ve beta kapısı geçti | Açık |
| `FAIL_STATIONARITY` | En az bir dal sayısal kapıyı geçmedi | Kapalı |
| `FAIL_GEOMETRY_HESSIAN` | Conditional covariance geçersiz | Kapalı |
| `FAIL_BETA_SUPPORT` | Beta için yeterli sektör/ölçek desteği yok | Kapalı |
| `FAIL_RESIDUAL_CORRELATION` | Yetkili maksimum beta 1.2'yi aştı | Kapalı |

Geçerli residual beta başarısız olursa OU/Matérn/SHO eski ELPD sonuçlarıyla
yeniden aday yapılamaz. Yeni correlated-noise remediation ayrı bir protokol ve
ayrı bilimsel karar gerektirir; bu planın varsayılanı Yol B'ye geçmektir.

### 7.9 Yasak işlemler

- V2'yi `PASS` veya `CONDITIONAL_PASS` olarak yeniden etiketlemek.
- Üçte-üç kuralını mevcut V2 için iki-of-three yapmak.
- Yalnız iki başarısız dalı çalıştırıp 22 eski dalı kullanmak.
- Başarısız dalları çıkarmak veya ağırlıklarını sıfırlamak.
- Tek pencere/polinom hücresine dönmek.
- Yeni seed, pencere, polinom veya optimizer ayarı taramak.
- İstenen sonucu veren solverı seçmek.
- Karmaşık kernelleri yalnız yüksek ham ELPD nedeniyle kabul etmek.
- Mask-interaction veya boundary kapılarını gevşetmek.
- V1 beta/geometri sonuçlarını kullanmak.
- Beta zaman ölçeğini veya 1.2 eşiğini değiştirmek.
- Faz 6R geçmeden adopted Faz 7 analizi başlatmak.

### 7.10 Artifact ve testler

Asgari artifactler:

```text
data/faz6r_numerical_remediation_protocol.json
outputs/faz6r_source_manifest.json
outputs/faz6r_objective_equivalence.csv
outputs/faz6r_gradient_step_audit.csv
outputs/faz6r_optimizer_attempts.csv
outputs/faz6r_stationarity_audit.csv
outputs/faz6r_k0_joint_fits.csv
outputs/faz6r_gate_audit.json
```

Yalnız sayısal kapılar geçerse:

```text
data/toi3492_faz6r_k0_geometry_draws.npz
outputs/faz6r_residual_acf.csv
outputs/faz6r_residual_beta.csv
outputs/faz6r_residual_periodogram.csv
outputs/faz6r_residual_peaks.csv
outputs/faz6r_final_noise_model.json
```

Testler en az şunları doğrulamalıdır:

- V1/V2 dosyalarının değiştirilmediğini.
- 24 dal ve bütün ağırlıkların korunduğunu.
- Full-start spread kullanıldığını.
- `success=True` statusunun tek başına yeterli olmadığını.
- Bir dal başarısızsa residual artifact üretilmediğini.
- `FAIL_STATIONARITY` ile `FAIL_RESIDUAL_CORRELATION` ayrımını.
- Phase 7'nin yalnız `PASS_K0_WHITE` ile açıldığını.

## 8. Faz 6'dan bağımsız hemen yürütülecek işler

### 8.1 WP-11: atmosfer/SED/izokron posterioru

Durum: `READY_PARALLEL`.

Amaç:

- Pivot-wavelength kara cisim kontrolünü nihai stellar model gibi kullanmamak.
- Passband-integrated atmosfer ve en az iki izokron gridinden kovaryanslı stellar
  posterior üretmek.

Girdiler:

- Gaia G/BP/RP ve paralaks.
- Güvenilir optik fotometri.
- 2MASS J/H/Ks.
- WISE bantları ve saturation/systematic floor bilgisi.
- Gaia kalite, astrometri ve multiplicity göstergeleri.

Yöntem:

- Paralaks sıfır noktası, extinction ve zero-point belirsizliklerini örnekle.
- En az iki evrim gridini karşılaştır.
- Tek yıldız ve çözülmemiş ikili dallarını ayrı tut.
- Transit yoğunluğunu stellar likelihood'a verme.
- Spektroskopi yoksa `[Fe/H]` için en az 0.2-0.3 dex dış sistematik içeren geniş
  öncül kullan.
- Kütle, yarıçap, yaş, metaliklik, extinction ve mesafe kovaryansını çekilişlerde
  koru.

Kapı:

- Kullanılan her bandda `|z|<3`.
- Global posterior-predictive p-değeri 0.05-0.95.
- İki grid 1 birleşik sigma içinde veya sonuç görülmeden dondurulmuş predictive
  score/evidence kuralıyla model ortalaması.
- Tek/ikili dallar açıkça ayrılmış olmalı.

Başarısızlık:

- Sonuç lehine bant çıkarılmaz.
- Grid uyuşmazlığında tek grid seçilmez; model zarfı/mixture kullanılır.
- Geçerli stellar posterior üretilemezse yoğunluk iddiası bloklanır ve yarıçap
  katalog-koşullu geniş aralıkla sınırlandırılır.

Makale etkisi:

- Stellar Characterization ve stellar tablo yeniden yazılır.
- Fiziksel yarıçap, yoğunluk, irradiation ve RV ölçekleri değişir.

### 8.2 WP-09A: formal sektör heterojenliği

Durum: `PARTIAL_READY`.

- `chi2=29.84994`, `dof=5`, `p=1.5786e-5` bağımsız yeniden hesaplanır.
- Formal, scatter-inflated ve ilerideki model-tabanlı hatalar ayrılır.
- Kamera, CCD, aperture, CROWDSAP ve background tanımlayıcıları eklenir.
- Formal heterojenlik astrofiziksel değişkenlik kanıtı olarak sunulmaz.
- Faz 10 tamamlanmadan sektör saçılımının nedeni ilan edilmez.

Kapı: `chi2` mutlak `0.01` toleransla, `dof=5` birebir ve p-değeri yüzde 1 bağıl
toleransla yeniden üretilmelidir. Üretilemezse eski heterojenlik sonucu
kullanılmaz.

### 8.3 WP-28: astrosismolojiyi çıkarma kararı

Durum: `READY_PARALLEL`; önerilen nihai durum `REMOVED`, reason code
`INSUFFICIENT_SENSITIVITY`.

Mevcut çalışma global colored-noise FAP, iki bağımsız blokta tekrar ve beklenen
birkaç-ppm sinyallerde yüzde 90 recovery kapılarını karşılamamaktadır. Bu nedenle:

- Astrosismoloji yöntemi, sonuçları, şekilleri ve sonuç cümleleri canonical
  makaleden tamamen çıkarılmalıdır.
- Seismic yoğunluk hiçbir stellar veya transit sentezine girmemelidir.
- “Tespit yok” ifadesi kısıtlayıcı seismic non-detection gibi yorumlanmamalıdır.
- Artifactler yalnız provenance olarak korunmalıdır.

### 8.4 WP-13 hazırlığı: PRF ve güncel Gaia alanı

Durum: `PARTIAL_READY`.

Şimdi yapılabilecekler:

- Güncel Gaia proper-motion propagasyonu.
- TESS-band akı oranı dönüşümleri.
- Sektör bazlı PRF/ePRF kütüphanesi ve coordinate dönüşümleri.
- Hedef ve mimic-capable kaynak listesi.
- Difference-image ve injection protokol tasarımı.

Kritik açık kaynak Gaia DR3 `5347362002981716992`, yaklaşık 56.29 yay saniyesi
uzaktadır. Aperture dışında görünmesi PRF kanatlarından sıfır akı geldiğini
kanıtlamaz. Kalibre source likelihood üretilmeden kaynak dışlanamaz.

### 8.5 WP-19A: ortak yakınsama protokolü

Mevcut Faz 16-19 tarifinde mantıksal döngü vardır. Çözüm:

1. Faz 19A sampler çalışmadan önce yakınsama kurallarını dondurur.
2. Faz 16C aday dairesel posterior üretir.
3. Faz 19B-16 bu posterioru denetler ve ancak geçerse adopted yapar.
4. Faz 17C ve Faz 18C ayrı aday posteriorlar üretir.
5. Faz 19B-17 ve Faz 19B-18 her birini ayrı denetler.

Önceden dondurulacak metrikler:

- En az dört dağınık chain.
- Warmup ve production ayrımı.
- `Nstep/tau>=50`.
- Rank-normalized split R-hat `<1.01`.
- Bulk ve tail ESS `>=1000`.
- MCSE `<0.05` posterior standart sapması.
- Rolling quantile ve stationarity.
- Bound sticking ve multimodality.
- HMC/NUTS için divergence, treedepth ve energy.

Rolling-quantile farkı, stationarity testi, multimodality, izin verilen divergence
sayısı, maksimum treedepth oranı ve energy/BFMI eşikleri sampler çalışmadan önce
sayısal olarak protokole yazılmalıdır. Yalnız görsel trace incelemesi PASS üretmek
için yeterli değildir.

### 8.6 WP-29A: makale iskeleti

Bilimsel sayılar dondurulmadan şu yapısal işler yapılabilir:

- AASTeX sınıfına geçiş.
- Data, Stellar, Transit/Noise, Results, Source/Vetting, Density/RV ve
  Conclusions bölüm iskeleti.
- Adopted, diagnostic, failed ve removed sonuç etiketleri.
- Depth, area ratio ve physical radius için ayrı alt başlıklar.
- Odd/even ve secondary için ayrı alt başlıklar.
- Astrosismoloji bölümünün çıkarılması.

Özet, sonuç, ana tablo, final şekiller ve sayısal metin henüz finalize edilmez.

### 8.7 WP-04F-A/B: reduction-family handoff ve final belirsizlik aktarımı

Durum: `NOT_STARTED`; Faz 4 sonucu bilinmektedir fakat final propagation yöntemi
henüz dondurulmamıştır.

Sorun:

- Faz 4'te PDCSAP, SAP+CBV, pipeline-aperture TPF ve TPF-PLD kabul edilmiştir.
- Faz 5/5B ve Faz 6 karşılaştırmaları yalnız PDCSAP referans kolunda yapılmıştır.
- Bu dört seri aynı TESS piksellerinden geldiği için likelihood'ları bağımsız veri
  gibi çarpılamaz.
- Faz 4'teki skaler quadrature padding, final çok-parametreli kovaryansı ve
  doğrusal olmayan derived nicelikleri tek başına temsil etmeyebilir.

Faz 10'dan önce ayrı bir
`data/faz4f_reduction_propagation_protocol.json` dondurulmalıdır. Protokol sonuç
görülmeden aşağıdaki iki yöntemden yalnız birini seçmelidir:

1. Aynı final transit/noise/nuisance yapısını dört accepted reduction üzerinde
   conditional sensitivity dalı olarak çalıştırmak ve bu dalları bağımsız
   likelihood çarpımı yapmadan önceden dondurulmuş prior/predictive ağırlıklarla
   posterior mixture olarak taşımak.
2. Hesap maliyeti bunu engelliyorsa ortak parametreler için çok değişkenli
   reduction-shift nuisance priorı kullanmak. Eski Faz 4 dal kaymaları yalnız
   başlangıç bilgisi olabilir; final dilution/host covariance'ını içermez. Bu
   nedenle dört reduction üzerinde final-model calibration fitleri yapılarak
   geometri, hierarchy, dilution ve host çapraz kovaryansları ayrıca tahmin
   edilmeden seçenek 2 kullanılamaz.

WP-04F iki yürütme aşamasına ayrılır:

- WP-04F-A, Faz 10'dan önce cadence/event eşlemesini, reduction kimliğini,
  propagation yöntemini, ağırlık kuralını ve ortak hierarchy modelinin dört
  reduction üzerinde nasıl değerlendirileceğini dondurur. Faz 10 bu aşamada
  yalnız PDCSAP üzerinde candidate hierarchy yapısını kurabilir.
- WP-04F-B, WP-10 candidate hierarchy ile WP-12/13/14 nuisance yapısı hazır
  olduktan sonra seçilmiş propagation yöntemini dört reductionın tamamında
  uygular. Faz 10 ve reduction belirsizliği ancak WP-04F-B geçerse adopted olur.

Kurallar:

- Yöntem final sonuç görülerek seçilemez.
- Dört accepted reduction sonuç lehine elenemez.
- Predictive ağırlık kullanılacaksa yalnız transit-dışı önceden tanımlı bloklardan
  gelir ve ağırlık formülü protokole yazılır.
- Eşit prior ağırlık kullanılacaksa gerekçesi önceden yazılır.
- Aynı-piksel kolları hiçbir aşamada bağımsız kanıt gibi çarpılmaz.
- Reduction ile geometri, dilution ve host arasındaki covariance korunur.
- Faz 4 systematic'i mixture/nuisance içinde taşındıysa ikinci kez quadrature
  eklenmez.

Kapı:

- Dört reduction dalı veya eşdeğer dört-dal kalibre nuisance desteği korunmalı.
- Final drawların reduction kimliği veya reduction-shift çekilişi izlenebilir
  olmalı.
- Posterior mixture ağırlıkları toplamı bir olmalı ve sonuçtan sonra
  değiştirilmemeli.
- WP-20 reduction influence tablosu bu handoff'tan yeniden üretilebilmeli.

Başarısızlık:

- Reduction covariance geçerli biçimde taşınamazsa final native-cadence geometri
  adopted olmaz.
- Eski skaler padding, final çok değişkenli posterior gibi sunulmaz.

## 9. Faz 6R geçerse kritik bilimsel yol

### 9.1 WP-07: aktivite, leke, flare ve spot crossing

Girdiler:

- Yetkili Faz 6R residuaları.
- SAP, PDCSAP ve kabul edilen TPF reductionları.
- Faz 2 olay ledger'ı.
- Faz 5B dal yapısı.

Analizler:

- Transit-masked Lomb-Scargle, ACF ve wavelet.
- Block/permutation bootstrap ile global FAP.
- Sektör ve bağımsız zaman bloklarında replication.
- Her olayda flare, spot crossing ve keskin background anomalisi.
- Derinlik ile yerel parlaklık, aktivite genliği ve background arasında
  hiyerarşik regresyon.
- Spot sıcaklığı ve covering fraction duyarlılığı.

Kapı:

- Rotasyon için global FAP `<0.01` ve iki bağımsız blokta uyumlu tekrar.
- Aktivite kaynaklı `Rp/Rstar` yanlılığının yüzde 95 üst sınırı 0.5 final sigmayı
  aşarsa aktivite terimi modele girer.

Başarısızlık:

- Rotasyon periyodu raporlanmaz.
- Quasi-periodic kernel açılmaz.
- Aktivite sınırlandırılamazsa sektör derinlik farkı astrofiziksel diye
  yorumlanmaz.

### 9.2 WP-08: olay zamanları ve ephemeris

Analizler:

- Ortak transit şekliyle her kullanılabilir olayın merkez zamanı.
- Doğrusal dönem/epoch ve tam kovaryans.
- Cycle-count posterioru.
- Sabit, olay-offset ve sektör-offset modellerinin karşılaştırması.
- Eşlenmiş 20-s zaman kontrolü.
- 1, 2 ve 5 yıllık takip pencereleri ve ephemeris expiration.

Kapı:

- Tek cycle-count çözüm olasılığı `>0.999`.
- Timing modeli kendi yakınsama kapısını geçmeli.
- Serbest timing geometriyi 0.5 sigmadan fazla kaydırırsa final modele girmeli.

Başarısızlık:

- TTV iddiası yapılmaz.
- Resmi ephemeris geniş predictive scatter ile verilir.
- Takip penceresi yapay biçimde dar gösterilmez.

### 9.3 WP-10: hiyerarşik sektör/olay derinliği

Girdiler: Faz 6R noise, Faz 7 aktivite, Faz 8 timing, Faz 9 formal audit,
mask/window dalları ve WP-04F-A reduction handoff specification.

Çıktılar:

- Ortak `Rp/Rstar`.
- Sektör fazla-saçılım posterioru.
- Desteklenirse sektör içinde olay saçılımı.
- Kamera/background/aktivite kovaryatları.
- SBC ve posterior-predictive sonuçları.

Bu aşamadaki hierarchy sonucu WP-04F-B tamamlanana kadar `candidate` durumundadır;
PDCSAP-only sonuç adopted final hierarchy sayılamaz.

Kapı:

- SBC simulation sayısı, rank-uniformity testi, yüzde 68/95 coverage toleransı
  ve bias eşiği sonuç görülmeden WP-10 protokolünde sayısallaştırılmış olmalı.
- PPC p-değeri 0.05-0.95.
- Bütün sektörler yüzde 99 predictive aralıkta.

Başarısızlık:

- Bir sektör çıkarılarak kapı geçirilmez.
- Outlier sektör systematic dal olarak korunur.
- Merkezi yoğunluk/geometri iddiası bloklanır.

### 9.4 WP-12: metaliklik ve limb darkening

Girdiler: WP-11 stellar çekilişleri ve Faz 6R model yapısı.

- PHOENIX/LDTk ve bağımsız atmosfer reçetesi karşılaştırılır.
- Fiziksel `q1/q2` transit fitinde örneklenir.
- Geniş ve atmosphere-informed öncül dalları karşılaştırılır.
- Gerekirse quadratic ve power-2 kanunları karşılaştırılır.
- `[Fe/H]=0` ölçüm gibi kullanılmaz.

Kapı: `q1/q2` sınıra yığılmamalı; atmosfer reçetesi geometriyi 0.5 sigmadan fazla
değiştirirse model ortalaması gerekir.

### 9.5 WP-13: kalibre PRF kaynak yerelleştirmesi

Girdiler:

- Altı TPF.
- Güncel Gaia alanı ve proper motion.
- TESS-band akı oranları.
- Faz 8 ephemeris.
- Difference images.

Analizler:

- Sektör bazlı hedef ve bütün mimic-capable kaynak PRF throughput'u.
- Olay/sektör difference-image joint fit.
- Hedefe ve komşulara sentetik transit enjeksiyonu.
- Gerekli intrinsik tutulma derinliği posterioru.
- Hedef, katalog komşuları, Gaia-altı/çözülmemiş kaynak sınıfı ve eksik-katalog
  sınıfı için önceden tanımlı prior odds.
- Gaia completeness ve TESS-band kaynak-popülasyonu belirsizliği.
- Çoklu kaynak hipotezleri üzerinde normalize edilmiş, tanımlı kaynak kümesine
  koşullu kalibre `P(source|data, source_set)`.

Kapı: 56.29 yay saniyelik kaynak yalnız gerekli tutulmanın yüzde 99.7 alt sınırı
yüzde 100'ü aşarsa veya bütün prior-odds duyarlılık dallarında kalibre koşullu
`P(source|data, source_set)<0.003` ise dışlanır. Bu kapı yalnız adı geçen kaynağı
dışlar; çözülmemiş veya katalog-altı hostları dışlamaz ve tek başına hedef üzerinde
olma kanıtı değildir.

Başarısızlık: kaynak açık false-positive dalıdır; `on target` yazılmaz.

### 9.6 WP-14: dilution ve alternatif host dalları

- Sektör bazlı dilution posterioru.
- Hedef-host dalı.
- Çözülmemiş companion-host dalı.
- İzinli uzak Gaia-host dalları.
- Her dalda intrinsik depth ve companion radius.
- PDCSAP'a ikinci CROWDSAP uygulanmaz.

Kapı: dilution sonucu 0.5 sigmadan fazla değiştirirse zorunlu nuisance olur. Açık
host dalı varken tek koşulsuz yarıçap verilmez.

Contrast curve yokluğu çözülmemiş companion dalını sıfırlamaz.

### 9.7 WP-15: uçtan uca enjeksiyon kampanyası

Bu paket aday pipeline ailesi WP-07-14 sonunda dondurulduktan sonra çalıştırılır.

- Ham TPF ve SAP'a detrending öncesi transit enjekte edilir.
- Gerçek gap, quality, background ve pointing korunur.
- Derinlik, impact parameter, süre, ingress ve timing değişir.
- Pipeline başına en az 300 transit ve 300 null denemesi yapılır.
- Inverted, scrambled-ephemeris, off-transit, off-target ve control-star
  denemeleri bulunur.
- Yüzde 68/95 coverage kontrol edilir; binomial belirsizlik yöntemi ve nominal
  oranlardan izin verilen sapma protokolde simülasyondan önce dondurulur.

Kapı:

- Gözlenen derinlikte recovery `>=%95`.
- Medyan normalize bias `<0.25 sigma`.
- Null false-alarm `<%1`.
- Coverage ön kayıtlı binomial toleranslarda nominal oranlarla uyumlu.

Başarısızlık:

- Pipeline sonucu görüldükten sonra ayarlanmaz.
- Bias açıkça modele taşınır veya pipeline elenir.
- Hiçbir pipeline geçmezse Faz 16 adopted olamaz ve Yol B'ye geçilir.

### 9.8 WP-16C ve WP-19B-16: final dairesel posterior

Faz 16C candidate posterior üretir:

- Gerçek 120-s zamanları ve pozlama entegrasyonu.
- Kullanılabilir bütün olaylar.
- Timing, hiyerarşik derinlik, baseline, noise, LD, dilution ve jitter.
- Stellar-density öncülü olmadan circular reference.
- Binlenmiş likelihood yok.
- Faz 5B model belirsizliği korunur.
- WP-04F ile reduction-family belirsizliği bağımsız likelihood çarpımı yapmadan
  draw-by-draw taşınır.

Faz 19B-16 ancak bütün yakınsama kapıları geçerse posterioru `adopted` yapar.

Başarısızlık:

- En fazla bir ön kayıtlı farklı sampler/parametrizasyon fallback'i.
- Yakınsamazsa aralıklar final tabloya girmez.
- Faz 17-27 adopted fiziksel zinciri kapatılır ve Yol B uygulanır.

### 9.9 WP-17: 20-s geometri kontrolü

- S90/S99/S100 native 20-s modeli.
- Kontrollü 120-s'ye binlenmiş 20-s modeli.
- Eşlenmiş 120-s modeli.
- Paired bootstrap/enjeksiyon covariance'ı.
- `Rp/Rstar`, `a/Rstar`, `b`, `T14` ve ingress karşılaştırması.

Kapı: covariance-aware farklar her ana parametrede `<2 sigma`.

20-s ve 120-s bağımsız kanıt gibi çarpılmaz. Uyuşmazlıkta cadence systematic'i
taşınır; tercih edilen cadence seçilerek fark gizlenmez.

### 9.10 WP-18 ve WP-19B-18: eccentricity

Bu paket yalnız eccentricity ölçümü makale hedefi olarak korunuyorsa yapılır.

- Photometry-only eccentric dal.
- Bağımsız stellar-density-informed dal.
- Circular modelle aynı nuisance yapısı.
- `sqrt(e)cos(omega)` ve `sqrt(e)sin(omega)` koordinatları.
- Eccentricity öncül duyarlılığı.
- Predictive ve evidence karşılaştırması.
- Ayrı yakınsama denetimi.

Kapı:

- Her iki model yakınsamış.
- `delta ELPD>2 SE`.
- Önceden seçilmiş güçlü evidence eşiği.
- Öncel/stellar/noise değişiminde `<0.5 sigma` kayma.

Geçmezse eccentricity ölçümü tamamen kaldırılır; `e_min` yalnız analitik
illüstrasyon olur ve eski yaklaşık `e=0.28` kullanılmaz.

### 9.11 WP-20: posterior predictive ve etki analizi

- Event, sektör, faz, background, pointing ve aktivite PPC.
- Leave-one-event-out ve leave-one-sector-out.
- Reduction, pencere, kernel, LD ve stellar-grid model belirsizliği.
- Grazing ve multimodal posterior olasılıkları.

Kapı:

- Event çıkarımı `<0.5 sigma`.
- Sektör çıkarımı `<1 sigma`.
- Gözlenen özetler yüzde 99 predictive aralıkta.
- Grazing olasılığı yüzde 1'i aşarsa ayrı dal korunur.

Etkili olay veya sektör sonuç lehine çıkarılmaz. Büyük etki merkezi yoğunluk
iddiasını bloke eder.

### 9.12 WP-21: fiziksel nicelikler

Girdiler: WP-11, WP-14, adopted WP-16 ve WP-20.

Draw-by-draw üretilecekler:

- Geometrik alan oranı.
- Limb-darkened model derinliği.
- Fiziksel yarıçap ve semimajor axis.
- `T14`, `T12` ve `rho_circ`.
- Incident flux ve equilibrium temperature.
- Host ve mass-ratio dalları.
- Yüzde 68 ve 95 aralıklar.

Kapı: bağımsız hesap yüzde 0.1 içinde uyuşmalı; alan oranı ve model derinliği
ayrı raporlanmalı; host belirsizliği açıkken tek koşulsuz yarıçap verilmemeli.

### 9.13 WP-22, WP-23 ve WP-24: false-positive fotometrik kontroller

Bu üç paket uygun final girdilerden sonra paralel çalışabilir.

WP-22 odd/even:

- `P` için odd/even.
- `2P` için phase-0/phase-0.5.
- Derinlik, süre, ingress ve tam şekil.
- Noise, hierarchy ve timing belirsizliği.
- Farklar `<3 sigma`; kısıtlayıcı test için yüzde 95 bağıl derinlik/süre farkı
  üst sınırı `<%10`.
- Aksi halde sonuç `inconclusive` olur.

WP-23 secondary:

- Faz 0.05-0.95.
- Süre `0.25T14-2T14`.
- En az `1e4` block/GP null.
- Hücre bazlı injection recovery.
- Faz 18 yoksa geniş fiziksel eccentric-template gridi.
- Tespit için global FAP `<0.01`; upper limit için ilgili hücrede recovery
  `>=%90`.
- Eski 135 ppm değeri bütün fazlara genellenmez.

WP-24 harmonikler:

- SAP, PDCSAP ve TPF.
- Control star, off-target aperture ve leave-one-sector.
- GP, CBV/background ve sektör baseline'ları.
- İşaret/amplitude injection recovery.
- Fiziksel sonuç için doğru işaret, global 5 sigma, iki blokta 3 sigma, iki
  reduction, yüzde 90 recovery ve null FP `<%1`.
- Eski negatif reflection terimi fiziksel detection değil systematics uyarısıdır.

### 9.14 WP-25: formal FPP

Validation hedefleniyorsa zorunlu girdiler:

- Final transit posterioru.
- Stellar ve host dalları.
- PRF source likelihood.
- Dilution.
- Odd/even ve secondary.
- Contrast curve veya gerçekten eşdeğer yakın-companion kısıtı.
- Instrumental reliability.

Kapı:

- En az `1e6` etkin simülasyon.
- En az 20 seed.
- Bütün kabul edilen stellar/host/aperture dalları.
- Tekrarlar arası dağılım `<%20`.
- Önceden tanımlı FPP/NFPP eşikleri bütün dallarda.

Contrast curve yoksa varsayılan kapanış:

```text
formal_fpp = null
statistical_validation_claim_supported = false
status = NOT_CLAIMED_MISSING_CONTRAST_AND_COMPLETE_LOCALIZATION
```

Formal FPP olmaması aday makalesini engellemez; `validated` kelimesini engeller.

### 9.15 WP-26: yoğunluk oranı sentezi

- Her kabul edilen modelde `rho_circ/rho_star`.
- `(1+q)g^3` ve uygun `e_min` duyarlılığı.
- Stellar, timing, dilution, LD, noise, activity ve host katkı ayrıştırması.
- Model zarfı.

Kapı: her kabul edilen circular-photometry ve stellar dalında yüzde 95 alt sınır
1'in üzerinde olmalıdır. Yüksek çözünürlüklü spektroskopi yoksa bu kapı geçse
bile sonuç yalnız `photometric-stellar-model-conditional density ratio` olarak
adlandırılır; `robust density anomaly` veya bağımsız astrodensity kanıtı denmez.
Güçlü `robust` dili ancak bağımsız spektroskopik stellar posterior da aynı
önceden tanımlı kapıyı geçerse değerlendirilebilir. Kapı geçmezse 2.6 yalnız
model-koşullu oran olarak kalır ve sigma yazılmaz.

### 9.16 WP-27: RV fizibilitesi ve dış gözlem

Erken planlama Faz 8 ve Faz 11 sonrasında yapılabilir:

- 1, 3, 13 ve 80 Jupiter-kütlesi için K ölçekleri.
- Reconnaissance ve precision-RV hedeflerinin ayrılması.
- Faz örnekleme ve alias planı.
- BIS, FWHM, Ca II H&K, H-alpha ve çift-çizgi kontrolleri.

Final schedule WP-18/21/26 sonrasında:

- Eccentric periastron, jitter/activity ve cihaz offsetleri.
- En az 1000 schedule simülasyonu.
- Hedef sinyal için yüzde 90 recovery.

Gerçek hedefe özgü epoch RV olmadan measured mass, dynamical confirmation veya
RV-temelli eccentricity yoktur. Gaia combined RV bir yörünge değildir.

Gerçek RV elde edilirse ayrı WP-27B zorunludur:

- Ham spektrum/RV provenance, barycentric zaman, cihaz ve pipeline sürümü.
- Epoch kalite kontrolü, düşük S/N ve outlier kuralları sonuç görülmeden
  dondurulmalıdır.
- Cihaz zero-point ve offsetleri, ek jitter, gecelik korelasyon ve activity
  göstergeleri modellenmelidir.
- BIS, FWHM, Ca II H&K, H-alpha ve RV korelasyonları raporlanmalıdır.
- Tek/çift çizgi ve km/s stellar-binary senaryoları ayrı tutulmalıdır.
- Circular ve izinliyse eccentric Keplerian modeller aynı nuisance yapısıyla
  karşılaştırılmalıdır.
- Period/epoch öncülü photometric posterior provenance'ına bağlı olmalıdır.
- Kütle posterioru stellar-mass covariance ile draw-by-draw üretilmelidir.
- Alias, activity-only, trend ve null modelleri önceden dondurulmuş predictive
  veya evidence kapısıyla karşılaştırılmalıdır.
- Injection/recovery ve leave-one-instrument/epoch etki analizi yapılmalıdır.

WP-27B kapısı ayrıca protokolde sayısallaştırılmalıdır: bütün chainler WP-19
yakınsama kapısını geçmeli, orbital model önceden seçilmiş null/evidence ve
injection-calibrated detection kapısını geçmeli, activity/alias dallarında sinyal
kararlı olmalıdır. Pozitif destekli bir mass/K öncülünde posteriorun sıfırdan büyük
olması detection kanıtı sayılmaz; null-model karşılaştırması veya signed-amplitude
kalibrasyonu zorunludur. Bunlar geçmeden gerçek RV noktaları bulunsa dahi measured
mass veya confirmation yazılmaz.

## 10. Faz 6R başarısız olursa Yol B

Faz 6R veya tek ön kayıtlı fallback başarısız olursa şu kararlar otomatikleşir:

1. Faz 6 `FAIL_STATIONARITY` olarak korunur.
2. Daha fazla seed, optimizer, pencere, polinom veya dal araması durur.
3. Faz 7 adopted activity/residual analizi kapatılır.
4. Faz 8 yalnız geniş ephemeris/takip penceresi düzeyinde tutulabilir; TTV iddiası
   yapılmaz.
5. Faz 9 formal heterojenlik sonucu doğru sınırlamayla korunabilir.
6. Faz 10-21 içinde hiç çalıştırılmayan paketler `NOT_CLAIMED`; önceden üretilmiş
   fakat final olmayan tanısal posteriorlar `NOT_ADOPTED` olur.
7. Faz 18 eccentricity ölçümü kaldırılır.
8. Odd/even sonucu `inconclusive screening` olur.
9. Secondary yalnız test edilen faz/süre bölgesiyle sınırlandırılır.
10. Phase curve fiziksel detection olarak sunulmaz.
11. `formal_fpp=null`; validation iddiası yoktur.
12. Yoğunluk oranı ana keşif iddiası olmaktan çıkar.
13. RV yalnız takip önerisi olur.
14. Astrosismoloji çıkarılmış kalır.
15. Makale betimleyici ve açıkça sınırlı bir aday çalışması olarak tamamlanır.

Yol B'de takip penceresi verilecekse ayrı WP-08B uygulanır. Bu paket transit
geometrisi veya TTV ölçümü üretmez; resmi TOI ephemerisini, katalog kovaryansını,
TESS sektörleri arasındaki cycle-count'i ve önceden tanımlı konservatif ek timing
floor'unu kullanır. Çıktı yalnız geniş takip penceresi ve expiration tarihidir.
Cycle count tek değilse bütün izinli pencereler verilir. WP-08B protokolü olmadan
Yol B makalesinde yeni hassas ephemeris veya takip penceresi yayımlanmaz.

Yol B başarısız bir proje değildir. Bilimsel olarak dürüst bir kapsam kapanışıdır.

## 11. Faz 7-30 durum ve bağımlılık matrisi

| Faz | Şimdiki durum | Başlama koşulu | Başarısızlıkta kapanış |
|---:|---|---|---|
| 7 | Faz 6 nedeniyle bloklu | `PASS_K0_WHITE` | Rotasyon yok; aktivite sınırlaması |
| 8 | Adopted analiz bloklu | Faz 6R; ledger hazırlığı şimdi olabilir | TTV yok; geniş takip penceresi |
| 9 | Kısmen hazır | Formal kısım şimdi | Yorum Faz 10'u bekler |
| 10 | Bloklu | Faz 6-9 | Heterojenlik limitation; final tek derinlik yok |
| 11 | Hazır/paralel | Faz 0 | Geniş koşullu stellar sonuç |
| 12 | Kısmen bloklu | Faz 11 ve noise yapısı | Sabit LD final olamaz |
| 13 | Kısmen hazır | Final için Faz 8 | Kaynak açık senaryo |
| 14 | Bloklu | Faz 10-13 | Tek koşulsuz yarıçap yok |
| 15 | Protokol hazırlanabilir | Aday pipeline WP-07-14 sonunda | Faz 16 adopted olamaz |
| 16 | Bloklu | Faz 1-15 ve Faz 19A | Yol B |
| 17 | Bloklu | Adopted Faz 16 | 20-s yalnız tanısal |
| 18 | Opsiyonel/bloklu | Faz 11-16 | Eccentricity iddiası kaldırılır |
| 19 | Yatay kalite kapısı | Protokol şimdi, denetim her posterior sonrası | Aralıklar final olmaz |
| 20 | Bloklu | Adopted Faz 16-19 | Merkezî geometri/yoğunluk iddiası yok |
| 21 | Bloklu | Faz 11,14,16-20 | Koşullu radius veya kaldırma |
| 22 | Bloklu | Final timing/hierarchy/model | `inconclusive` |
| 23 | Protokol kısmen hazır | Final noise/model; Faz 18 şart değil | Yalnız test edilen hücreler |
| 24 | Bloklu | Final noise/model | Fiziksel phase curve kaldırılır |
| 25 | Dış veri bloklu | Final girdiler + contrast | `formal_fpp=null` |
| 26 | Bloklu | Faz 11-21 | 2.6 yalnız koşullu oran |
| 27 | Kısmen hazır | Erken plan Faz 8/11; final sonra | Yalnız takip önerisi |
| 28 | Hazır | Hemen karar | Öneri: tamamen kaldır |
| 29 | Kısmen hazır | İskelet şimdi, final bilim sonrası | Placeholder korunur |
| 30 | Final bloklu | Bütün iddia kapanışları | Yayın yapılmaz |

## 12. Dış gözlem gereksinimleri

| Dış gözlem | Açtığı bilimsel kapı | Olmadan yapılabilecek | Olmadan yasak olan |
|---|---|---|---|
| Yüksek çözünürlüklü spektroskopi | Bağımsız `Teff/logg/[Fe/H]`, çift çizgi, aktivite | Geniş metallicity öncüllü photometric stellar posterior | Güçlü bağımsız astrodensity yorumu |
| Speckle/AO contrast curve | Gaia-altı yakın companion ve validation | Companion dalını açık tutmak | Formal validation |
| Transit sırasında yer tabanlı görüntüleme | Kesin gökyüzü kaynağı | Kalibre TESS PRF olasılığı | Kesin host attribution |
| Reconnaissance spektroskopi | Stellar binary/çift çizgi/km-s hareket | Fotometrik EB vetting | Spektroskopik binary dışlama |
| Precision epoch RV | Kütle ve orbital eccentricity | K ölçeği ve schedule simülasyonu | Measured mass/confirmation |
| Yeni transit zamanları | Güncel ephemeris | TESS tabanlı geniş kovaryanslı pencere | Yapay hassas güncel ephemeris |

Dış gözlem eksikliği bütün makaleyi bloke etmez. İlgili iddia
`BLOCKED_EXTERNAL` veya `NOT_CLAIMED` olarak kapanır.

## 13. Gerçek çalışma sırası

### 13.1 Hemen yapılacak paralel blok

1. WP-00 iddia ve kapsam triage'ı.
2. WP-06R makine-okunur protokolü ve sentetik kalibrasyon tasarımı.
3. WP-11 stellar posterior protokolü.
4. WP-09A formal sektör istatistiği.
5. WP-28 astrosismolojiyi çıkarma kararı.
6. WP-13 Gaia/PRF hazırlığı.
7. WP-19A ortak yakınsama protokolü.
8. WP-29A AASTeX bölüm iskeleti.
9. Contrast curve, spectroscopy, source imaging ve RV için dış gözlem talep
   paketleri.

### 13.2 Yol A kritik yolu

```text
WP-06R
  -> WP-04F-A protocol/handoff freeze
  -> WP-07 + WP-08
  -> WP-10 + WP-12 + WP-13(final)
  -> WP-14
  -> WP-04F-B reduction-family application ve hierarchy adoption
  -> WP-15
  -> WP-16C
  -> WP-19B-16
  -> WP-17 + WP-18(optional)
  -> ilgili WP-19 denetimleri
  -> WP-20
  -> WP-21
  -> WP-22 + WP-23 + WP-24
  -> WP-26
  -> WP-25 yalnız dış girdiler varsa
  -> WP-27 final schedule
  -> WP-27B yalnız gerçek RV verisi ve mass iddiası varsa
  -> WP-29B
  -> WP-30
```

WP-11, WP-28, WP-09A, WP-13 hazırlığı ve WP-29A bu kritik yoldan bağımsız
ilerleyebilir.

### 13.3 Yol B kritik yolu

```text
WP-00
  -> Faz 6 başarısızlığını ve sınırlı iddiaları makaleye uygula
  -> WP-11 koşullu stellar karakterizasyon
  -> WP-09A formal heterojenlik
  -> WP-08B yalnız geniş takip penceresi yayımlanacaksa
  -> WP-13 yalnız mevcut PRF sınırları veya açık-host senaryosu
  -> WP-28 kaldırma
  -> tanısal vetting sonuçlarını doğru sınırlamalarla yeniden yaz
  -> WP-29A/29B
  -> WP-30
```

## 14. Makale değişiklik planı

### 14.1 Hemen yapılacak metin düzeltmeleri

- Başlığı doğrulanmamış ve teyit edilmemiş aday kapsamına indir.
- Katlanmış/binlenmiş transit fitini `diagnostic reference` olarak etiketle.
- Yakınsamamış native-cadence 120-s/20-s aralıklarını final statüsünden çıkar.
- 4.3-sigma ifadesini kaldır.
- 2.6 değerini yalnız yoğunluk oranı olarak açıkla.
- Yaklaşık `e=0.28` ve `e_min` değerlerini ölçüm gibi sunma.
- SPOC/DV ve eski difference-image sonucunu formal on-target localization gibi
  sunma.
- Odd/even sonucunu `clean` değil `inconclusive screening` olarak sınırla.
- 54 ppm'i yalnız sabit faz/süre formal sonuç; 135 ppm'i systematics-limited
  envelope olarak yaz.
- FPP, validation, mass ve confirmation sayıları verme.
- Faz 4 reduction, Faz 5/5B baseline/window ve Faz 6 noise duyarlılığını Methods
  ve Limitations'a ekle.
- Astrosismolojiyi WP-28 kararıyla çıkar.

### 14.2 Yol A geçerse final değişiklikler

- Ana transit tabloyu Faz 16-21 adopted posteriorundan yeniden üret.
- Folded referans değerlerini ayrı historical/diagnostic tabloya taşı.
- Reduction, mask, window, polynomial, noise, timing, hierarchy, LD, stellar,
  dilution ve host belirsizliklerini taşı.
- Alan oranı ile limb-darkened derinliği ayrı satırlara koy.
- Sektör tablosunu formal, bootstrap ve model-tabanlı hatalarla yenile.
- Adopted fit, corner, residual ve source-localization şekillerini final
  artifactlerden yeniden üret.
- Eccentricity ve FPP yalnız kendi kapıları geçerse; mass ise yalnız gerçek
  hedefe özgü RV ve WP-27B geçerse özet/sonuca girer.

### 14.3 Yol B uygulanırsa final değişiklikler

- Ana sonuç, sinyalin altı sektördeki betimleyici kalıcılığı olur.
- Transit geometri yalnız referans model ve duyarlılık zarfı olarak verilir.
- Fiziksel radius güçlü koşul cümlesiyle veya senaryo tablosuyla sınırlandırılır.
- Density/eccentricity merkezi keşif anlatısı kaldırılır.
- Formal validation ve confirmation bölümleri `not claimed` olarak kapanır.
- Follow-up bölümü contrast, source imaging, spectroscopy ve RV ihtiyacını
  açıklar.

## 15. Artifact, kod ve yeniden üretilebilirlik kuralları

- Her bilimsel çalışma paketi için sonuç görülmeden protokol dosyası gerekir.
- Her protocol artifact upstream hashlerini, yazılım sürümünü ve karar eşiklerini
  içermelidir.
- `acceptable`, `stable`, `consistent`, `replicated`, `nominal coverage` ve
  `independent agreement` gibi nitel kapılar gerçek veri çalışmadan sayısal hale
  getirilmelidir.
- Her protokol simulation sayısı, çoklu-test düzeltmesi, missing-data desteği,
  optimizer/sampler toleransı, model ağırlık kuralı ve başarısızlık tetikleyicisi
  gerektiriyorsa bunları açıkça yazmalıdır.
- Ham ve immutable artifactler overwrite edilmez.
- Yeni remediation yeni dosya adı ve schema version kullanır.
- Başarısız denemeler silinmez; `invalid`, `quarantined` veya `diagnostic_only`
  olarak etiketlenir.
- Her branch/fold/start satır düzeyinde provenance taşımalıdır.
- Random seedler protokolde sabitlenmelidir.
- Paralel çalışma deterministik sonuç birleştirmesi kullanmalıdır.
- Önce sentetik/unit test, sonra gerçek veri, sonra artifact verify-only, sonra
  faz testi uygulanmalıdır.
- Tam pytest paketi büyük bilimsel milestone sonunda çalıştırılır; her küçük
  belge değişikliğinde zorunlu değildir.
- Release manifesti her fazda üretilmez.

## 16. Paketleme ve yayın politikası

Bilimsel analiz sırasında yapılmayacaklar:

- Her fazdan sonra release ZIP üretmek.
- Her küçük değişiklikte arXiv veya Zenodo paketi yenilemek.
- Bilimsel değerler dondurulmadan final PDF/DOI yazmak.
- Bayat mathematical audit veya eski package `PASS` kaydını güncel kanıt saymak.

Paketleme yalnız şu kilometre taşlarında yapılır:

1. İsteğe bağlı dahili checkpoint: Faz 6R kararı ve Yol A/B seçimi.
2. Bilimsel freeze: bütün hedeflenen iddialar kapandıktan sonra.
3. Final release: WP-29B ve WP-30 geçtikten sonra.

Final sırada:

1. Canonical TeX bilimsel olarak dondurulur.
2. Final TeX üzerinde matematik ve claim audit çalışır.
3. PDF derlenir ve görsel denetlenir.
4. Tam test paketi çalışır.
5. Release manifesti üretilir.
6. Reproducibility ve arXiv ZIP'leri oluşturulur.
7. Zenodo deposit yüklenir ve indirilen dosya hash'i doğrulanır.
8. DOI ancak çözülür ve hash doğrulanırsa README/CFF/makaleye yazılır.

## 17. Stop kuralları ve sonuç avcılığını önleme

- Bir kapı başarısız olduğunda tercih edilen sonucu veren yeni seed aranmaz.
- Bir dal yalnız sonucu kötü olduğu için çıkarılmaz.
- Eşikler sonuçtan sonra değiştirilmez.
- En fazla bir ana remediation ve aynı ilk protokolde gerçek veri görülmeden
  yöntemi/tetikleyicisi dondurulmuş bir maddi olarak farklı fallback uygulanır.
- Fallback de başarısızsa iddia zayıflatılır veya kaldırılır.
- Dış veri yoksa simülasyon dış gözlemin yerine geçirilmez.
- `PASS` almak projenin amacı değildir; geçerli bilimsel kapanış amaçtır.
- Her güçlü iddia için tek bir yetkili artifact zinciri bulunmalıdır.

## 18. Tamamlanma tanımı

### 18.1 Yol A tamamlanma koşulları

- Faz 6R geçmiştir.
- Native-cadence circular posterior bütün yakınsama kapılarını geçmiştir.
- Reduction, baseline, noise, timing, hierarchy, LD, stellar, dilution ve host
  belirsizlikleri taşınmıştır.
- Enjeksiyon ve posterior-predictive kapılar geçmiştir.
- Eccentricity ve FPP yalnız kendi ek kapıları geçerse; mass ise yalnız gerçek
  hedefe özgü RV ve WP-27B geçerse raporlanmıştır.
- Dış gözlem eksikleri açıkça belirtilmiştir.
- Makale, tablo ve şekiller aynı adopted artifact zincirine bağlıdır.

### 18.2 Yol B tamamlanma koşulları

- Faz 6 başarısızlığı gizlenmemiştir.
- Native-cadence ve eccentricity sayıları final ölçüm olarak sunulmamıştır.
- Formal FPP, validation, mass ve confirmation iddiaları yoktur.
- 2.6 yalnız model-koşullu oran, sigma değildir.
- Host ve physical radius açıkça koşulludur.
- Astrosismoloji tamamen çıkarılmıştır.
- Her başarısız faz `FAIL_CLAIM_REMOVED`, `NOT_CLAIMED`, `REMOVED` veya
  `BLOCKED_EXTERNAL` durumuyla kapanmıştır.
- Dar kapsamlı aday makalesi kendi iddia düzeyinde tutarlıdır.

### 18.3 WP-30 nihai kabul kapısı

- Yakınsamamış final aralık sayısı: 0.
- Kaynaksız sayı sayısı: 0.
- Gizli informative prior/bound sayısı: 0.
- İddia matrisi uyumsuzluğu: 0.
- Başarısız kapıdan sızan güçlü iddia sayısı: 0.
- Her final sayı tek bir adopted posterior/artifacte bağlı.
- İkinci okuyucu claim audit tamamlanmış.
- Final TeX üzerinde mathematical audit tamamlanmış.
- Final PDF, testler ve release hashleri güncel.

## 19. İlk uygulanacak somut adımlar

1. Yol A'nın hedeflendiğini ve Faz 6R başarısız olursa Yol B'ye dönüleceğini
   karar kaydına yaz.
2. `data/faz6r_numerical_remediation_protocol.json` taslağını yalnız yöntem ve
   değişmezlerle oluştur.
3. KKT/Newton eşiklerini belirlemek için sentetik kalibrasyon testlerini yaz.
4. Full-start spread ve optimizer-status bağımsız stationarity testlerini ekle.
5. Gerçek veri çalıştırmadan protokol ve testleri gözden geçirip hashle.
6. Aynı 24 dalın tamamında ana Faz 6R çalışmasını yap; yalnız kayıtlı tetikleyici
   oluşursa aynı protokoldeki tek fallback'i uygula.
7. Faz 6R gate auditini üret; ana veya kayıtlı fallback geçerse WP-07/08, ikisi
   de geçmezse Yol B.
8. Faz 6R sürerken bağımsız olarak WP-11 stellar protokolünü başlat.
9. WP-28 ile astrosismolojiyi canonical metinden çıkarma listesini hazırla.
10. WP-09A formal sektör istatistiğini doğrula.
11. WP-13 Gaia/PRF hazırlık artifactlerini üret.
12. WP-19A yakınsama protokolünü dondur.
13. Makalenin güçlü iddialarını WP-00 kapsamında hemen düzelt.
14. Bilimsel freeze'e kadar release ZIP/DOI/manifest yenilemesini ertele.

## 20. Kısa karar özeti

Şu anda doğru sonraki işlem Faz 7'yi başlatmak değildir. Önce, mevcut V2
sonucunu değiştirmeyen ayrı Faz 6R sayısal remediation protokolü hazırlanmalıdır.
Bu çalışma K0 modelini aynı 24 dalın tamamında bağımsız stationarity sertifikası
ile sınar. Geçerse tam native-cadence Yol A açılır. Geçmezse daha fazla sonuç
aramadan Yol B'ye geçilir ve makale mevcut kanıtın desteklediği dar aday kapsamı
içinde tamamlanır. Faz 11, Faz 9'un formal kısmı, PRF hazırlığı, astrosismolojiyi
çıkarma ve makale iskeleti bu karar beklenmeden paralel ilerleyebilir.

## 21. Günlük uygulama kaydı: 2026-07-23

### 21.1 Bugün tamamlanan işler

1. Faz 6R için bir sentetik kalibrasyon denemesi yapıldı; ancak eşik formülü,
   güvenlik katsayıları ve solver ayarları kullanıcı tarafından önceden
   onaylanmamıştı. Bu deneme bilimsel karar olarak benimsenmedi.
2. Karışıklık yaratmaması için bu onaysız ara denemeye ait protokol, kalibrasyon,
   manifest, script ve test dosyaları çalışma ağacından kaldırıldı. Sonuç yalnız
   bu günlük kaydında yöntemsel ders olarak tutulmaktadır.
3. Kullanıcı kararıyla Faz 6R yöntem incelemesine yeniden açıldı:
   - bilimsel yol `UNDECIDED`;
   - Faz 7 kapalı;
   - yeni gerçek-data Faz 6R fit sayısı sıfır;
   - kullanıcı onayı olmadan yeni eşik, benchmark veya gerçek-data fit yok.
5. WP-00 kapsamında canonical makale ihtiyatlı robustness/candidate-assessment
   diline geçirildi. Yakınsamamış native-cadence aralıklar, merkezi
   density/eccentricity iddiaları ve astrosismoloji bölümü çıkarıldı;
   phase-folded fit `descriptive reference` olarak etiketlendi. Bu metin güvenli
   çalışma taslağıdır; Yol B'nin kullanıcı tarafından nihai seçildiği anlamına
   gelmez.
6. WP-09A formal sektör heterojenliği bağımsız olarak tamamlandı ve `PASS` verdi:
   - `chi2=29.84993816215844`;
   - `dof=5`;
   - `p=1.5786269411100997e-5`;
   - formal ağırlıklı ortalama `2691.94 +/- 25.89 ppm`;
   - scatter-scaled ortalama hatası `63.27 ppm`.
7. WP-09A sektör tablosuna kamera, CCD, optimal aperture piksel sayısı,
   CROWDSAP, FLFRCSAP üstverisi, kullanılan olay sayısı ve background aralığı
   eklendi. Formal heterojenliğin nedeni astrofiziksel olarak ilan edilmedi.
8. Canonical TeX başarıyla derlendi. Final matematik audit/release manifesti
   bilimsel freeze olmadığı için yenilenmedi.
9. Tam test paketi `85 passed` verdi.
10. VS Code/Antigravity içinde `google.colab 0.8.1` eklentisi doğrulandı. Mevcut
    Faz 6R kodu NumPy/SciPy/celerite tabanlı ve CPU ağırlıklı olduğu için bir
    saatlik Colab GPU hakkı bu aşamada kullanılmadı; GPU ancak JAX/CuPy gibi
    açıkça onaylanmış yöntem değişikliği veya GPU-uygun MCMC/enjeksiyon işi için
    değerlendirilecek.

### 21.2 Bugün değiştirilmeden korunan bilimsel durum

- Faz 1, Faz 2 ve Faz 3 `PASS` durumundadır.
- Faz 4 `CONDITIONAL_PASS` durumundadır.
- Faz 5 `FAIL`, Faz 5B `CONDITIONAL_CONTINUE` durumundadır.
- Faz 6'nın yetkili sonucu `FAIL_STATIONARITY` olarak korunmaktadır.
- Altı sektörde kalıcı transit-benzeri sinyal vardır.
- Sinyalin gökyüzü kaynağı, gezegensel doğası, formal FPP'si, kütlesi ve
  eccentricity'si belirlenmemiştir.
- “Non-candidate/elendi” sonucu desteklenmemektedir. Yayınlanabilir mevcut çerçeve,
  kapsamlı fakat fiziksel iddiaları ihtiyatlı bir robustness ve candidate
  assessment çalışmasıdır.

### 21.3 Bugünkü stop noktası

Bugün yeni gerçek-data Faz 6R çalışması başlatılmamıştır. Proje aşağıdaki karar
noktasında güvenli biçimde durdurulmuştur:

```text
mevcut V2 sonucu
  -> kullanıcı-onaylı olmayan sentetik kalibrasyon benimsenmedi ve ara dosyaları silindi
  -> Faz 6R yöntem incelemesi açık
  -> Yol A/B kararı henüz verilmedi
  -> Faz 7 kapalı
```

### 21.4 Sonraki oturumun ilk işi

Yeni hesaplamadan önce kullanıcıya tek sayfalık, anlaşılır bir Faz 6R yöntem
özeti sunulacaktır. Özet en az şunları içerecektir:

1. V2'deki iki line-search durumunun neden bilimsel mod ayrışması olmayabileceği.
2. Aynı 24 dal ve üç başlangıcın neden korunacağı.
3. Optimizer `success` bitinin tanısal mı kapı mı olacağı.
4. Objective/parametre spread, gradient, Hessian, bound ve bağımsız solver
   eşiklerinin her birinin anlamı ve sayısal değeri.
5. Beklenen CPU süresi ve üretilecek artifactler.
6. Geçme, başarısızlık ve stop kuralları.

Kullanıcı bu özeti açıkça onaylamadan yeni protokol “dondurulmuş” sayılmayacak,
Colab/yerel gerçek-data hesabı çalıştırılmayacak ve Yol A/B kararı
kesinleştirilmeyecektir.

### 21.5 Onay sonrası Faz 6R sonucu

Kullanıcı yöntem özetini onayladıktan sonra aynı Faz-6 V2 K0 white+jitter
modeli, aynı 24 Faz-5B dalı ve dal başına aynı üç başlangıçla gerçek-data Faz
6R çalışması dört yerel CPU worker kullanılarak tamamlandı. Yeni bir gürültü
modeli, dal elemesi, seed araması veya bilimsel fallback uygulanmadı.

İlk ara değerlendirmede iki-adımlı finite-difference gradient tanısı yanlışlıkla
stationarity kapısına dahil edilmişti. Bu, çalışma öncesinde açıklanan “gradient
tanısal; esas kabul üç başlangıç ve bağımsız Powell uzlaşmasıdır” kuralıyla
çeliştiği için bilimsel sonuç olarak benimsenmedi. Eşik sonuç lehine
değiştirilmedi: gradient değerleri CSV'de tanı olarak korundu, kapı önceden
açıklanan sekiz kontrole döndürüldü ve bu ayrımı sabitleyen regresyon testi
eklendi.

Yetkili Faz 6R sonucu:

- stationarity: `24/24 PASS`;
- pozitif-tanımlı tam-rank geometri Hessianı ve Laplace draw desteği: `24/24 PASS`;
- beta desteği: kayıtlı altı zaman ölçeğinin tamamında mevcut;
- ağırlıklı beta değerleri: `1.13844`, `1.22621`, `1.29361`, `1.28827`,
  `1.22785`, `1.19004` (`20`, `40`, `80`, `160`, `320`, `360` dakika);
- maksimum ağırlıklı beta: `1.2936064512125263`;
- önceden kayıtlı beta üst sınırı: `1.2`;
- nihai durum: `FAIL_RESIDUAL_CORRELATION`;
- Faz 7: kapalı.

Bu sonuç, eski V2 line-search/stationarity problemini sayısal olarak giderir;
ancak değişmeden korunan K0 white+jitter modelinin transit-zaman ölçeğindeki
residual korelasyonu yeterince açıklamadığını gösterir. Stop kuralları gereği
Faz 6R PASS ilan edilmez, yeni bir eşik veya sonuç-sonrası model aranmaz ve proje
Yol B'nin dar, fiziksel iddiaları ihtiyatlı candidate-assessment kapsamına döner.
Yetkili sonuç `outputs/faz6r_result.json`, dal checkpointi
`outputs/faz6r_joint_fits.csv` ve geometri drawları
`data/faz6r_geometry_draws.npz` içindedir.
