# Crystal Remix ikonok

Az EDPD Menedzser 2.6.3 Crystal SVG nevű beállítása a KDE 3 Crystal Project és Crystal Clear grafikáit egyesítő Crystal Remix készletre épül. A Postaszámla ugyanabból a rögzített upstream változatból használ ikonokat. [EDPD 2.6.3 ikonforrások](https://github.com/baloghim/beerkezett_posta_kezeles/blob/v2.6.3/docs/ICONS.md) · [Crystal Remix forrás, f8863b5](https://github.com/dangvd/crystal-remix-icon-theme/tree/f8863b558b8eedf22caea0eabe18030bfcbe0783)

Az eredeti ikonokat Everaldo Coelho, a Crystal Remix átdolgozását Viet Dang (Đặng Việt Dũng) készítette. Az upstream GNU LGPL licencet jelöl meg verziószám nélkül. A forrás közleményét, az LGPL 2.1 és LGPL 3.0 szövegét, valamint az utóbbihoz tartozó GPL 3.0 szöveget mellékeljük. A képek eredeti PNG-raszterek.

| Csomagolt eredeti | Útvonal a Crystal Remix készletben |
| --- | --- |
| `about` | `128x128/status/dialog-information.png` |
| `add` | `32x32/actions/list-add.png` |
| `docx` | `128x128/mimetypes/application-vnd.openxmlformats-officedocument.wordprocessingml.document.png` |
| `edit` | `32x32/actions/document-edit.png` |
| `first` | `128x128/actions/go-first.png` |
| `fit-page` | `32x32/actions/zoom-fit-best.png` |
| `help` | `128x128/apps/help-browser.png` |
| `last` | `128x128/actions/go-last.png` |
| `new` | `32x32/actions/document-new.png` |
| `next` | `128x128/actions/go-next.png` |
| `open` | `32x32/actions/document-open.png` |
| `pdf` | `128x128/mimetypes/application-pdf.png` |
| `previous` | `128x128/actions/go-previous.png` |
| `print` | `32x32/actions/document-print.png` |
| `refresh` | `128x128/apps/system-software-update.png` |
| `settings` | `128x128/actions/system-run.png` |
| `zoom-in` | `32x32/actions/zoom-in.png` |
| `zoom-out` | `32x32/actions/zoom-out.png` |

A Postaszámla zöld pluszt ad az új dokumentum ikonjához, két színnel jelöli a PDF állapotát, és oldalirányú nyilakkal egészíti ki a szélességre igazítás ikonját. A módosítások forrása a `packaging/render_icons.py` program. A futtatáshoz a Tk által betölthető PNG-ívek tartoznak. A Pillow csak az újrageneráláshoz kell.
