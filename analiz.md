# TOI-3492.01 Projesini Baştan Sona Anlama ve Devam Planı

Son güncelleme: 2026-07-23

Bu belge projenin ne yaptığını, hangi sonuçların sağlam olduğunu, nerede sorun
çıktığını ve bundan sonra ne yapılması gerektiğini teknik jargona boğmadan
anlatır. Amaç bir faza `PASS` yazdırmak değil, bu makalenin TOI-3492.01 için
yapabileceği en kapsamlı ve dürüst fotometrik analizi tamamlamaktır.

## 1. Önce tek paragrafta bütün hikaye

TESS, TOI-3492.01 adlı adayda yaklaşık 9.22 günde bir tekrarlayan bir parlaklık
düşüşü gördü. Bu düşüş altı ayrı TESS sektöründe tekrar ediyor. Dolayısıyla
ortada gerçek ve tekrar eden bir transit-benzeri sinyal olduğuna dair güçlü
fotometrik kanıt var. Sorun sinyalin hiç olmaması değil. Sorun, sinyalin kesin
büyüklüğünü ve şeklini ölçmeye çalıştığımızda sonucun veriyi nasıl temizlediğimize,
transitin çevresinden kaç saat veri aldığımıza, arka plan eğrisini nasıl
çıkardığımıza ve zaman bağlantılı gürültüyü nasıl modellediğimize duyarlı olması.
Mevcut beyaz-gürültü modeli bu zaman bağlantılı kalıntıyı yeterince açıklamadı.
Bu yüzden henüz nihai doğal-kadans transit geometrisi üretilemedi. Sağlıklı
devam noktası Faz 1'e dönmek veya tek bir modeli keyfî seçmek değildir. Faz 1-4
ve Faz 5B korunmalı; Faz 5B'den sonra Faz 6 gürültü modeli, önceden belirlenmiş
ve yapay veride doğrulanmış yeni bir yöntemle yeniden kurulmalıdır.

## 2. Bu projenin amacı tam olarak ne?

Bu çalışma bir TESS fotometrik karakterizasyon çalışmasıdır. Temel sorular
şunlardır:

1. Yıldızın ışığında gerçekten tekrar eden bir düşüş var mı?
2. Bu düşüş kaç günde bir tekrar ediyor?
3. Düşüş altı sektörde de görülüyor mu?
4. Düşüşün derinliği, süresi ve şekli güvenilir biçimde ölçülebiliyor mu?
5. Sonuç veri temizleme, pencere, arka plan ve gürültü modeline ne kadar duyarlı?
6. Düşüşün hedef yıldızdan geldiğini TESS pikselleriyle gösterebiliyor muyuz?
7. Gezegen, yıldız çifti veya arka plandaki başka bir kaynak olasılıklarını ne
   kadar ayırabiliyoruz?
8. Yıldız özellikleriyle transit şekli birbiriyle tutarlı mı?
9. Bu veriden yarıçap, yoğunluk ve eksantriklik hakkında ne kadar güçlü konuşmak
   mümkündür?

Bu makalenin tamamlanması için nesnenin mutlaka "kesin gezegen" çıkması gerekmez.
Analiz eksiksiz yapılır ve sonuç "güçlü ama doğrulanmamış aday" çıkarsa makale
yine tamamlanmış olur. Tamamlanmak ile istenen sonucun çıkması aynı şey değildir.

## 3. Basit sözlük

Raporun geri kalanını anlamak için kullanılan kelimeler:

| Kelime | Basit anlamı |
|---|---|
| Transit | Bir cismin yıldızın önünden geçerken ışığı azaltması |
| Transit-benzeri | Transit gibi görünen, fakat kaynağı ve gezegen doğası henüz kesin olmayan düşüş |
| Sektör | TESS'in gökyüzünün aynı bölgesine baktığı ayrı gözlem dönemi |
| Cadence / kadans | TESS'in ne sıklıkla bir parlaklık ölçümü yaptığı; burada ana veri 120 saniyelik |
| Native cadence / doğal kadans | Veriyi zaman içinde katlayıp binlemeden, ölçüldüğü 120 saniyelik noktalarla kullanmak |
| Folded / katlanmış veri | Farklı transitleri aynı faz üzerine üst üste koymak |
| Binned / binlenmiş veri | Birçok ölçümü zaman kutularında ortalamak |
| Reduction / indirgeme | Ham teleskop verisini temizleyip kullanılabilir ışık eğrisine dönüştürme yöntemi |
| Baseline | Transitin dışındaki yıldız parlaklığının yerel eğilimi |
| Pencere | Her transit merkezinin çevresinden analize alınan toplam zaman |
| Polinom | Baseline eğrisini sabit, doğrusal veya eğrisel anlatan basit matematiksel şekil |
| Beyaz gürültü | Bir ölçümdeki hatanın sonraki ölçümle bağlantısız olduğu rastgele gürültü |
| Kırmızı/korelasyonlu gürültü | Yakın zamanlardaki hataların birbirine benzediği, zaman bağlantılı gürültü |
| Kernel | Korelasyonlu gürültünün zamana göre nasıl davrandığını anlatan model |
| Dal / branch | Maske, pencere ve polinom gibi seçimlerin belirli bir birleşimi |
| Posterior | Veriyi ve varsayımları birlikte kullanınca parametreler için elde edilen olasılık dağılımı |
| Yakınsama | Farklı başlangıçlardan yapılan hesapların aynı güvenilir sonuca gelmesi |
| Gate / kapı | Analiz başlamadan önce belirlenen geçme koşulu |
| Beta | Veriyi zaman içinde ortalayınca kalan gürültünün beyaz-gürültü beklentisine oranı |
| ELPD | Bir modelin görmediği veriyi ne kadar iyi tahmin ettiğini karşılaştırmak için kullanılan skor |
| PRF | Bir gökyüzü kaynağının TESS piksellerine nasıl yayıldığını anlatan görüntü modeli |
| FPP | Sinyalin gezegen yerine yanlış-pozitif senaryodan gelme olasılığı |

## 4. Projenin başlangıcındaki durum

İlk analizlerde bütün transitler aynı faz üzerine katlandı ve veri binlendi. Bu
görsel olarak temiz bir transit profili üretti. Yaklaşık sonuçlar şunlardı:

| Nicelik | Betimleyici referans sonuç |
|---|---:|
| Periyot | 9.2224171 gün |
| Yarıçap oranı, `Rp/Rstar` | yaklaşık 0.055 |
| Transit derinliği | yaklaşık 3000 ppm |
| Transit süresi | yaklaşık 5.2 saat |
| Sinyalin görüldüğü 120-s sektör sayısı | 6 |

Bu başlangıç sonucu "ortada incelenmeye değer bir sinyal var" demek için
kullanışlıydı. Fakat nihai fiziksel ölçüm olmak için yetersizdi. Çünkü veriyi
katlamak ve binlemek bazı problemleri saklayabilir:

1. Bir sektör diğerlerinden farklıysa üst üste koyunca fark görünmez hale gelir.
2. Bir transit diğerlerinden erken veya geç geldiyse şekil yapay olarak yayılır.
3. Zaman bağlantılı gürültü binleme sırasında olduğundan küçük görünebilir.
4. Arka plan veya pencere seçiminin etkisi tek bir düzgün eğri içinde kaybolabilir.
5. Çok sayıda nokta ortalandığı için hata çubukları gerçekte olduğundan fazla
   iyimser görünebilir.

Başlangıç makalesinde transit yoğunluğu ile katalog yıldız yoğunluğu arasındaki
yaklaşık 2.6 oran fazla güçlü yorumlanmıştı. Bazı metinlerde bunun 4.3 standart
sapmalık keşif gibi sunulma riski vardı. Eksantriklik için de ölçülmüş sonuç gibi
okunabilecek ifadeler bulunuyordu. Oysa native-cadence zincirleri ve gürültü
modeli henüz bu gücü desteklemiyordu.

