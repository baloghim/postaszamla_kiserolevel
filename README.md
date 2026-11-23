# Postaszámla-kísérőlevél v0.1.0

A parancssori program JSON-adatokból szerkeszthető DOCX-kísérőlevelet készít. A költségösszesítő normál Word-táblázat két fejlécsorral, négy szolgáltatási sorral és egy összesítő sorral. A generáláshoz elegendő a Python és a telepített csomagok.

## Telepítés és mintagenerálás

A tároló gyökerében, Windows parancssorban:

```bat
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\python.exe -m postaszamla examples\minta.json --output output
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

A minta eredménye az `output/postaszámla_2026.10.24-10.31_ellátási_ki_be_szallitas.docx` fájl. A végösszeg 247 225 Ft. A megadott mentési mappa szükség esetén létrejön. Ha a célfájl már létezik, a program hibaüzenettel leáll, és megőrzi a meglévő fájlt.

Linuxon a parancsokban a `py -3.11` helyett `python3`, a virtuális környezet Pythonjához pedig `.venv/bin/python` használható a támogatott Python-verziókkal.

## Saját adatok és sablon

Az `examples/minta.json` fiktív adatokkal mutatja be a formátumot. Saját használatra másold a mintát a Git-tárolón kívülre, majd töltsd ki az alábbi mezőket.

| Mező | Tartalom |
| --- | --- |
| `start`, `end` | Az időszak kezdő- és záródátuma ÉÉÉÉ-HH-NN alakban |
| `reference` | Iktatószám |
| `sent`, `dated` | A megküldés dátuma és a keltezés ÉÉÉÉ-HH-NN alakban |
| `invoices` | Egy vagy több számlaszám szöveges JSON-listája |
| `attachments` | A mellékletek darabszáma |
| `costs` | A `postal`, `transport`, `forwarding` és `mailbox` sorok `operating` és `benefits` összege egész forintban |

Egyes tételeknél megengedett a nulla. A teljes táblázat nem lehet nulla, és negatív érték nem adható meg. A sorösszegeket és az oszlopösszegeket a motor számítja ki. Ha az időszak átnyúlik az évhatáron, mindkét év megjelenik a fájlnévben. Az oszlopösszegek alapján az ellátási és a működési jelölés, a szolgáltatási sorok alapján pedig a ki-, beszállítás, a belföldi utánküldés és a fiókbérlet jelölése kerülhet a fájlnévbe, ebben a sorrendben.

Az alapértelmezett [mintasablon](postaszamla/templates/minta.docx) a csomag része. Saját DOCX megadásához használd a `--template` kapcsolót.

```bat
.venv\Scripts\python.exe -m postaszamla "D:\Hivatali\adatok.local.json" --output "D:\Hivatali\Levelek" --template "D:\Hivatali\sablon.docx"
```

A sablont Wordben módosíthatod. A fejlécet, címzettet, megszólítást, aláírást és a változatlan ügyviteli adatokat a sablonban állítsd be. A `{{REFERENCE}}`, `{{PERIOD}}`, `{{SENT}}`, `{{INVOICES}}`, `{{ATTACHMENTS}}` és `{{DATED}}` helyőrzők mindegyike pontosan egyszer szerepeljen közvetlen bekezdésszövegben. A költségtáblázat első két sora fejléc. Az utána következő öt sor első oszlopának felirata maradjon a mintával azonos, a másik három oszlopba rendre `{{B1}}`, `{{C1}}`, `{{D1}}` kerül, és így tovább az ötödik sorig. A formázást a sablon adja, a motor külön fájlba ment.

## Windows 10 1607 és Office 2016

A célgéphez a 64 bites CPython 3.11 a kiindulási verzió. A CPython 3.11 Windows-dokumentációja Windows 8.1-től jelöl támogatást. A rögzített `python-docx 1.2.0` és `typing-extensions 4.15.0` platformfüggetlen csomagja, valamint az `lxml 6.1.0` CPython 3.11-es, 64 bites Windows-csomagja letölthető. A telepítést és a dokumentumgenerálást Linuxon, Python 3.12 alatt ellenőriztük. [CPython Windows-dokumentáció](https://github.com/python/cpython/blob/3.11/Doc/using/windows.rst)

A későbbi EXE-csomagolás vizsgálatához a PyInstaller 6.11.1 dokumentált követelményei lefedik a Python 3.11-et és a Windows 8 vagy újabb rendszereket. A konkrét Windows 10 1607-es gépen külön ellenőrizendő a Python, a natív lxml és a későbbi EXE futása. [PyInstaller 6.11.1 követelményei](https://github.com/pyinstaller/pyinstaller/blob/v6.11.1/README.rst)

A mintasablon A4-es és fiktív arculatú. Az eredeti hivatalos megjelenést, az egylapos tördelést és a nyomtatási képet a végleges, helyi sablonnal Word 2016-ban kell ellenőrizni.

## Adatvédelem

A tároló nyilvános. Az eredeti hivatali sablonokat, valós számlaszámokat, bemeneti adatfájlokat és elkészült leveleket a Git-tárolón kívül tartsd. A Git alapértelmezett kizárásai lefedik az `output/` mappát, a `*.local.json` adatfájlokat és az érdemi Office- és PDF-kimeneteket. A Gitbe csak szándékosan kiválasztott, fiktív mintaadatok és a nyilvános mintasablon kerüljenek.
