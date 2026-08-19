STAGE18G FBSTART DEADMAN - DERLEME PAKETI
========================================

ONEMLI:
Bu ZIP dogrudan boot edilecek bir EFI degildir. NootedGreen ve HookCase
kextlerini macOS Intel runner uzerinde derleten GitHub Actions workflow'udur.

NE YAPACAKSIN:
1. ZIP icindeki su dosyayi NootedGreen fork'una koy:
   .github/workflows/build-tgl-stage18g-fbstart-deadman.yml
2. GitHub > Actions bolumunde
   "Build NootedGreen REAL TGL Stage18G FBStart deadman diagnostic"
   workflow'unu ac.
3. Run workflow dugmesine bas.
4. Islem yesil tamamlaninca su artifact'i indir:
   NootedGreen-REAL-TGL-STAGE18G-FBSTART-DEADMAN
5. Indirdigin ZIP'i ACIP DEGISTIRMEDEN bu sohbete yukle.

YAPMA:
- Dahili guvenli EFI'yi degistirme.
- /Library/Extensions icine yeni kext kurma veya mevcut kextleri degistirme.
- Bu paketteki kaynak onizlemesini derlenmis EFI sanip USB'ye kopyalama.
- SMBIOS, NVRAM veya boot-args degistirme.

ARTIFACT'I YUKLEDIKTEN SONRA:
Stage18F LOADLOCK USB-only EFI tabanini kullanarak NootedGreen.kext ve
HookCase.kext'i yerlestirecegim, config snapshot/hash kontrollerini yapacagim
ve boot edilebilir Stage18G USB-only EFI ZIP'ini teslim edecegim.

STAGE18G'NIN TEK AMACI:
AppleIntel{Base,Framebuffer}Controller::start() 30 saniyede donmezse bilincli
kernel panic olusturmak ve panic mesajina son gorulen asamayi yazmak.

Asama kodlari:
100 = FB_START_ENTER
199 = FB_START_RETURN
210 = PW_INIT_ENTER
211 = PW_INIT_RETURN
220 = PGE_ENTER
221 = PGE_RETURN
230 = AUX_ENTER
231 = AUX_RETURN
240 = DDI_ENTER
241 = DDI_RETURN

Stage18F grafik davranisi aynen korunur. Stage18C genis framebuffer route'lari
kapali kalir. Yeni wrapper MMIO yazmaz, donus degerini degistirmez ve orijinal
start() fonksiyonunu aynen cagirir.