Buradaki temel başlangıç hatası şuydu:

> Temiz görünen katlanmış/binlenmiş referans fit, doğal-kadans ve sektör-duyarlı
> sağlamlık analizi tamamlanmadan fiziksel olarak fazla güçlü yorumlandı.

## 5. Faz 0: Makaledeki iddiaları denetleme

### 5.1 Ne yapıldı?

Makaledeki önemli cümleler tek tek sınıflandırıldı. Şu sorular ayrı kapılara
ayrıldı:

1. Sinyal var mı?
2. Sinyal hedef yıldız üzerinde mi?
3. Fiziksel yarıçap güvenilir mi?
4. Yıldız yoğunluğu farkı güvenilir mi?
5. Eksantriklik ölçüldü mü?
6. İstatistiksel doğrulama var mı?
7. Kütle veya dinamik teyit var mı?
8. Astrosismoloji gerçekten bilgi veriyor mu?

Toplam 24 maddelik bir iddia matrisi oluşturuldu. Yakınsamayan doğal-kadans
sonuçlarının final ölçüm olarak kullanılmaması, 2.6 değerinin sigma değil oran
olduğu ve gezegenin doğrulanmadığı açıklaştırıldı.

### 5.2 Ne düzeldi?

Güncel `toi3492_characterization.tex` büyük ölçüde daha güvenli dile geçirildi:

1. 4.3-sigma yoğunluk keşfi çıkarıldı.
2. Ölçülmüş eksantriklik iddiası çıkarıldı.
3. Astrosismoloji bölümü çıkarıldı.
4. Katlanmış fit "betimleyici referans" olarak işaretlendi.
5. Kütle, doğrulama, teyit ve hedef-kaynak iddiaları kaldırıldı.

### 5.3 Neden Faz 0 hâlâ resmen kapanmış sayılmamalı?

Makale değişti, fakat son TeX üzerinde yeni bilimsel iddia denetimi ve matematik
denetimi çalıştırılmadı. Eski audit farklı bir TeX hash'ine bağlı. Ayrıca makalede
Faz 6R'nin hiç çalıştırılmadığını söyleyen bayat cümle ve yakınsamayan bir
analizden kalan sayısal aralık bulunuyor.

Bu nedenle doğru durum şudur:

> Faz 0'ın önemli metin düzeltmeleri yapıldı; fakat güncel makale yeniden audit
> edilmeden Faz 0 resmen `PASS` değildir.

## 6. Faz 1: Ham veriyi doğru aldık mı?

### 6.1 Ne yapıldı?

TESS'ten gelen ham ürünler envanterlendi. Toplam 18 ürün doğrulandı:

1. Altı adet 120-s ışık eğrisi ürünü.
2. Altı adet 120-s piksel ürünü.
3. Üç adet 20-s ışık eğrisi ürünü.
4. Üç adet 20-s piksel ürünü.

Her dosyanın boyutu, SHA-256 hash'i, tablo kolonları, zaman bilgisi, sektör,
kamera, CCD, cadence ve aperture bilgileri kontrol edildi.

### 6.2 Neden önemliydi?

Ham dosya yanlışsa sonraki bütün analiz doğru görünse bile yanlış olur. Burada
"hangi noktayı neden attık" sorusunun cevabını veren cadence ledger'ları da
oluşturuldu.

### 6.3 Sonuç

Faz 1 `PASS`.

1. Beklenen 18 ürünün 18'i mevcut.
2. Dosya hash'leri eşleşiyor.
3. Zaman dönüşümü tolerans içinde.
4. 120-s ve 20-s verinin aynı fiziksel gözlemin farklı örneklemeleri olduğu
   kaydedildi.

Bu fazı yeniden yapmak için bir neden yok.

## 7. Faz 2: Kaç transit olayı gerçekten gözlenmiş?

### 7.1 Ne yapıldı?

Resmi periyot ve başlangıç zamanı kullanılarak TESS gözlem aralığına düşmesi
beklenen bütün transitler listelendi. Sadece güzel görünen olaylar seçilmedi.
Olay sınıflandırması transit derinliğine bakmadan yapıldı.

### 7.2 Sonuç

Toplam 18 beklenen olay bulundu:

1. 16 olay kullanılabilir ve tam kapsamalı.
2. 2 olay veri boşluğuna denk geliyor.
3. Kullanılan 16 olay altı sektöre dağılıyor.
4. 20-s olaylar ikinci bağımsız transit sayılmıyor.

Bu önemli, çünkü aynı olayı 20-s ve 120-s veride iki ayrı kanıt gibi saymak
yanlış olurdu.

### 7.3 Durum

Faz 2 `PASS`. Bu fazı yeniden yapmak için bir neden yok.

## 8. Faz 3: Teleskop veya veri kalitesi sahte sinyal üretiyor mu?

### 8.1 Ne kontrol edildi?

Her transit çevresinde şu bilgiler denetlendi:

1. TESS kalite bitleri.
2. Uydu yönelim bozuklukları.
3. Momentum boşaltmaları ve benzeri operasyonlar.
4. Arka plan ışığı.
5. Piksel/centroid hareketleri.
6. CBV sistematik düzeltmeleri.
7. Yakındaki kontrol yıldızları.
8. Farklı kalite maskeleri.

### 8.2 Sonuç

Gerekli kalite, telemetry, CBV ve kontrol-yıldızı kapıları geçti. Sinyali tek
başına açıklayan açık bir TESS operasyonu bulunmadı.

### 8.3 Durum

Faz 3 `PASS`. Bu, "kesin gezegen" demek değildir. Yalnızca bilinen basit veri
kalitesi sorunlarının sinyali açıkça açıklamadığını söyler.

Bu fazı yeniden yapmak için bir neden yok.

## 9. Faz 4: Veriyi dört farklı şekilde temizleme

### 9.1 Neden dört yöntem kullanıldı?

Teleskop verisini temizlemenin tek yolu yoktur. Aynı ham gözlemler şu dört
yöntemle işlendi:

| Dal | Basit açıklama |
|---|---|
| `pdcsap` | TESS/SPOC tarafından hazırlanmış standart düzeltilmiş ışık eğrisi |
| `sap_cbv` | Daha ham SAP ışık eğrisine CBV sistematik düzeltmesi uygulanması |
| `tpf_pipeline` | Piksel dosyasından standart aperture ile yeniden ışık eğrisi çıkarılması |
| `tpf_pld` | Piksel seviyesindeki hareketleri kullanarak PLD düzeltmesi yapılması |

### 9.2 Ne bulundu?

Dört yöntem de sinyali geri kazandı ve kendi kabul kontrollerini geçti. Fakat
transit geometrisi tamamen aynı çıkmadı. En büyük fark, önceden belirlenen 0.5
birleşik-sigma sınırını aşıp yaklaşık 0.90 birleşik sigma oldu.

Bu yüzden Faz 4 doğrudan `PASS` değil, `CONDITIONAL_PASS` aldı. Anlamı:

> Dört yöntem de kullanılabilir; ancak temizleme yönteminden gelen fark final
> belirsizliğe ayrıca taşınmalıdır.

### 9.3 Burada hata yaptık mı?

Hayır. Dört yöntemin aynı sonucu vermemesi verinin bir özelliğidir. Tek bir
yöntemi sırf istediğimiz sonucu verdiği için seçmek bilimsel hata olurdu.

Doğru yapılan şeyler:

1. PDCSAP'a ikinci kez CROWDSAP uygulanmadı.
2. Dört reduction bağımsız gözlem gibi çarpılmadı.
3. Aralarındaki fark ayrı sistematik olarak tutuldu.
4. Enjeksiyon ekranları çalıştırıldı.

Bu fazın sonuçları korunmalıdır.

## 10. Faz 5: Transit çevresinden ne kadar veri almalı ve baseline'ı nasıl çizmeliyiz?

### 10.1 Sorun neydi?

