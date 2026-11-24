# A Postaszámla Qt 5 ikonleltára

A kiinduló `main` a `68ee071` commiton állt, és a régi Crystal sprite-okat használta, opcionális külső EDPD-ikonbetöltéssel. A `migration/qt5-production` fejlesztési ág a `1416f98` commiton állt, és az EDPD 2.6.3 tizenkét beépített témáját használta. Az audit és a javítás ezen az ágon készült. Az értesítési megoldás az EDPD `IconThemeManager` szerepalapú feloldását és témajelzését követi. [EDPD 2.6.3 ikonkezelő](https://github.com/baloghim/beerkezett_posta_kezeles/blob/v2.6.3/src/edpd/ui/icons.py)

Az előző kiadásban több ikon feloldása Crystal- vagy Qt-helyettesítésnél állt meg. A már megnyitott vezérlők feliratkozása gyenge Python-hivatkozást használt, ezért a Qt tulajdonában lévő gomb vagy akció Python-oldali objektuma idő előtt eltűnhetett. Az új kötés a Qt-objektum megszűnéséig tartja életben a feliratkozást. A témajelzés előtt kiürül a témagyorsítótár. A jel az aktuális ablakokban frissíti az ikonokat, a dokumentumkijelölés és a PDF-előnézet megtartásával.

## Műveletenkénti leltár

A „forrás” oszlop a v0.7.0 feloldását mutatja. A „váltás” oszlop azt jelzi, hogy az ikon követhette-e a kijelölt témát az előző kiadásban. A tételes v0.7.1 forrás, a feloldási sorrend eredménye és a csomagolt elérési út mind a 34 szerephez és 12 témához megtalálható a [gépi jelentésben](icon-sources.json).

| Hely és művelet | Logikai szerep | v0.7.0 forrás | Korábbi témaváltás | v0.7.1 javítás |
| --- | --- | --- | --- | --- |
| Fő eszköztár · Új kísérőlevél | `new` | Crystal `mail` | Mindig Crystal | Mind a 12 témában saját `document-new` |
| Fő eszköztár · Szerkesztés | `edit` | Qt fájltartalom-ikon | Qt-stílust követett | Saját ikon, Nuvolánál Crystal-helyettesítés |
| Fő eszköztár · Megnyitás Wordben | `open` | Qt megnyitás | Qt-stílust követett | Mind a 12 témában saját megnyitás- vagy mappaikon |
| Fő eszköztár · Nyomtatás | `print` | EDPD nyomtató | Témaspecifikus | Tartós akciókötés |
| Fő eszköztár · Frissítés | `refresh` | EDPD frissítés | Témaspecifikus | Tartós akciókötés |
| Fő eszköztár · Beállítások | `settings` | EDPD beállítások | Témaspecifikus | Tartós akciókötés |
| Fő eszköztár · Névjegy | `about` | EDPD információ | Témaspecifikus | Tartós akciókötés |
| Fő eszköztár · Súgó | `help` | Qt súgó | Qt-stílust követett | Mind a 12 témában saját súgóikon |
| Dokumentumlista · DOCX | `docx` | Qt fájlikon | Qt-stílust követett | Saját Word- vagy irodai dokumentumikon |
| Dokumentumlista · PDF van | `pdf-present` | EDPD PDF | Témaspecifikus, eltérő színek | Témaspecifikus ikon és zöld „Van” |
| Dokumentumlista · PDF nincs | `pdf-missing` | EDPD figyelmeztetés | Témaspecifikus, gyakran sárga | Témaspecifikus ikon és piros „Nincs” |
| Dokumentumlista · Keresés törlése | `clear-input` | Qt belső mezőikon | Qt-stílust követett | Központi kötés a meglévő törlési akción |
| PDF-betekintő · Első oldal | `first` | EDPD első oldal | Témaspecifikus | Tartós akciókötés |
| PDF-betekintő · Előző oldal | `previous` | EDPD előző oldal | Témaspecifikus | Tartós akciókötés |
| PDF-betekintő · Következő oldal | `next` | EDPD következő oldal | Témaspecifikus | Tartós akciókötés |
| PDF-betekintő · Utolsó oldal | `last` | EDPD utolsó oldal | Témaspecifikus | Tartós akciókötés |
| PDF-betekintő · Kicsinyítés | `zoom-out` | EDPD kicsinyítés | Témaspecifikus vagy Crystal | Tartós kötés, dokumentált helyettesítés |
| PDF-betekintő · Nagyítás | `zoom-in` | EDPD nagyítás | Témaspecifikus vagy Crystal | Tartós kötés, dokumentált helyettesítés |
| PDF-betekintő · Szélesség | `fit-width` | EDPD szélesség | Témaspecifikus vagy Crystal | Tartós kötés, dokumentált helyettesítés |
| PDF-betekintő · Teljes oldal | `fit-page` | EDPD teljes oldal | Témaspecifikus vagy Crystal | Tartós kötés, dokumentált helyettesítés |
| Új kísérőlevél és Szerkesztés · Számla hozzáadása | `invoice-add` | Crystal `mail` | Mindig Crystal | Saját hozzáadásikon |
| Új kísérőlevél és Szerkesztés · Számla eltávolítása | `invoice-delete` | EDPD törlés | Témaspecifikus | Tartós gombkötés |
| Új kísérőlevél, Szerkesztés és Beállítások · Mentés | `save` | EDPD mentés | Témaspecifikus | Tartós gombkötés |
| Új kísérőlevél, Szerkesztés és Beállítások · Mégse | `cancel` | Qt megszakítás | Qt-stílust követett | Saját megszakításikon |
| Beállítások · Dokumentumtár és sablon tallózása | `open` | Qt megnyitás | Qt-stílust követett | Saját megnyitásikon, mindkét gomb tartósan kötve |
| Beállítások · Alaphelyzet | `refresh` | EDPD frissítés | Témaspecifikus | Tartós gombkötés |
| Névjegy · Jelzés | `about` | EDPD információ | Témaspecifikus | A már megnyitott párbeszéd is frissül |
| Súgó · Jelzés | `help` | EDPD információ | Témaspecifikus információjel | Saját súgóikon |
| Mentés, törlés, szerkesztés, visszaállítás és nyomtatás megerősítése · Jelzés | `question` | EDPD figyelmeztetés | Témaspecifikus figyelmeztetés | Saját kérdésjel, ahol van, egyébként Qt kérdésjel |
| Hibaüzenet · Jelzés | `warning` | EDPD figyelmeztetés | Témaspecifikus | A megnyitott ablak is frissül |
| Párbeszédablak · Igen és OK | `confirm` | Qt igen | Qt-stílust követett | Saját jóváhagyásikon |
| Párbeszédablak · Nem és Mégse | `cancel` | Qt megszakítás | Qt-stílust követett | Saját megszakításikon |
| Szerkeszthető mezők helyi menüje · Visszavonás és újra | `undo`, `redo` | Operációs rendszer Qt-ikonkészlete | A Postaszámla témájától független | A meglévő Qt-akciók szerepkötése |
| Mezők és szöveges betekintő helyi menüje · Kivágás, Másolás, Beillesztés | `cut`, `copy`, `paste` | Operációs rendszer Qt-ikonkészlete | A Postaszámla témájától független | A meglévő Qt-akciók szerepkötése |
| Mezők helyi menüje · Törlés | `delete` | Operációs rendszer Qt-ikonkészlete | A Postaszámla témájától független | Központi EDPD törlésikon |
| Mezők és szöveges betekintő helyi menüje · Összes kijelölése | `select-all` | Operációs rendszer Qt-ikonkészlete | A Postaszámla témájától független | Saját ikon, ahol szerepel a témában, egyébként szöveges menüpont |
| Alkalmazás, főablak és párbeszédablakok címsora | `application` | Vegyes Qt és témakötött ablakikonok | Egyes ablakok eltértek | Egyetlen rögzített alkalmazásikon, az EXE ikonja is ezt használja |
| Naptár, lenyíló listák, táblázatrendezés, rendszerfájl-választó | Natív Qt és rendszervezérlők | Qt és operációs rendszer | Natív | A natív vezérlőjelzéseket a felületi stílus kezeli |
| Indulási hiba az ikonkezelő betöltése előtt | Natív hibajel | Qt hiba | Natív | A hibaüzenet önállóan megjelenhet |

## Ellenőrzött helyettesítések

A központi sorrend a választott téma, Crystal SVG, megfelelő gyári Qt-ikon, végül szöveges akció. A kiegészítő ikonok az EDPD témái által megjelölt, rögzített upstream commitokból származnak. Az SVG-fájlokból azonos rajzolatú PNG készült. Az eredeti út, licenc, SHA-256 és a futásidejű fájl a [kiegészítő manifestben](../postaszamla/qt/edpd_graphics/assets/role-icons.json) ellenőrizhető. Egyes upstream készletek azonos grafikát használnak, ilyen szerepnél a forrás megváltozhat azonos látható pixelek mellett. [EDPD licencrészletek](edpd-grafika.md)

| Téma | Saját szerep a 34-ből | Más forrás |
| --- | ---: | --- |
| Crystal SVG | 32 | Qt kérdésjel, Összes kijelölése szöveggel |
| Nuvola | 29 | Crystal Szerkesztés, Szélesség és mezőtörlés, Qt kérdésjel, Összes kijelölése szöveggel |
| KDE Modern Classic | 34 | — |
| Papirus | 34 | — |
| We10X | 34 | — |
| Oxygen | 33 | Qt kérdésjel |
| Win10Sur | 34 | — |
| Oxylite | 33 | Crystal Szélesség |
| WhiteSur | 34 | — |
| Diagonal | 34 | — |
| Modern Office Day | 30 | Crystal Nagyítás, Kicsinyítés, Szélesség és Teljes oldal |
| SE98 | 33 | Crystal Szélesség |

A jelentést a `python packaging/icon_report.py` állítja elő. A `--check` kapcsoló ellenőrzi a közzétett jelentést a ténylegesen csomagolt szerepfeloldással szemben. A tesztek ellenőrzik az eredeti és futásidejű fájlok hashét, a már létrehozott gombok, menük, dokumentumsorok és párbeszédablakok Qt-képét, valamint a témajelzéseket.

## Az alkalmazásikon forrása

A kért Ravenna 3D Mail ikon szerzőjeként az IconArchive címe Double-J Designt jelöli. Az oldal és a kép-CDN ebben a környezetben 403-as választ adott, így az eredeti grafika és a pontos terjesztési feltételek átvétele függőben van. [A kiválasztott Ravenna Mail ikon](https://www.iconarchive.com/show/ravenna-3d-icons-by-double-j-design/Mail-icon.html)

A v0.7.1-ben a rögzített alkalmazásikon a Postaszámla meglévő Crystal Remix DOCX-grafikájának ICO-változata. Az eredeti grafika Everaldo Coelho Crystal Project készletéből és Viet Dang Crystal Remix átdolgozásából származik. A forrás GNU LGPL nyilatkozatot közöl verziószám nélkül. [Átadott forrásmegjelölés és licencszövegek](../postaszamla/icons/FORRAS.md)
