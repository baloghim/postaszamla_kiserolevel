# Postaszámla-kísérőlevél v0.2.0

A parancssori program JSON-adatokból szerkeszthető DOCX-kísérőlevelet készít. A költségösszesítő normál Word-táblázat két fejlécsorral, négy szolgáltatási sorral és egy összesítő sorral. A generáláshoz elegendő a Python és a telepített csomagok.

## Telepítés és mintagenerálás

A tároló gyökerében, Windows parancssorban:

```bat
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\python.exe -m postaszamla examples\minta.json --output output
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

A minta eredménye az `output/2026/postaszámla_2026.10.24-10.31_ellátási_ki_be_szallitas.docx` fájl. A végösszeg 247 225 Ft. A `--output` a dokumentumtár gyökérmappáját adja meg. A program az elszámolási időszak kezdőévének almappájába ment, évhatáron átnyúló időszaknál is. Az almappa szükség esetén létrejön. A korábbi közvetlen mentéshez add meg a `--flat-output` kapcsolót. Ha a célfájl már létezik, a program hibaüzenettel leáll, és megőrzi a meglévő fájlt.

Linuxon a parancsokban a `py -3.11` helyett `python3`, a virtuális környezet Pythonjához pedig `.venv/bin/python` használható a támogatott Python-verziókkal.

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

A célgéphez a 64 bites CPython 3.11 a kiindulási verzió. A CPython 3.11 Windows-dokumentációja Windows 8.1-től jelöl támogatást. A rögzített `python-docx 1.2.0` és `typing-extensions 4.15.0` platformfüggetlen csomagja, valamint az `lxml 6.1.0` CPython 3.11-es, 64 bites Windows-csomagja letölthető. A telepítést és a dokumentumgenerálást Linuxon, Python 3.12 alatt ellenőriztük. [CPython Windows-dokumentáció](https://github.com/python/cpython/blob/3.11/Doc/using/windows.rst)

A későbbi EXE-csomagolás vizsgálatához a PyInstaller 6.11.1 dokumentált követelményei lefedik a Python 3.11-et és a Windows 8 vagy újabb rendszereket. A konkrét Windows 10 1607-es gépen külön ellenőrizendő a Python, a natív lxml és a későbbi EXE futása. [PyInstaller 6.11.1 követelményei](https://github.com/pyinstaller/pyinstaller/blob/v6.11.1/README.rst)

A mellékelt hivatali sablont fiktív bemenettel szerkezetileg ellenőriztük. Az egylapos tördelés és a nyomtatási kép ellenőrzéséhez nyisd meg a helyben generált DOCX-et Word 2016-ban.

## Adatvédelem

A tároló nyilvános. Az eredeti hivatali sablonokat, valós számlaszámokat, bemeneti adatfájlokat és elkészült leveleket a Git-tárolón kívül tartsd. A Git alapértelmezett kizárásai lefedik az `output/` mappát, a `*.local.json` adatfájlokat és az érdemi Office- és PDF-kimeneteket. A Gitbe csak szándékosan kiválasztott, fiktív mintaadatok és a nyilvános mintasablon kerüljenek.