Bir transit yaklaşık 5.2 saat sürüyor. Transit çevresindeki yıldız parlaklığını
anlamak için transit öncesi ve sonrası veri gerekir. Ama ne kadar veri alınacağı
sonucu etkileyebilir:

1. Çok kısa pencere seçilirse baseline iyi ölçülemez.
2. Çok uzun pencere seçilirse başka yavaş değişimler modele girer.
3. Baseline sabit alınırsa gerçek eğim kaçabilir.
4. Çok esnek polinom alınırsa transit şeklinin bir bölümü baseline tarafından
   yenebilir.

### 10.2 Hangi seçenekler test edildi?

Beş pencere ve üç polinom derecesi kullanıldı:

| Seçim | Değerler |
|---|---|
| Toplam pencere | 13, 16, 20, 26 ve 32 saat |
| Polinom derecesi | 0, 1 ve 2 |

Toplam 15 model hücresi oluştu. Örneğin `W16_P1`, 16 saatlik pencere ve doğrusal
baseline demektir.

### 10.3 Neden sadece en iyi skorlu modeli seçmedik?

En iyi ham tahmin skoru `W16_P1` modelindeydi. Fakat önceden belirlenen kural
şuydu:

> Tek model seçilecekse, diğer bütün modellerden belirsizliği hesaba kattıktan
> sonra açıkça daha iyi olmalıdır.

`W16_P1` bu kadar açık üstünlük göstermedi. On bir model istatistiksel olarak
birbirine yeterince yakındı. Bu yüzden "en yüksek sayı onda çıktı" diyerek tek
model seçmek doğru değildi.

### 10.4 Faz 5 neden `FAIL` oldu?

Korunan modellerden `W26_P1`, yarıçap oranı ve transit süresi için karışımın
önceden belirlenen yüzde 68 aralığının hemen dışında kaldı. Basit anlamı:

> Makul bir pencere/baseline seçimi, sonucu hesapladığımız ana belirsizlik
> bandının dışına itecek kadar değiştirebiliyordu.

Bu yüzden mevcut karışımın model-seçimi belirsizliğini yeterince güvenli
kapsamadığına karar verildi ve Faz 5 `FAIL` kaldı.

### 10.5 Bu başarısızlık ne anlama gelmiyor?

Şunları söylemez:

1. Transit yok.
2. Veri bozuk.
3. Analiz tamamen çöpe gitti.
4. Mutlaka `W16_P1` seçilmeli.
5. Mutlaka bütün çalışma Faz 1'den başlamalı.

Şunu söyler:

> Transit geometrisi baseline ve pencere seçimine düşündüğümüzden daha duyarlı.

Bu bilimsel bir bulgudur.

## 11. Faz 5B: Faz 5 sorununu gizlemeden ileri taşıma

### 11.1 Neden Faz 5B yapıldı?

Faz 5'in başarısızlığından sonra iki yanlış seçenek vardı:

1. En sevdiğimiz modeli seçip diğerlerini yok saymak.
2. Bütün model farklarını tek bir gelişigüzel hata sayısına dönüştürmek.

Bunlar yapılmadı. Bunun yerine farklı veri maskeleri, pencereler ve polinomlar
ayrı model dalları olarak korundu.

### 11.2 İki maske neydi?

| Maske | Basit anlamı |
|---|---|
| `raw_valid` | Faz 4'te geçerli kabul edilen cadence'ler |
| `reference_included` | Eski referans ürünle tam eşleşen, 60 cadence daha az içeren alt küme |

Toplam yaklaşık 102 bin cadence içinde sadece 60 cadence fark vardı. Fakat bu
küçük fark bazı pencere modellerinin korunup korunmamasını etkileyebiliyordu.

### 11.3 Kaç dal oluştu?

1. `raw_valid` maskesinde 11 dal.
2. `reference_included` maskesinde 13 dal.
3. Toplam 24 dal.
4. İki maskeye yüzde 50-yüzde 50 ön ağırlık.
5. Her maskenin içinde korunan modellere eşit koşullu ağırlık.

### 11.4 24 dalı taşımak hata mıydı?

Hayır. Önceki sözlü açıklamalarda "karar veremedik, her şeyi taşıdık ve bu hata
oldu" denmesi doğru değildi.

24 dalı taşımak şu nedenle doğru ve ihtiyatlıydı:

> Sonucu etkileyen makul analiz seçimlerini saklamak yerine görünür tuttuk.

Hata, bu dallardan birini sonuç güzel görünüyor diye seçmek olurdu. Faz 5B'nin
kendisi sorunun nedeni değildir. Faz 5'in `FAIL` durumunu da `PASS` yapmadı;
yalnız belirsizliği Faz 6'ya düzenli biçimde devretti.

### 11.5 Durum

Faz 5B `CONDITIONAL_CONTINUE`.

Bu, "Faz 5 artık geçti" demek değildir. "Faz 5 sorunu görünür biçimde taşındığı
için gürültü modeli denenebilir" demektir.

## 12. Faz 6: Gürültü modelini seçme

### 12.1 Neden gürültü modeli gerekiyor?

Transit dışındaki ışık eğrisi tamamen düz değildir. Yakın zamanlarda ölçülen
noktalar birbirine bağlı hareket edebilir. Bunun nedenleri yıldız aktivitesi,
arka plan, teleskop hareketi veya temizleme kalıntısı olabilir.

Bu bağlantıyı yok sayarsak:

1. Hata çubukları fazla küçük çıkabilir.
2. Transit süresi ve şekli fazla kesin görünür.
3. Baseline dalgalanması transit sinyaliyle karışabilir.
4. Yoğunluk ve eksantriklik gibi türetilmiş sonuçlar yapay olarak güçlü olur.

### 12.2 Hangi modeller karşılaştırıldı?

| Model | Basit anlamı |
|---|---|
| `K0_white` | Noktalar arasında zaman bağlantısı yok; yalnız beyaz gürültü ve ek jitter |
| `K1_ou` | Yakın zamanlardaki noktalar daha benzer, bağlantı zamanla üstel azalıyor |
| `K2_matern32` | Daha yumuşak bir zaman bağlantısı modeli |
| `K3_sho` | Salınım benzeri korelasyonu anlatabilen model |

Her model 24 dalda ve altı held-out sektörde test edildi:

`24 dal x 4 kernel x 6 sektör = 576 karşılaştırma`

576 hesabın 576'sı da sayısal olarak tamamlandı.

### 12.3 Korelasyonlu modeller daha iyi miydi?

Görmediği sektörü tahmin etme skorunda üç korelasyonlu model de K0 beyaz
gürültüden daha iyi görünüyordu:

| Model | K0'a göre yaklaşık tahmin iyileşmesi |
|---|---:|
| OU | 18.68 |
| Matérn-3/2 | 19.55 |
| SHO | 19.72 |

Bu önemli bir işarettir: Veride zaman bağlantılı yapı olma ihtimali vardır.

### 12.4 O zaman neden bu modellerden birini seçmedik?

Çünkü yalnız tahmin skorunun yüksek olması yetmiyordu. Modellerin kararlı ve
fiziksel olarak tanımlı çalışması da gerekiyordu. Üçünde de iki sorun görüldü:

1. Bazı gürültü parametreleri izin verilen sınırların kenarına dayandı.
2. Modelin K0'a göre kazancı, 60 cadence farkı olan iki maskede beklenenden fazla
   değişti.

İkinci sorun günlük dilde şöyle anlatılabilir:

> Model gerçekten genel bir gürültü yapısı öğrenmek yerine, küçük veri-seçimi
> farklarına fazla hassas davranıyor olabilir.

Bu yüzden OU, Matérn ve SHO doğrudan final model olarak kabul edilmedi. Buradan
"korelasyonlu gürültü yok" sonucu çıkmaz. Tam tersine tahmin skorları korelasyon
olabileceğini söylüyor; fakat kullanılan parametreleme ve karar kuralları kararlı
bir final model üretemedi.

## 13. Faz 6 V1: Gerçek bir sayısal hata

