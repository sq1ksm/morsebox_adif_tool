# MorseBOX ADIF Tool

**MorseBOX ADIF Tool** to aplikacja okienkowa do przeglądania, edycji i eksportowania logów QSO generowanych przez program MorseBOX (lub kompatybilne rejestratory). Aplikacja może pobierać pliki logów bezpośrednio z serwera (np. ESP32) lub wczytywać lokalne pliki `.txt`/`.log`, parsować je, wyświetlać łączności w tabeli, a na koniec eksportować do standardowego formatu ADIF.

## Funkcje

-  **Pobieranie z serwera** – wpisz adres serwera (np. `http://192.168.1.12`), pobierz listę dostępnych plików i wybierz ten, który chcesz załadować – ładuje się automatycznie.
-  **Wczytywanie lokalnego pliku** – wybierz plik logu z dysku; jego treść zostanie sparsowana i wyświetlona.
-  **Edycja w tabeli** – kliknij dwukrotnie w komórkę, by edytować jej wartość. Pola daty i czasu są automatycznie formatowane, raporty RST są normalizowane (`5NN` → `599`), a niepoprawne godziny są usuwane.
-  **Zaznaczanie wierszy** – kliknij symbol `☐` w ostatniej kolumnie, by zaznaczyć wiersze do usunięcia. Zaznaczone wiersze zmieniają kolor na czerwony.
-  **Dodawanie pustego wiersza** – wstawia nowy, pusty wiersz na dole tabeli.
-  **Usuwanie zaznaczonych** – usuwa wszystkie wiersze oznaczone symbolem ☑.
-  **Domyślnee pasmo** – ustaw jedno pasmo dla wszystkich QSO za jednym razem.
-  **Eksport ADIF** – zapisuje zawartość tabeli jako standardowy plik `.adi`, gotowy do zaimportowania do dowolnego programu logującego.
-  **Wbudowana pomoc** – szybkie podsumowanie funkcji wewnątrz aplikacji.
-  **Wieloplatformowość** – działa na Windows, macOS i Linux (wymaga Pythona podczas kompilacji).

## Wymagania przy kompilacji

- **Python 3.6+**
- Dodatkowy pakiet Pythona: `requests`

Zainstaluj zależność:

```bash
pip install requests
```

## Build

Aby zbudować wersję:

## Windows
```bash
pyinstaller --onefile --windowed --name MorseBOX_ADIF_Tool.py
```

## macOS
```bash
pyinstaller --onefile --windowed --name MorseBOX_ADIF_Tool.py
```

