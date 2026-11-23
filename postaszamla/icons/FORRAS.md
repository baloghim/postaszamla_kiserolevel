# KDE Modern Classic ikonok

A mellékelt ikonok Shaun Belcher KDE Modern Classic témájából származnak. Az SVG-k, az eredeti generátorforrás és a közreműködők adatai a rögzített forrásverzióban érhetők el. [Forrás és SVG-generátor, 466f093](https://github.com/nzoomed/kde-modern-classic/tree/466f093bf391f80c67cef60a24d4013be2536707)

Az ikonok licence LGPL-3.0-or-later. A csomag tartalmazza a licencszövegeket, a szerzői adatokat, a KDE Classic eredeti licencét és a téma fejlesztőinek tájékoztatóját. A Postaszámla alkalmazás az ikonfájlokat külön erőforrásként tölti be.

| Alkalmazásbeli SVG | Eredeti ikon a téma `scalable/` mappájában |
| --- | --- |
| `new` | `actions/document-new-from-template.svg` |
| `edit` | `actions/edit-rename.svg` |
| `open` | `actions/document-open.svg` |
| `print` | `devices/document-print.svg` |
| `refresh` | `actions/view-refresh.svg` |
| `settings` | `actions/configure.svg` |
| `about` | `actions/help-about.svg` |
| `help` | `actions/help-browser.svg` |
| `docx` | `mimetypes/application-vnd.openxmlformats-officedocument.wordprocessingml.document.svg` |
| `pdf-missing`, `pdf-present` | `mimetypes/application-pdf.svg` |
| `previous`, `next` | `actions/go-previous.svg`, `actions/go-next.svg` |

A `pdf-present.svg` a téma piros PDF-ikonjának zöld átszínezése. A futtatáshoz a Tk alatt közvetlenül betölthető, több DPI-mérethez előállított PNG-ívek tartoznak. Az íveket név szerinti sorrendben az SVG-kből a `packaging/render_icons.py` állítja elő Inkscape és Pillow használatával. Ezek csak az ikonok újragenerálásához szükségesek.