### 13.1 Ne oldu?

Karmaşık kernel'ler elenince K0 beyaz-gürültü modeliyle ortak fit yapılmaya
çalışıldı. 24 dalın her biri üç başlangıçtan çalıştırıldı. Toplam 72 optimizer
denemesi vardı.

İlk V1 çalışmasında 72 denemenin 72'si de başlangıç noktasından hareket etmedi.
Optimizer bir sonuç dosyası üretmiş olsa da gerçekte modeli optimize etmemişti.

### 13.2 Neden bu gerçek bir hatadır?

Bir programın `success` benzeri bir bayrak vermesi tek başına yeterli değildir.
Parametrelerin gerçekten hareket edip etmediği ve objective'in düştüğü kontrol
edilmelidir.

V1'de bu ilk kurulumda yeterince güvenli değildi. Sonraki audit bunu yakaladı ve
V1 şu şekilde işaretlendi:

`INVALID_NUMERICAL_RESULT`

V1'den çıkan beta veya geometri bilimsel sonuç olarak kullanılmamalıdır.

### 13.3 İyi tarafı ne?

Hata gizlenmedi. Sonuç iptal edildi, audit kaydına alındı ve ölçeklenmiş V2
çalışması yapıldı. Yani V1 hatası final bilimsel sonuç içine sessizce girmedi.

## 14. Faz 6 V2: Sayısal sorun büyük ölçüde düzeldi ama kapı geçmedi

### 14.1 Ne düzeldi?

V2'de parametre ölçeklemesi ve optimizer kurulumu düzeltildi:

1. Bütün dallarda objective düştü.
2. Bütün dallarda parametreler başlangıçtan hareket etti.
3. Farklı başlangıçlar yaklaşık aynı optimuma geldi.
4. 24 dalın 22'si bütün stationarity koşullarını geçti.

### 14.2 İki dal neden kaldı?

Şu iki dalda üç başlangıçtan biri line-search sonlandırma uyarısı verdi:

1. `raw_valid::W20_P0`
2. `reference_included::W32_P2`

Bu başarısız başlangıçlar da diğerleriyle yaklaşık aynı optimuma ulaştı. Bu,
farklı bir fiziksel çözümden çok sayısal line-search davranışına benziyordu.
Fakat önceden konan kural üç başlangıcın üçünün de geçmesini istiyordu.

### 14.3 Neden sonradan "önemli değil" deyip geçmedik?

Sonucu gördükten sonra kural değiştirmek sonuç avcılığı olurdu. Bu nedenle Faz 6
yetkili olarak `FAIL_STATIONARITY` kaldı. V2'de beta hesaplanmadı.

Bu katı ama bilimsel olarak doğru bir karardı.

## 15. Faz 6R: Stationarity düzeldi, fakat zaman bağlantılı kalıntı kaldı

### 15.1 Ne amaçlandı?

Faz 6R yeni bir fiziksel model aramak yerine aynı K0 beyaz-gürültü modelinin
sayısal stationarity sorununu bağımsız kontrollerle çözmeyi amaçladı.

### 15.2 Hesap sonucu neydi?

1. 24 dalın 24'ü stationarity kontrollerini geçti.
2. Geometri Hessian kontrolleri 24/24 geçti.
3. K0 optimizer'ın eski line-search sorunu giderildi.
4. Fakat residual beta kapısı geçmedi.

Beta sonuçları:

| Zaman ölçeği | Beta |
|---:|---:|
| 20 dakika | 1.1384 |
| 40 dakika | 1.2262 |
| 80 dakika | 1.2936 |
| 160 dakika | 1.2883 |
| 320 dakika | 1.2278 |
| 360 dakika | 1.1900 |

Önceden kullanılan üst sınır 1.20 idi. En yüksek beta 80 dakikada 1.2936 çıktı.

### 15.3 Beta 1.2936 günlük dilde ne demek?

Beyaz gürültüde noktaları zaman kutularında ortaladıkça gürültünün belirli bir
hızda azalması beklenir. Beta, gözlenen kalıntı gürültüsünü bu beklentiye böler.

1. Beta 1'e yakınsa beyaz-gürültü davranışı iyidir.
2. Beta 1.2936 ise 80 dakikalık ölçekte kalan saçılım beyaz-gürültü beklentisinden
   yaklaşık yüzde 29 daha büyüktür.
3. Bu, transit yok demek değildir.
4. Bu, K0 modelinin zaman bağlantılı kalıntıyı yeterince açıklamadığını söyler.

40-160 dakikalık ölçekler transit giriş/çıkış geometrisi için önemlidir. Bu
yüzden beta fazlalığını yok sayarak çok hassas geometri raporlamak doğru olmaz.

### 15.4 Faz 6R'nin kayıt/provenance sorunu

Hesap sonucu `outputs/faz6r_result.json` içinde var. Fakat Stage-2 planının
zorunlu tuttuğu `data/faz6r_numerical_remediation_protocol.json` dosyası yok.
Planlanan source manifest, ayrı gate audit, objective-equivalence ve bazı
gradient/diagnostic artifactleri de eksik.

Bu nedenle iki şeyi ayırmak gerekir:

1. Hesaplanan sonuç: `FAIL_RESIDUAL_CORRELATION`.
2. Süreç durumu: Tam preregistered ve hash-bağlı Faz 6R paketinin eksiksiz olduğu
   söylenemez.

Bu eksiklik beta değerini otomatik olarak uydurma yapmaz. Fakat Faz 6R'yi örnek
bir preregistered bilimsel kapı olarak sunmamızı engeller. Yeni çalışma bu
provenance açığını tekrarlamamalıdır.

## 16. WP-09A: Sektörlerde transit derinliği aynı mı?

Altı sektörün formal transit derinlikleri sabit bir değerle karşılaştırıldı.

Sonuçlar:

| Nicelik | Değer |
|---|---:|
| Ağırlıklı ortalama derinlik | 2691.94 ppm |
| Formal ortalama hata | 25.89 ppm |
| Ki-kare | 29.85 |
| Serbestlik derecesi | 5 |
| p-değeri | 0.0000158 |
| Saçılımla büyütülmüş ortalama hata | 63.27 ppm |

Formal hatalar altında sektör derinlikleri sabit değil. Fakat bunun nedeni henüz
bilinmiyor. Olası nedenler:

1. Kamera veya CCD farkı.
2. Aperture farkı.
3. Background farkı.
4. Reduction farkı.
5. Eksik modellenmiş korelasyonlu gürültü.
6. Yakındaki kaynakların katkısı.
7. Gerçek astrofiziksel değişim.

Veri şu anda bu nedenlerden hangisinin doğru olduğunu göstermiyor. Bu yüzden
"transit astrofiziksel olarak değişiyor" denemez.

WP-09A `PASS` demek, "derinlik sabit" demek değildir. Testin doğru biçimde
yapıldığını ve formal heterojenliğin yeniden üretildiğini söyler.

## 17. Şu ana kadar gerçekten neyi gösterdik?

Güvenle söylenebilenler:

1. TOI-3492.01 yönünde yaklaşık 9.2224171 günlük tekrar eden transit-benzeri
   sinyal var.
2. Sinyal altı 120-s TESS sektöründe görülüyor.
3. Beklenen 18 olaydan 16'sı kullanılabilir, 2'si veri boşluğunda.
4. Dört ayrı reduction sinyali geri kazanıyor.
5. Basit kalite, background, pointing ve kontrol-yıldızı denetimleri sinyali
   açıkça ortadan kaldırmıyor.
6. Sinyalin ölçeği kabaca dev-gezegen boyutu ile uyumlu olabilir.
7. Bu fiziksel boyut, olayın gezegensel olması, doğru yıldız üzerinde olması ve
   yıldız/dilution varsayımlarının doğru olması koşuluna bağlıdır.
