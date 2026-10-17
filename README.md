# 🌟 Desktop GIF Sticker (Floating Widget)

Aplikasi dekorasi desktop ringan untuk menempelkan animasi GIF transparan melayang di layar Windows.

---

## 📦 Pilihan Distribusi & Menjalankan

### Opsi 1: Setup Installer Wizard (Paling Praktis untuk Pengguna Awam)
Jalankan file installer di folder `dist/`:
```
dist/DesktopSticker_Setup_v1.0.exe
```
* **Fitur Installer**:
  * Wizard instalasi standar Windows (*Next > Install > Finish*).
  * Tidak butuh password Administrator Windows (1-click install).
  * Opsi otomatis membuat icon shortcut di Desktop.
  * Opsi otomatis berjalan saat Windows dinyalakan (*Startup*).
  * Dilengkapi **Uninstaller resmi** di Windows Settings (*Apps & Features*).

---

### Opsi 2: Standalone Portable (.exe Tanpa Perlu Install)
Jika kamu hanya ingin langsung menjalankan tanpa install ke sistem:
```
dist/DesktopSticker.exe
```
* Cukup double-click langsung jalan.
* Portabel: Bisa dimasukkan ke flashdisk dan dipindah ke komputer lain tanpa perlu install Python.

---

### Opsi 3: Menjalankan dari Source Code (Developer)
```powershell
py main.py
```
atau double-click file `run.bat`.

---

## ✨ Fitur Utama Aplikasi

* **Auto-Transparent Background (Fitur Cerdas)**:
  * Otomatis mendeteksi dan menghapus background putih solid, hitam, atau green-screen dari file GIF internet.
  * Menjaga bagian putih di dalam karakter (seperti bola mata atau gigi) agar tidak ikut berlubang.
* **Bebas Geser (Drag & Move)**: Klik kiri dan tahan stiker untuk menggesernya ke mana saja di layar.
* **Ubah Ukuran Halus (Scroll Zoom)**: Putar roda mouse ke atas (memperbesar) atau ke bawah (mengecilkan).
* **Ganti Animasi (Drag & Drop)**: Seret file `.gif` langsung dari File Explorer dan lepas di atas stiker.
* **Multi-Sticker**: Bisa memunculkan banyak stiker sekaligus di layar.
* **Menu Opsi Modern (Klik Kanan)**:
  * 👾 **Karakter Bawaan**: Pilihan instan animasi bawaan (*Herta Kurukuru*, *Tenor*, *Pikachu*, *Pikachu White BG*, *Eevee*, *Gengar*, *Gengar Green BG*).
  * 📁 **Buka File GIF Lain**: Pilih file animasi apa saja dari komputermu.
  * ✨ **Tambah Stiker Baru**: Buka beberapa karakter sekaligus di layar.
  * 🎨 **Hapus Background**: Mode Otomatis, Putih, Hitam, Green Screen, atau Nonaktif + Pengatur Toleransi.
  * ⚡ **Kecepatan & FPS Animasi**: Pilihan preset FPS (10, 15, 24, 30, 60 FPS), Kustom FPS bebas (1-120 FPS), atau Pengali Kecepatan (0.25x - 3.0x).
  * 🌓 **Transparansi Layar**: Atur opacity jendela (100%, 85%, 70%, 50%, 30%).
  * 🔒 **Kunci Posisi**: Kunci posisi stiker agar tidak sengaja tergeser saat bekerja/gaming.
  * 📌 **Selalu di Depan (Overlay Layar & Fullscreen)**: Mengunci stiker agar terus melayang di puncak tampilan layar, termasuk di atas video player, browser fullscreen (F11), atau game mode borderless windowed tanpa mencuri fokus.
  * 🔄 **Reset Ukuran**: Kembalikan ke ukuran standar.
  * ❌ **Tutup Stiker Ini**: Menutup stiker yang aktif.
  * 🚪 **Tutup Semua & Keluar**: Keluar dari aplikasi sepenuhnya.
