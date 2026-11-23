# Kiadások a GitHubon

Minden közzétett módosításnál legyen elérhető a GitHubon a legfrissebb változat, annak hordozható Windows ZIP-je és forrás-ZIP-je és a változásokat bemutató, képernyőképes kiadási jegyzet.

1. Válassz új verziót a módosításhoz, és egyeztesd a `pyproject.toml` és az alkalmazás verziójelzését.
2. Írd meg magyarul a változásokat a `docs/kiadasok/vX.Y.Z/README.md` fájlban. Készíts képernyőképeket a futó alkalmazásról fiktív adatokkal. A képeket ugyanebbe a könyvtárba mentsd, és relatív Markdown-képhivatkozással (`./név.png`) illeszd a jegyzetbe. Dokumentáld az eltérő tesztkörnyezetet, ahol az befolyásolja, mit mutat a kép.
3. Futtasd a teszteket, és ellenőrizd a kiadandó fájlokat. Hivatali dokumentum, valós számlaadat és helyi konfiguráció nem kerülhet a repóba, a képernyőképekre vagy a ZIP-be.
4. A GitHubra feltöltött commitot címkézd az első lépés szerinti verzióval (`vX.Y.Z`). A címke indítja a Windows buildet, majd közzéteszi mindkét ZIP-et és a jegyzetet. A munkafolyamat befejezése után ellenőrizd a Release-oldalt, mindkét ZIP letöltését és a jegyzet képeit. A korábbi kiadásokhoz új verziót adj ki.
5. A visszajelzésben add meg a GitHub-kiadás, a hordozható Windows ZIP, a forrás-ZIP és a képernyőképes jegyzet linkjét. A GitHub változatlan `releases/latest` hivatkozása a legutóbb közzétett kiadásra mutat.