8. Sektörlerin formal derinlikleri sabit-derinlik modeline uymuyor.
9. Transit geometrisi pencere, baseline, reduction ve gürültü modeline duyarlı.
10. Mevcut K0 beyaz-gürültü modeli 40-320 dakikalık kalıntı korelasyonunu yeterince
    açıklamıyor.

## 18. Henüz neyi göstermedik?

Şunlar henüz bilimsel olarak tamamlanmış sonuç değildir:

1. Nihai ve yakınsamış doğal-kadans transit geometrisi.
2. Kaynağın kesin olarak katalog hedef yıldızı olduğu.
3. Nesnenin kesin olarak gezegen olduğu.
4. Güvenilir fiziksel yarıçap posterioru.
5. Kalibre edilmiş yoğunluk uyumsuzluğu anlamlılığı.
6. Ölçülmüş eksantriklik.
7. Kalibre edilmiş formal FPP.
8. Ölçülmüş kütle.
9. İstatistiksel validation.
10. Dinamik confirmation.

Bu liste projenin boşa gittiği anlamına gelmez. Final modelden önce hangi
soruların açık olduğunu gösterir.

## 19. Neler gerçekten hataydı?

### 19.1 Bilimsel iddialar final modelden önce fazla güçlendirildi

Katlanmış/binlenmiş referans fit temiz görünüyordu. Fakat native-cadence,
sektör-duyarlı, korelasyonlu-gürültü ve model-belirsizliği kontrolleri bitmeden
yoğunluk ve eksantriklik anlatısı öne çıktı.

Doğru sıra şu olmalıydı:

`ham veri -> olaylar -> reduction -> baseline -> gürültü -> sektör/timing -> final fit -> fiziksel yorum`

İlk taslakta fiziksel yorum bu zincirin önüne geçti.

### 19.2 Doğal-kadans sağlamlık modeli çok geç merkezî hale geldi

Başlangıçta sağlam bir sektör-duyarlı native-cadence model kurulup sonra makale
yazılmalıydı. Bunun yerine referans fit ve yayın paketi büyük ölçüde hazırlandı,
sonra temel robustness kapıları eklendi. Bu yüzden sonradan çok sayıda güçlü
cümle geri çekilmek zorunda kaldı.

### 19.3 V1 optimizer'ın hareket etmediği ilk anda yeterince korunmadı

72 optimizer denemesinin hareket etmemesi doğrudan sayısal problemdi. Yalnız
`success` bayrağına güvenilmemesi gerekiyordu. Bu hata sonradan yakalandı ve V1
iptal edildi.

### 19.4 Faz 6R planlanan provenance standardını karşılamadı

Faz 6R çalıştı, fakat kendi planında zorunlu tutulan ayrı preregistration JSON'u,
hash zinciri ve tam audit artifact seti oluşmadı. Ayrıca gradient tanısının kapı
olup olmadığı çalışma sırasında düzeltilmek zorunda kaldı. Yeni yöntem gerçek
veriye uygulanmadan önce bu kararların tamamı yazılı ve hash'li olmalıdır.

### 19.5 Durum belgeleri güncel sonuçla eşitlenmedi

Şu an proje belgeleri birbiriyle çelişiyor:

| Dosya | Sorun |
|---|---|
| `outputs/release_status.json` | Faz 6R'yi çalıştırılmamış gösteriyor; oysa sonuç dosyası var |
| `outputs/release_status.json` | WP-09A'yı bir yerde tamamlanmış, başka yerde eksik gösteriyor |
| `docs/todo.md` | Faz 6R kararı ve astrosismoloji için eski durumu taşıyor |
| `README.md` | Faz 6R ve WP-09A güncel durumunu göstermiyor |
| `toi3492_characterization.tex` | Faz 6R'nin çalışmadığını söyleyen bayat cümle içeriyor |
| `provenance/SHA256SUMS.json` | Yeni TeX, Faz 6R ve WP-09A değişikliklerini kapsamıyor |

Bu belgeler düzeltilmeden yayın paketi yapılmamalıdır.

## 20. Neler hata değildi?

Şunları yanlış diye etiketlememeliyiz:

### 20.1 Faz 4'te dört reduction'ı karşılaştırmak hata değildi

Bu karşılaştırma gerekliydi. Sonuçların biraz farklı çıkması gizlenmesi değil,
belirsizliğe taşınması gereken bilgidir.

### 20.2 Faz 5'te tek model seçememek hata değildi

Veri tek bir pencere/baseline modelini açıkça üstün göstermedi. Zorla birini
seçmek hata olurdu.

### 20.3 Faz 5B'de 24 dalı taşımak hata değildi

Bu, makul analiz seçimlerinin sonucunu görünür tutan model-ortalama yaklaşımıdır.
24 dal bağımsız veri değildir ve bağımsızmış gibi çarpılmamıştır.

### 20.4 Faz 6'nın kapıyı geçmemesi hata değildir

Bir kapının başarısız olması analizin işini yaptığı anlamına gelebilir. Burada
kapı, yetersiz gürültü modelinin fazla kesin fiziksel sonuç üretmesini engelledi.

### 20.5 Beta 1.2936 "aday çöpe gitti" demek değildir

Bu sayı sinyalin yokluğunu değil, mevcut K0 modelinin residual korelasyonu eksik
modellediğini gösterir.

## 21. Proje neden bu noktaya geldi?

Sebep tek bir büyük hata değildir. Zincir şöyledir:

1. Katlanmış/binlenmiş fit temiz ve ikna edici göründü.
2. Bu fit üzerinden fiziksel yorumlar erken güçlendi.
3. Sonradan ham veri ve robustness denetimleri eklendi.
4. Dört reduction sinyali buldu ama küçük geometri farkları gösterdi.
5. Pencere ve baseline seçenekleri sonucu beklenenden fazla değiştirdi.
6. Bu belirsizlik Faz 5B'de dürüstçe 24 dala taşındı.
7. Korelasyonlu kernel'ler tahminde daha iyi göründü ama sınır ve maske-kararlılığı
   kontrollerini geçmedi.
8. K0 beyaz-gürültü modeli sayısal olarak önce çalışmadı, sonra düzeltildi.
9. Sayısal stationarity düzeldiğinde residual beta sınırı geçmedi.
10. Böylece mevcut modelin transit zaman ölçeğindeki korelasyonu açıklamadığı
    ortaya çıktı.

Kısa cevap:

> Sinyal kaybolmadı. Basit modelin verdiği kesinlik güvenilir çıkmadı.

## 22. Önceki sözlü açıklamalardaki yanlış yönlendirmelerin düzeltilmesi

Önceki açıklamalarda birkaç aşırı basitleştirme yapıldı. Doğruları şunlardır:

### 22.1 "Faz 4'te bir reduction seçmeliydik" doğru değil

Tek bir reduction seçmek, seçimin bilimsel ve önceden tanımlı bir gerekçesi yoksa
sonuç seçmek olur. Dört reduction belirsizliğini korumak daha doğru.

### 22.2 "Faz 5'te bir pencere seçmeliydik" doğru değil

Veri tek pencereyi açıkça üstün göstermedi. Keyfî seçim yapılmamalı.

### 22.3 "24 dal işi bozdu" doğru değil

24 dal işi bozmadı; zaten var olan model-seçimi belirsizliğini görünür yaptı.
Sorun, sonraki gürültü modelinin bu model evreninde kararlı ve yeterli sonuç
üretememesi.

### 22.4 "Makaleyi hemen küçültüp iki günde yayımlayalım" bu projenin hedefi değil

Kullanıcının hedefi bu makalede kapsamlı fotometrik analizi tamamlamak. Bu nedenle
önce Faz 6 metodunu bilimsel olarak düzeltmek gerekir. Sonuç yine doğrulanmamış
aday olabilir; fakat analiz yarım bırakılmış olmaz.

### 22.5 "Daha güçlü ikinci makale gerekir" zorunlu değil

Bu makale TESS fotometrisinin verebildiği bütün sonucu çıkarıp bitebilir. Dış
gözlem olmadan validation veya mass iddiası yapılamaması, fotometrik analizin
ikinci makaleye bırakılması anlamına gelmez.

