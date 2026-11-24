# Az EDPD-grafika forrása

A beépített felületek és ikonkészletek az EDPD Menedzser v2.6.3 `543845a5e60eacc43253ea8e28fdd33e611ea4a6` commitjából származnak. A Postaszámla a saját `postaszamla.qt.edpd_graphics` névterében használja a palettákat, a QSS-szabályokat, a stílusváltót és a manifestalapú ikonbetöltőt. Az ikontémák 22 és 40 pixeles PNG-jei, a Crystal SVG futásidejű méretei és az eredeti állományok a kiadásban is megtalálhatók. [EDPD v2.6.3](https://github.com/baloghim/beerkezett_posta_kezeles/tree/v2.6.3)

## Postaszámla-szerepek

| Művelet | EDPD-szerep vagy Qt-helyettesítés |
| --- | --- |
| Új kísérőlevél és számla hozzáadása | `mail` |
| Szerkesztés | Qt `SP_FileDialogContentsView` |
| Megnyitás Wordben és Tallózás | Qt `SP_DialogOpenButton` |
| Nyomtatás | `print` |
| Frissítés és Alaphelyzet | `refresh` |
| Beállítások | `settings` |
| Névjegy | `about` |
| Súgó | Qt `SP_DialogHelpButton` |
| DOCX-dokumentum | Qt `SP_FileIcon` |
| PDF elérhető | `pdf` |
| PDF hiányzik és megerősítés jelzése | `warning` |
| Számla eltávolítása | `delete` |
| Mentés | `save` |
| Mégse és Nem | Qt `SP_DialogCancelButton` |
| Igen és OK | Qt `SP_DialogYesButton` |
| Első, előző, következő és utolsó oldal | `first`, `previous`, `next`, `last` |
| Nagyítás és kicsinyítés | `zoom_in`, `zoom_out` |
| Szélesség és Teljes oldal | `width`, `page` |

A feloldás először a kiválasztott témában keresi a szerepet, majd a Crystal SVG megfelelőjét és végül a Qt gyári ikonját használja. A Nuvola, az Oxylite és az SE98 a szélességhez a Crystal SVG ikonját használja. Az eredeti EDPD manifestben a `mail` szerepet a Crystal SVG készlet adja mind a tizenkét témában. A Modern Office Day a szélességhez, a teljes oldalhoz, a nagyításhoz és a kicsinyítéshez használ Crystal SVG ikont. A Qt-ikonok azokhoz a dokumentum- és párbeszédablak-műveletekhez tartoznak, amelyekhez az EDPD manifestje nem ad szerepet. [EDPD ikontéma-audit](https://github.com/baloghim/beerkezett_posta_kezeles/blob/v2.6.3/docs/ICON-THEME-AUDIT-2.6.2.md)

## Eredet és licencek

A `themes.json` szerepenként rögzíti az eredeti fájlokat, a forrásverziót, a licencet, valamint az ellenőrzött SHA-256 értékeket. A Crystal Remix külön `manifest.json` fájlt és GNU LGPL forrásnyilatkozatot kapott. Az egyes témák szerzői listái és licencfájljai az `assets/notices` alatt találhatók. A forrásállományok és a licencek a hordozható EXE ZIP-jében is szerepelnek. [EDPD licenc- és forrásösszesítő](https://github.com/baloghim/beerkezett_posta_kezeles/blob/v2.6.3/docs/ICON-THEMES.md)

| Ikontéma | Forrás szerinti licenc |
| --- | --- |
| Crystal SVG | GNU LGPL, a Crystal Remix forrása verziószám nélkül jelöli |
| Nuvola | LGPL-2.1-or-later |
| KDE Modern Classic | LGPL-3.0-or-later és a történeti KDE-elemek külön feltételei |
| Papirus | GPL-3.0 |
| We10X | GPL-3.0, megőrzött Yaru-kredittel |
| Oxygen | LGPL-3.0-or-later |
| Win10Sur | GPL-3.0, megőrzött OSX_ONE-kredittel |
| Oxylite | A tároló GPL-3.0 nyilatkozata mellett a kiválasztott fájlok külön LGPL-feltételei irányadók |
| WhiteSur | GPL-3.0 |
| Diagonal | CC-BY-4.0 az ikonokra, az egyedi megjelölésekkel |
| Modern Office Day | GPL-3.0, a Breeze-források megőrzött LGPL-3.0-or-later jelölésével |
| SE98 | A forrástároló GPL-2.0 nyilatkozata. Az EDPD auditja az egyedi Microsoft-eredetű fájlok továbbterjesztési jogát nem minősítette igazoltnak. |

A grafikai modulok eredeti EDPD licenctájékoztatója az `assets/notices/EDPD-LICENSE.txt` fájlban, az SE98 részletes eredetleírása pedig az `assets/notices/se98` alatt található. [EDPD licenctájékoztató](https://github.com/baloghim/beerkezett_posta_kezeles/blob/v2.6.3/LICENSE)
