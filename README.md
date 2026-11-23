# Postaszámla-kísérőlevél v0.5.0

A PySide2 és Qt 5 alapú asztali alkalmazás éves dokumentumtárban böngészi és előnézetben megnyitja a kísérőleveleket. Egy levélhez több számla rögzíthető. A meglévő parancssori program továbbra is közvetlenül JSON-adatokból készít DOCX-et. A költségösszesítő normál Word-táblázat két fejlécsorral, négy szolgáltatási sorral és egy összesítő sorral. A generáláshoz elegendő a Python és a telepített csomagok.

## Letöltés és változások

- [A legfrissebb GitHub-kiadás](https://github.com/baloghim/postaszamla_kiserolevel/releases/latest)
- [A legfrissebb forráskód ZIP-ben](https://github.com/baloghim/postaszamla_kiserolevel/releases/latest/download/postaszamla-forras.zip)
- [Hordozható Windows x64 alkalmazás v0.5.0 (ZIP)](https://github.com/baloghim/postaszamla_kiserolevel/releases/download/v0.5.0/Postaszamla-v0.5.0-win64.zip)
- [A v0.5.0 változásai képernyőképekkel](docs/kiadasok/v0.5.0/README.md)

## Asztali alkalmazás

A hordozható ZIP teljes tartalmát csomagold ki egy írható mappába. A `Postaszamla\Postaszamla.exe` indításához a mellette található `_internal` mappa szükséges. A csomag saját Python-futtatókörnyezetet tartalmaz. A `beallitasok.json` az első indításkor jön létre az EXE mellett.

Forrásból a projektkönyvtárban, Windows parancssorban:

```bat
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install ".[desktop]"
.venv\Scripts\python.exe -m postaszamla.gui
```

1. A **Beállítások** ablakban válaszd ki az éves almappákat tartalmazó dokumentumtárat és a hivatali DOCX-sablont. Itt előre megadhatod az ügyintéző, az aláíró és a beosztás alapértékeit.
2. Az **Új kísérőlevél** ablakban add meg a közös adatokat, majd rögzíts minden számlát külön. A dátumok `ÉÉÉÉ.HH.NN.` vagy `ÉÉÉÉ-HH-NN` alakban adhatók meg. Az időszak, a szolgáltatásonkénti összegek és a fájlnév folyamatosan frissülnek.
3. A listában év és fájlnév szerint kereshetsz, az oszlopfejlécekkel pedig rendezhetsz. A PDF-jelzés az azonos alapnevű fájl jelenlétét mutatja. A kijelölt DOCX előnézete automatikusan betöltődik.
4. A program ellenőrzött adatfájllal rendelkező levelekhez kínál szerkesztést. A belépés és a mentés megerősítést igényel. A régi vagy Wordben utólag módosított DOCX-ek előnézetben és Wordben nyithatók meg.

### A főablak megjelenése

Az alapbeállításokkal a dokumentumlista és az előnézet egyenlő szélességet kap. Az elválasztó húzható, a felhasználó által beállított helyét az alkalmazás megjegyzi. A „Szélesség” nagyítás követi a panel méretét. A vízszintes görgetősáv akkor jelenik meg, ha a nagyított dokumentum szélesebb a panelnél.

A főablak, a levélszerkesztő és a beállítások ugyanazt az XP Luna Blue stílust használják. A kék, átmenetes panelcímek, a krémszínű eszköztár és a tagolt állapotsor az EDPD Menedzser 2.6.3 XP Luna Blue megjelenéséhez igazodnak. Az előnézet külön gombokat ad az első, előző, következő és utolsó oldalhoz, a nagyításhoz és a két illesztési módhoz. [Full HD főablak](docs/kiadasok/v0.5.0/foablak.png)

A beépített művelet- és dokumentumikonok az EDPD által is használt Crystal Remix készletből származnak. Az eredeti PNG-k, a felhasznált forrásverzió és a GNU LGPL licencanyagok a csomagba kerülnek. [Ikonforrások és licenc](postaszamla/icons/FORRAS.md)

### Hordozható beállítások

A forrásból a fenti paranccsal indítva a `beallitasok.json` a projekt gyökerébe kerül. A hordozható változat az EXE mellett tárolja. A relatív útvonalak alapja ugyanez a könyvtár. A `beallitasok.example.json` másolható kiindulópontként. Ha a tényleges konfiguráció hiányzik, a program alapbeállításokkal újra létrehozza. Sérült fájlról mentés készül, és az alkalmazás felajánlja a visszaállítást.

Az üres sablonmező a csomag fiktív mintasablonját választja. Az alapértelmezett dokumentumtár a programkönyvtárbeli `dokumentumok` mappa. Az oszlopszélességeket, ablaktulajdonságokat, panelméreteket és nagyítást a program bezáráskor menti. A következő indításkor mindig az aktuális év jelenik meg.

### Adatfájl és mentés

A DOCX melletti azonos alapnevű `*.postaszamla.json` UTF-8 JSON. A gyökérmezők `version` (jelenleg 1), `docx_sha256` és `letter`. A `letter` tartalmazza a `reference`, `clerk`, `signer`, `position`, `dated`, `sent` és `invoices` mezőt. A számlák tömbjének elemei `number`, `start`, `end` és `costs` mezőket tartalmaznak. A dátumok ISO-formátumúak, a költségmezők megegyeznek a parancssori minta mezőivel. A kezdő nullás számlaszámok szövegek. Az összesítés mindig újraszámítható a számlákból. A DOCX és az adatfájl csak együtt kezelhető szerkeszthető levélként.

Jóváhagyott szerkesztéskor a korábbi DOCX és adatfájl ellenőrzött másolatát a dokumentumtár `.postaszamla-backups` almappája őrzi. Ha megváltozik a fájlnév, a korábbi DOCX és adatfájl csak az új pár ellenőrzése után kerül ki az éves mappából. Másik levél fájljai és a meglévő PDF-ek érintetlenek maradnak. Futás közbeni írási hiba esetén a program visszagörgeti az addigi műveleteket. A folyamat kényszerített megszakításakor megmaradhat egy `.postaszamla-lock` mappa. Ilyenkor az alkalmazás új mentést nem kezd. A mentett párt és az esetleges biztonsági másolatot kézzel kell ellenőrizni, majd a zárolást csak akkor eltávolítani, ha biztosan nem fut mentés.

### Előnézet és nyomtatás

Windowson a háttérben futó Word COM-automatizálás csak olvasható ideiglenes DOCX-másolatból PDF-et készít. A többoldalas PDF-et a PDFium jeleníti meg. Az alapértelmezett nézet az oldalszélességhez igazodik. Az eredeti Word-fájl és az esetleges meglévő PDF változatlan marad. A Word-alapú előnézet hibája esetén, illetve Linuxon a program szöveges betekintést ad, ha a DOCX olvasható. A megnyitás és a nyomtatás a Windows DOCX-fájltársítását használja; a célgépen ezt állítsd Wordre.

A Qt-felületet Linuxon Full HD felbontásban, a PDF lapozását és nagyítását fiktív kétoldalas PDF-fel ellenőriztük. A Word 2016 COM-konverzió, az eltérő Windows DPI-beállítások és a nyomtatás célgépes próbát igényelnek.

## Parancssori telepítés és mintagenerálás

A tároló gyökerében, Windows parancssorban:

```bat
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\python.exe -m postaszamla examples\minta.json --output output
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

A minta eredménye az `output/2026/postaszámla_2026.10.24-10.31_ellátási_ki_be_szallitas.docx` fájl. A végösszeg 247 225 Ft. A `--output` a dokumentumtár gyökérmappáját adja meg. A program az elszámolási időszak kezdőévének almappájába ment, évhatáron átnyúló időszaknál is. Az almappa szükség esetén létrejön. A korábbi közvetlen mentéshez add meg a `--flat-output` kapcsolót. Ha a célfájl már létezik, a program hibaüzenettel leáll, és megőrzi a meglévő fájlt.

Linuxon a parancsokban a `py -3.10` helyett `python3`, a virtuális környezet Pythonjához pedig `.venv/bin/python` használható a támogatott Python-verziókkal.

## Saját adatok és sablon

Az `examples/minta.json` fiktív adatokkal mutatja be a formátumot. Saját használatra másold a mintát a Git-tárolón kívülre, majd töltsd ki az alábbi mezőket.

| Mező | Tartalom |
| --- | --- |
| `start`, `end` | Az időszak kezdő- és záródátuma ÉÉÉÉ-HH-NN alakban |
| `reference` | Iktatószám |
| `sent`, `dated` | A megküldés dátuma és a keltezés ÉÉÉÉ-HH-NN alakban |
| `invoices` | Egy vagy több számlaszám szöveges JSON-listája, a kívánt sorrendben. A kezdő nullák megmaradnak. |
| `clerk`, `signer`, `position` | Ügyintéző, aláíró és az aláíró beosztása. A hivatali sablonhoz kötelezők. |
| `attachments` | Elhagyható. A régi mintasablonnal felülbírálhatja a számlákból számított darabszámot. A hivatali sablon mindig a számlák darabszámát használja. |
| `costs` | A `postal`, `transport`, `forwarding` és `mailbox` sorok `operating` és `benefits` összege egész forintban |

Egyes tételeknél megengedett a nulla. A teljes táblázat nem lehet nulla, és negatív érték nem adható meg. A sorösszegeket és az oszlopösszegeket a motor számítja ki. Ha az időszak átnyúlik az évhatáron, mindkét év megjelenik a fájlnévben. Az oszlopösszegek alapján az ellátási és a működési jelölés, a szolgáltatási sorok alapján pedig a ki-, beszállítás, a belföldi utánküldés és a fiókbérlet jelölése kerülhet a fájlnévbe, ebben a sorrendben.

Az alapértelmezett [mintasablon](postaszamla/templates/minta.docx) a csomag része. Saját DOCX megadásához használd a `--template` kapcsolót.

```bat
.venv\Scripts\python.exe -m postaszamla "D:\Hivatali\adatok.local.json" --output "D:\Hivatali\Levelek" --template "D:\Hivatali\sablon.docx"
```

A számlaszámok például `["00001", "00002", "00003"]` alakban adhatók meg. A hivatali levélben ez „00001, 00002 és 00003” formában jelenik meg, és a „számla” szó a darabszámhoz igazodik. A megküldés dátuma például „2026. november 4-én”, a keltezés pedig „2026. november 23.” alakú.

### Hivatali DOCX helyőrzői

| Helyőrző | Beillesztett érték |
| --- | --- |
| `{{iktatoszam}}` | Iktatószám |
| `{{ugyintezo}}` | Ügyintéző neve |
| `{{darabszam}}` | Számlaszámok darabszáma |
| `{{erkezett_datum}}` | A megküldés magyarul toldalékolt dátuma |
| `{{postaszamla_szamok}}` | Számlaszámok felsorolása megadási sorrendben |
| `{{tobbes}}` | `a` vagy `ák` a `száml{{tobbes}}` kifejezésben |
| `{{dátum}}` | A levél keltezése |
| `{{alairo}}` | Aláíró neve |
| `{{beosztas}}` | Aláíró beosztása |

A költségtáblázat két fejlécsora után a B, C és D oszlopba rendre `{{mukodesi1}}`, `{{ellatas1}}` és `{{osszesen1}}` kerül. Az öt szolgáltatási és összesítő sorban a sorszám 1-től 5-ig fut. Az A oszlop sorcímei maradjanak a mintával egyezőek, opcionális sorszámozással. A hivatali sablon második fejlécsorában a D oszlop képlete Wordben javítható `D. (B.+C.)` alakra. A Python a D oszlopban minden esetben összead.

Az eredeti, nagybetűs mezőket használó fiktív mintasablon továbbra is működik. Ebben a `{{REFERENCE}}`, `{{PERIOD}}`, `{{SENT}}`, `{{INVOICES}}`, `{{ATTACHMENTS}}` és `{{DATED}}` mezők, valamint a táblázatban a `{{B1}}`, `{{C1}}`, `{{D1}}` és a további számozott mezők szerepelnek.

Egy sablonon belül minden kötelező helyőrző pontosan egyszer szerepeljen. A külalakot és a változatlan szövegeket Wordben szerkesztheted. A motor az eredeti sablonból külön DOCX-fájlt hoz létre.

## Windows 10 1607 és Office 2016

A Windows x64 csomag CPython 3.10.11, PySide2 és shiboken2 5.15.2.1 (Qt 5.15.2), valamint PyInstaller 6.11.1 használatával készül. A Word-előnézethez `pywin32 311`, a PDF megjelenítéséhez `pypdfium2 5.15.2` tartozik. A parancssori dokumentumgenerálás Python 3.10–3.12 alatt használható. A Qt-felület forrásból történő futtatásához Python 3.10 x64 szükséges.

A `vX.Y.Z` címke a Windows Server 2022 GitHub-runneren futtatja a teszteket és a PyInstaller buildet. A munkafolyamat a közzététel előtt elindítja a kicsomagolt EXE-t, ellenőrzi a beállításfájlt és mindkét Qt-ablakot, majd fiktív dokumentummal próbálja ki a DOCX-mentést és a PDF-megjelenítést. A Windows 10 1607 és a Word 2016 együttes működéséhez célgépes próba szükséges. [CPython 3.10.11](https://www.python.org/downloads/release/python-31011/) · [PyInstaller 6.11.1 követelményei](https://github.com/pyinstaller/pyinstaller/blob/v6.11.1/README.rst)

A hordozható csomag dinamikusan betöltött Qt 5 könyvtárakat és licencanyagokat tartalmaz. A grafikai stílus Luna-alapú, a Postaszámlához igazított téma. A saját, helyi EDPD 2.6.3 munkapéldányból az eredeti stílus, az arányos táblázat és a referenciaikonkészlet betölthető a `--edpd-source` kapcsolóval, például `python -m postaszamla.gui --edpd-source C:\forras\beerkezett_posta_kezeles`. [Qt 5.15.2 forrás](https://download.qt.io/archive/qt/5.15/5.15.2/single/) · [Qt for Python forráskiadások](https://download.qt.io/official_releases/QtForPython/pyside2/)

A korábbi Tkinter-változat forrása a [legacy/tkinter](https://github.com/baloghim/postaszamla_kiserolevel/tree/legacy/tkinter) ágon érhető el.

A csomag fiktív mintasablont tartalmaz. A saját hivatali sablont a Beállításokban választhatod ki. Az egylapos tördelés és a nyomtatási kép ellenőrzéséhez nyisd meg a helyben generált DOCX-et Word 2016-ban.

## Adatvédelem

A tároló nyilvános. A `beallitasok.json`, a számlaadatfájlok és a mentési másolatok helyben maradnak, és a Git kizárja őket. Az eredeti hivatali sablonokat, valós számlaszámokat, bemeneti adatfájlokat és elkészült leveleket a Git-tárolón kívül tartsd. A Git alapértelmezett kizárásai lefedik az `output/` mappát, a `*.local.json` adatfájlokat és az érdemi Office- és PDF-kimeneteket. A Gitbe csak szándékosan kiválasztott, fiktív mintaadatok és a nyilvános mintasablon kerüljenek.