## 23. Şimdi tam olarak nereden devam etmeliyiz?

Net cevap:

> Faz 1, 2, 3 ve 4 korunacak. Faz 5'in `FAIL` kaydı korunacak. Faz 5B'nin 24
> dallı handoff'u korunacak. Çalışma Faz 5B'den sonra, Faz 6 gürültü modeli yeni
> ve eksiksiz ön-kayıtlı bir yöntemle yeniden tasarlanarak devam edecek.

Faz 4'e dönüp bir reduction seçmeyeceğiz. Faz 5'e dönüp tek pencere seçmeyeceğiz.
Eski K0 hesabını farklı seedlerle tekrar tekrar koşturmayacağız.

### 23.1 Bu karar mevcut Stage-2 planını değiştiriyor mu?

Evet. `currentproblemstage2.md` içindeki mevcut stop kuralı, Faz 6R de geçmezse
başka gürültü modeli aramayı durdurup Yol B'ye dönmeyi söylüyor. Faz 6R sonucu
çıktıktan sonra belge de Yol B'ye dönüş kaydetmiş durumda.

Kullanıcının güncel hedefi ise bu makalede kapsamlı fotometrik modellemeyi
tamamlamak. Bu hedef doğrultusunda yeni bir korelasyonlu-gürültü geliştirme
aşaması açılacaksa eski stop kuralı sessizce yok sayılamaz. Önce tarihli bir plan
değişikliği yapılmalıdır.

Bu değişiklik şunları açıkça söylemelidir:

1. Eski Faz 6 ve Faz 6R sonuçları değişmeden başarısız kalır.
2. Eski beta eşiği geriye dönük değiştirilmez.
3. Yeni çalışma eski Faz 6R'nin üçüncü seed denemesi değildir.
4. Yeni çalışma, yetersiz olduğu görülen model ailesinin yerine açıkça yeni bir
   yöntem-geliştirme fazıdır.
5. Daha önce görülen bütün gerçek-veri sonuçları yeni protokolde açıklanır.
6. Yeni model ailesi ve stop kuralları gerçek veri yeniden çalıştırılmadan önce
   dondurulur.
7. Bu yeni yöntemin de başarısız olması halinde yeni sonuç avı yapılmaz; makale
   ölçülebilen sınırlarla tamamlanır.

Yani öneri eski sonucu `PASS` yapmaya çalışmak değildir. Projenin hedefini açıkça
değiştirip, ayrı ve denetlenebilir tek bir yöntem-geliştirme aşaması açmaktır.

## 24. Adım adım yeni çalışma planı

### Adım 1: Mevcut durumu tek bir doğru kayda sabitle

Yeni bilimsel hesap yapmadan önce durum belgeleri eşitlenmelidir.

Yapılacaklar:

1. Faz 6R hesap sonucu `FAIL_RESIDUAL_CORRELATION` olarak kaydedilecek.
2. Faz 6R'nin preregistration/provenance eksikleri açıkça yazılacak.
3. Faz 7'nin mevcut protokol altında kapalı olduğu yazılacak.
4. Eski Yol B stop kaydı korunacak ve yeni kapsamlı analiz kararı ayrı, tarihli
   plan değişikliği olarak eklenecek.
5. WP-09A `PASS`, fakat neden atanmamış olarak kaydedilecek.
6. Makaledeki "Faz 6R çalışmadı" cümlesi düzeltilecek.
7. Eski audit ve manifestlerin güncel olmadığı işaretlenecek.
8. Eski başarısız artifactler silinmeyecek veya üzerine yazılmayacak.

Bu adım yeni fizik üretmez. Projenin ne durumda olduğunu herkes için aynı hale
getirir.

### Adım 2: Faz 6 post-mortem analizi yap

Yeni model seçmeden önce mevcut 576 fit ve residual dosyaları kullanılarak şu
sorular cevaplanmalıdır:

1. OU, Matérn ve SHO parametreleri tam olarak hangi sektörlerde ve hangi dallarda
   sınıra dayandı?
2. İki maske arasındaki model-kazancı farkını hangi 60 cadence sürüklüyor?
3. Beta fazlalığını hangi sektörler ve hangi olaylar sürüklüyor?
4. 40-160 dakikalık korelasyon background, pointing, CBV veya bilinen TESS
   operasyonlarıyla bağlantılı mı?
5. Uzun pencere ve yüksek polinom GP ile aynı yavaş yapıyı açıklamak için rekabet
   ediyor mu?
6. Transit dışı veride seçilen gürültü modeli transit içeren ortak fitte neden
   kararsızlaşıyor?
7. Residual ACF ve periodogram hangi zaman ölçeklerini gösteriyor?

Bu aşamada yeni gerçek-veri modeli denenmeyecek. Amaç neden bozulduğunu anlamak.

### Adım 3: Yeni Faz 6 protokolünü yaz ve dondur

Yeni çalışma eski sonucun görüldüğünü açıkça yazmalıdır. Kör preregistration
gibi sunulmamalıdır.

Protokolde sonuç görülmeden önce şu kararlar bulunmalıdır:

1. Kullanılacak kesin 24 dal ve ağırlıkları.
2. Kullanılacak reduction handoff'u.
3. Denenecek sınırlı gürültü-modeli ailesi.
4. Kernel parametrelerinin dönüşümleri ve sınırları.
5. Sektörlere özel ve ortak parametrelerin hangileri olduğu.
6. Baseline ile gürültü modelinin aynı sinyali yemesini engelleyen kural.
7. Transit bölgesinin gürültü eğitiminde nasıl korunacağı.
8. Optimizer ve bağımsız doğrulayıcı.
9. MCMC sampler ve yakınsama eşikleri.
10. Residual ACF, beta ve periodogram eşikleri.
11. Beta'nın nihai kapı mı, tanı mı olduğu.
12. Enjeksiyon geri-kazanım ve coverage eşikleri.
13. Held-out sektör tahmin kuralı.
14. Başarısızlık ve stop kuralları.
15. Random seedler, yazılım sürümleri ve upstream hash'ler.
16. Üretilecek bütün artifact dosyaları.

Burada onlarca yeni kernel denenmemelidir. Mevcut sonuçlara dayanarak en fazla
birkaç fiziksel olarak gerekçeli model seçilmelidir. Amaç en iyi sayıyı bulmak
değil, transit şeklini yemeden korelasyonu açıklayan kararlı model bulmaktır.

### Adım 4: Gerçek veriden önce yapay veri kalibrasyonu yap

Yeni model doğrudan TOI-3492.01 üzerinde çalıştırılmamalıdır. Önce gerçek TESS
zaman damgaları ve veri boşlukları kullanılarak yapay ışık eğrileri üretilmelidir.

Yapay testler şunları içermelidir:

1. Yalnız beyaz gürültülü veri.
2. Bilinen OU benzeri korelasyonlu veri.
3. Bilinen Matérn benzeri korelasyonlu veri.
4. Sektörden sektöre değişen gürültü genliği.
5. Background veya pointing ile bağlantılı sistematik.
6. Bilinen derinlik ve süreye sahip enjekte transit.
7. Transit olmayan kontrol verisi.
8. Sınır yakını kernel parametreleri.

Sorulacak sorular:

1. Doğru transit derinliği geri bulunuyor mu?
2. Transit süresi bias almadan geri bulunuyor mu?
3. Model transit giriş/çıkışını gürültü diye yiyor mu?
4. Yüzde 68 ve yüzde 95 aralıklar gerçek değeri beklenen sıklıkta kapsıyor mu?
5. Beyaz veri gereksiz yere korelasyonlu ilan ediliyor mu?
6. Korelasyonlu veri beyaz diye yanlış sınıflandırılıyor mu?
7. Beta, ACF ve predictive eşikleri hangi gerçek davranışa karşılık geliyor?

Eşikler bu testlerle belirlenip hash'lendikten sonra gerçek veri çalıştırılmalıdır.

### Adım 5: Yeni gürültü modelini gerçek veride çalıştır

Gerçek veri çalışmasında şu yapı korunmalıdır:

1. Aynı 16 fiziksel transit olayı.
2. Aynı 24 Faz 5B dalı.
3. İki maskenin bağımsız veri gibi çarpılmaması.
4. Reduction dallarının bağımsız veri gibi çarpılmaması.
5. Doğal 120-s zaman damgaları.
6. Pozlama süresinin modelde integrasyonu.
7. Sektör bazlı nuisance parametreleri.
8. Model-ortalama veya eşdeğer açık marginalizasyon.

Geçme koşulları en az şunları kapsamalıdır:

1. Farklı başlangıçlar aynı çözüme geliyor.
2. Bağımsız optimizer benzer çözüm buluyor.
3. MCMC yakınsıyor.
4. Parametreler sınırlara anlamsız biçimde dayanmıyor.
5. Held-out sektör tahmini kararlı.
6. İki maskede sonuç aşırı değişmiyor.
7. Residual ACF kontrol altında.
8. Transit-relevant zaman ölçeklerinde beta kabul edilebilir.
9. Enjekte transitler bias olmadan geri bulunuyor.
10. Posterior predictive kontroller veriyi makul yeniden üretiyor.

### Adım 6: Faz 6 geçerse sonraki fiziksel zinciri çalıştır

Faz 6 gerçekten geçerse sıralama şu olmalıdır:

| Sıra | İş | Basit amacı |
|---:|---|---|
| 1 | Faz 7 | Yıldız aktivitesi, flare ve spot-crossing etkisini kontrol et |
| 2 | Faz 8 | Her olayın zamanı kayıyor mu, ephemeris doğru mu bak |
| 3 | Faz 9-10 | Sektör derinliği farkını hiyerarşik modelle ölç |
| 4 | Faz 11 | Yıldızın atmosfer, SED ve izokron posteriorunu tutarlı kur |
| 5 | Faz 12 | Metaliklik ve limb-darkening belirsizliğini taşı |
| 6 | Faz 13 | TESS PRF ile sinyalin olası gökyüzü kaynağını değerlendir |
| 7 | Faz 14 | Dilution ve alternatif host senaryolarını modele kat |
| 8 | Faz 15 | Bütün pipeline boyunca transit enjeksiyon/geri-kazanım yap |
| 9 | Faz 16 | Nihai 120-s dairesel doğal-kadans posterioru üret |
| 10 | Faz 17 | 20-s veriyi bağımsız kanıt değil, geometri kontrolü olarak kullan |
| 11 | Faz 18 | Yalnız yeterli kanıt varsa eksantrik modeli karşılaştır |
| 12 | Faz 19 | R-hat, ESS, MCSE ve bütün yakınsama kontrollerini yap |
| 13 | Faz 20 | Posterior predictive ve influence analizi yap |
| 14 | Faz 21 | Koşullu fiziksel yarıçap ve diğer nicelikleri çıkar |
| 15 | Faz 22-24 | Odd/even, secondary ve phase-curve kontrollerini güncelle |
| 16 | Faz 25 | Yalnız girdiler yeterliyse formal FPP hesapla |
| 17 | Faz 26 | Yıldız ve transit yoğunluğu karşılaştırmasını doğru covariance ile yap |
| 18 | Faz 27 | RV fizibilitesi ve gözlem planı yaz; veri yoksa mass ölçme |
| 19 | Faz 28 | Astrosismolojiyi çıkarılmış durumda tut veya ancak gerçek kapıyla geri al |
| 20 | Faz 29-30 | Makale, audit, PDF, test, manifest ve yayın paketini tamamla |

Faz 11 stellar posterioru ve bazı dokümantasyon işleri Faz 6 geliştirilirken
paralel yürüyebilir. Ancak Faz 6 geçmeden nihai transit geometrisi ve ona bağlı
yoğunluk/eksantriklik sonuçları benimsenmemelidir.

## 25. Ne yapmamalıyız?

### 25.1 Aynı K0 modelini farklı seedlerle tekrar tekrar çalıştırmamalıyız

K0 sayısal stationarity'yi geçti ama residual korelasyonu açıklamadı. Seed
değiştirmek model eksikliğini çözmez.

### 25.2 Beta sınırını 1.2936 sonucuna bakıp yükseltmemeliyiz

Eşik değişecekse gerçek sonuçtan bağımsız yapay-veri kalibrasyonuyla yeni
protokolde değişmelidir. "Sonuç 1.29 çıktı, sınırı 1.30 yapalım" bilimsel değildir.

### 25.3 İstediğimiz sonucu veren pencereyi seçmemeliyiz

`W16_P1` en iyi ham skora sahip diye otomatik final model olamaz. Önceden konan
tek-model seçme kuralını geçmedi.

### 25.4 İstediğimiz sonucu veren reduction'ı seçmemeliyiz

PDCSAP, SAP+CBV, TPF ve PLD aynı gözlemlerden geliyor. Birini sonuç lehine seçmek
ve diğerlerini yok saymak belirsizliği gizler.

### 25.5 20-s ve 120-s veriyi bağımsız iki kanıt gibi birleştirmemeliyiz

İkisi aynı TESS piksellerindeki aynı fiziksel olaydır. 20-s veri yalnız çözünürlük
ve tutarlılık kontrolüdür.

### 25.6 Faz 6 geçmeden Faz 7-16 sonuçlarını finalleştirmemeliyiz

Yanlış gürültü modeli aktivite, timing, sektör farkı ve transit geometrisini
yanlış yorumlatabilir.

### 25.7 Faz 6R'yi eksiksiz preregistered çalışma gibi sunmamalıyız

Hesap sonucu korunmalı, fakat eksik protocol/provenance açıkça yazılmalıdır.

### 25.8 Sektör derinliği farkını hemen astrofiziksel ilan etmemeliyiz

Fark gerçek olabilir, fakat kamera, aperture, background ve red-noise gibi
alternatifler henüz elenmedi.

### 25.9 Katlanmış/binlenmiş fit aralıklarını nihai posterior gibi vermemeliyiz

Bu fit sinyali göstermek için iyidir; bütün belirsizlikleri taşıyan final ölçüm
değildir.

### 25.10 Bilimsel değerler donmadan yayın paketi üretmemeliyiz

Eski hash, audit, PDF veya ZIP'in `PASS` olması güncel makalenin doğru olduğu
anlamına gelmez.

### 25.11 Başarısız sonuçları silmemeliyiz

V1, V2, Faz 6R ve başarısız kernel sonuçları provenance olarak kalmalıdır. Yeni
çalışma yeni dosya adları ve yeni schema kullanmalıdır.

### 25.12 Analizi mutlaka gezegen sonucu çıkarmaya zorlamamalıyız

Tam analiz sonunda nesne hâlâ doğrulanmamış aday kalabilir. Bilimsel hedef
`PASS` almak değil, verinin desteklediği doğru sonucu bulmaktır.

## 26. Dış gözlem olmadan bu makale bitebilir mi?

Evet, bir fotometrik karakterizasyon ve aday-değerlendirme makalesi olarak
bitebilir. TESS verisinden yapılabilecek bütün analiz bu makalede tamamlanabilir.

Fakat dış gözlem olmadan şu ifadeler kapalı kalır:

| İddia | Neden dış veri gerekebilir? |
|---|---|
| Kesin hedef yıldız üzerinde transit | TESS pikselleri yakın kaynakları tam ayıramayabilir |
| Yakın yıldız yok | Speckle/AO contrast curve gerekir |
| Nesne yıldız değil | Spektroskopi ve/veya kütle bilgisi gerekir |
| Kütle ölçüldü | Hedefe özgü radyal hız gerekir |
| Dinamik olarak teyit edildi | RV veya eşdeğer dinamik kanıt gerekir |

Bu sınırlar makalenin yarım kalması değildir. Makalenin sonucu açıkça şöyle
olabilir:

> Altı sektörde sağlam biçimde tekrar eden, ayrıntılı fotometrik kontrollerden
> geçirilmiş, fakat kaynağı ve gezegensel doğası kesinleştirilmemiş aday.

Bu aynı makalenin final sonucudur. Zorunlu olarak ikinci makale demek değildir.

## 27. Yeni Faz 6 da geçmezse ne olacak?

Bu sorunun cevabı gerçek veriye bakmadan yazılmalıdır.

1. Yeni model yapay-veri ve gerçek-veri kapılarını geçerse tam doğal-kadans zinciri
   devam eder.
2. Yeni model sentetik testte transit parametrelerini bias'lı geri getirirse gerçek
   veriye uygulanmaz.
3. Gerçek veride bütün makul modeller residual korelasyonu açıklayamazsa hassas
   geometri ve yoğunluk iddiası yapılmaz.
4. Bu durumda analiz yine tamamlanır; final sonuç verinin hassas geometriyi
   desteklemediği olur.

Buradaki önemli ayrım:

> Analizin bitmesi, modelin mutlaka kapıyı geçmesi değildir. Önceden tanımlı
> bütün makul yöntemlerin dürüst bir sonuca ulaşmasıdır.

## 28. Gerçekçi zaman tahmini

Önceki "2-3 gün" tahmini yalnız mevcut dar metni temizleyip paketlemek için bile
fazla iyimserdi ve kullanıcının tam analiz hedefine uygun değildi.

Tam fotometrik analiz için kabaca:

| İş | Tahmini aktif çalışma |
|---|---:|
| Durum belgelerini eşitleme ve Faz 6 post-mortem | 1-3 gün |
| Yeni protokol ve sentetik kalibrasyon tasarımı | 2-5 gün |
| Kodlama, sentetik test ve düzeltme | 3-10 gün |
| Gerçek veri fitleri ve hesap kontrolü | 2-7 gün |
| Faz 7-21 ana fiziksel zinciri | 1-3 hafta |
| False-positive kontrolleri, makale, audit ve paket | 4-10 gün |

Bu süreler garanti değildir. Hesap süresi, modelin ilk seferde geçmesi ve mevcut
scriptlerin ne kadarının yeniden kullanılabileceğine bağlıdır. Gerçekçi toplam,
odaklı çalışmada yaklaşık 3-6 hafta mertebesidir. Yeni gürültü modeli tekrar
başarısız olursa süre değil, iddia kapsamı değişir.

## 29. Bugünkü kesin karar önerisi

Şu karar uygulanmalıdır:

1. Yayın paketi şimdilik durdurulsun.
2. Faz 1, Faz 2, Faz 3 ve Faz 4 yeniden yapılmasın.
3. Faz 5 `FAIL` sonucu değiştirilmesin.
4. Faz 5B'nin 24 dallı modeli korunsun.
5. Mevcut Faz 6R sonucu `FAIL_RESIDUAL_CORRELATION` ve provenance eksikleriyle
   birlikte kaydedilsin.
6. Stage-2'nin eski Yol B stop kararını değiştiren tarihli kapsam değişikliği
   gerçek veri hesabından önce yazılsın.
7. Eski K0 modeli tekrar tekrar denenmesin.
8. Mevcut Faz 6 sonuçlarının nedenlerini kullanan yeni, sınırlı ve ön-kayıtlı
   korelasyonlu-gürültü yöntemi tasarlansın.
9. Önce sentetik kalibrasyon, sonra gerçek veri çalıştırılsın.
10. Yeni Faz 6 geçerse Faz 7'den itibaren tam fiziksel zincir tamamlansın.
11. Sonuç ne çıkarsa çıksın makale TESS fotometrisinin desteklediği son noktada
    bitirilsin; sonuç zorla gezegen veya zorla `PASS` yapılmasın.

## 30. En basit son özet

Ne bulduk?

> Altı TESS sektöründe tekrar eden gerçek bir transit-benzeri sinyal bulduk.

Sorun ne?

> Sinyalin hassas şekli ve büyüklüğü, veri işleme seçimlerine ve zaman bağlantılı
> gürültüye duyarlı.

Ne bozuldu?

> İlk beyaz-gürültü ortak modeli önce sayısal olarak çalışmadı; düzeltildiğinde de
> residual korelasyonu yeterince açıklamadı.

24 dal hata mıydı?

> Hayır. 24 dal, makul analiz seçimlerinin belirsizliğini saklamamak için korundu.

Baştan mı başlayacağız?

> Hayır. Faz 1-4 ve Faz 5B kullanılabilir.

Nereden devam edeceğiz?

> Faz 5B'den sonra gürültü modelini yeniden tasarlayarak.

Ne yapmayacağız?

> Tek pencere seçmeyeceğiz, beta sınırını sonuca göre değiştirmeyeceğiz, seed
> aramayacağız ve başarısız sonuçları silmeyeceğiz.

Makale bitecek mi?

> Evet. Bu makalede TESS fotometrisinin bütün güvenilir analizi tamamlanacak.
> Final sonuç doğrulanmış gezegen de olabilir demiyoruz; verinin desteklediği en
> güçlü ve dürüst aday sonucu neyse makale onunla bitecek.

## 31. 23 Temmuz 2026 Stage-3 uygulama durumu

Bu rapordaki tarihli kapsam değişikliği artık yazıldı ve kullanıcı tarafından
aşamalı hazırlık için onaylandı. S3-00 durum eşitlemesi, S3-01 değişmez girdi
manifesti ve S3-02 mevcut-artifact Faz 6 post-mortemi `PASS` verdi.

S3-02 yeni model çalıştırmadı. Mevcut sonuçlardan şu somut tabloyu çıkardı:

1. OU, Matérn-3/2 ve SHO sınır sorunlarının tamamı ortak korelasyon zaman
   ölçeğinin 360 dakikalık üst sınırına dayanmasıdır.
2. Maske etkileşiminde en belirgin held-sector fold'ları 64, 100 ve 37'dir.
3. Hangi tekil cadence'in predictive farkı doğurduğu mevcut artifactlerden
   söylenemez; noktasal katkılar saklanmamıştır ve maske model evrenleri farklıdır.
4. Faz 6R'nin maksimum beta sonucu değişmedi: 80 dakikada 1.293606. Bu fazlalığı
   o ölçekte en çok sektör 37 sürükler; daha uzun ölçeklerde sektör 100 ve 64 de
   belirginleşir.
5. Eski V1 residual dosyaları dolu olsa da geçersiz sayısal no-op ürünleridir;
   V2 residual dosyaları boştur.
6. Background ve pointing ilişkileri yalnız betimleyicidir; kesin neden
   atanmamıştır.

Sıradaki güvenli adım S3-04'tür: tek Matern-3/2 adayının sentetik kalibrasyon
protokolünü gerçek veri sonucu görülmeden dondurmak. S3-03'te tek aday, sektör
bazlı kısmi-timescale havuzlaması, 24 dal ve K0 referans kararı hashlenmiştir.
Gerçek-veri yetkisi ve Faz 7 kapalıdır.

## 32. Bu raporun dayandığı ana dosyalar

1. `currentproblem.md`
2. `currentproblemstage2.md`
3. `outputs/faz1_product_inventory.json`
4. `outputs/faz2_transit_inventory.json`
5. `outputs/faz3_quality_audit.json`
6. `outputs/faz4_reduction_comparison.json`
7. `outputs/faz5_window_polynomial_grid.json`
8. `outputs/faz5b_remediation.json`
9. `outputs/faz6_kernel_comparison.json`
10. `outputs/faz6_gate_audit.json`
11. `outputs/faz6r_result.json`
12. `outputs/wp09a_formal_sector_audit.json`
13. `outputs/release_status.json`
14. `outputs/stage3_phase6_postmortem.json`
15. `toi3492_characterization.tex`
