# 🌟 Desktop GIF Sticker (Floating Widget)

Aplikasi dekorasi desktop ringan untuk menempelkan animasi GIF transparan melayang di layar Windows.

---

## 📦 Pilihan Distribusi & Menjalankan

### Opsi 1: Setup Installer Wizard (Paling Praktis untuk Pengguna Awam)
Jalankan file installer di folder `dist/`:
```
dist/DesktopSticker_Setup_v1.1.exe
```
* **Fitur Installer**:
  * Wizard instalasi standar Windows (*Next > Install > Finish*).
  * Tidak butuh password Administrator Windows (1-click install).
  * Opsi otomatis membuat icon shortcut di Desktop.
  * Opsi otomatis berjalan saat Windows dinyalakan (*Startup*).
  * Dilengkapi **Uninstaller resmi** di Windows Settings (*Apps & Features*).
  * Start paling cepat (~1 detik) karena aplikasi terpasang sebagai folder.

---

### Opsi 2: Standalone Portable (.exe Tanpa Perlu Install)
Jika kamu hanya ingin langsung menjalankan tanpa install ke sistem:
```
dist/DesktopSticker_Portable.exe
```
* Cukup double-click langsung jalan.
* Portabel: Bisa dimasukkan ke flashdisk dan dipindah ke komputer lain tanpa perlu install Python.
* Start sedikit lebih lambat (~2-3 detik) karena isinya diekstrak dulu ke folder Temp setiap kali dibuka.

---

### Build Sendiri (Installer + Portable)
Butuh [Inno Setup 6](https://jrsoftware.org/isdl.php) dan PyInstaller:
```powershell
py -m pip install -r requirements.txt pyinstaller
```
Lalu double-click `build.bat`. Hasilnya ada di folder `dist/`. Nomor versi diatur di baris `set "VERSION=..."` dalam `build.bat`.

---

### Opsi 3: Menjalankan dari Source Code (Developer)
Install dependency dulu (cukup sekali):
```powershell
py -m pip install -r requirements.txt
```
Lalu jalankan:
```powershell
py main.py
```
atau double-click file `run.bat`. Kalau library belum terinstall, `run.bat` akan menawarkan untuk menginstallnya otomatis.

> `numpy` sifatnya opsional, tapi membuat proses hapus background jauh lebih cepat untuk GIF besar.

---

## ✨ Fitur Utama Aplikasi

* **Auto-Transparent Background (Fitur Cerdas)**:
  * Otomatis mendeteksi dan menghapus background putih solid, hitam, atau green-screen dari file GIF internet.
  * Menjaga bagian putih di dalam karakter (seperti bola mata atau gigi) agar tidak ikut berlubang.
  * Mode Otomatis hanya menghapus warna yang sama di beberapa pojok, jadi rambut/badan karakter yang menyentuh pojok tidak ikut terhapus, dan GIF dengan background pemandangan dibiarkan utuh.
* **Bebas Geser (Drag & Move)**: Klik kiri dan tahan stiker untuk menggesernya ke mana saja di layar.
* **Ubah Ukuran Halus (Scroll Zoom)**: Putar roda mouse ke atas (memperbesar) atau ke bawah (mengecilkan).
* **Ganti Animasi (Drag & Drop)**: Seret file `.gif` langsung dari File Explorer dan lepas di atas stiker.
* **Multi-Sticker**: Bisa memunculkan banyak stiker sekaligus di layar.
* **Ingat Posisi & Setelan Otomatis**: Semua stiker (posisi, ukuran, GIF, mode background, FPS/kecepatan, transparansi, kunci posisi, selalu di depan) tersimpan otomatis dan muncul lagi persis sama saat aplikasi dibuka kembali, termasuk saat jalan otomatis di Startup Windows.
  * Disimpan di `%APPDATA%\DesktopSticker\stickers.json`. Hapus file ini untuk kembali ke tampilan awal.
  * Kalau monitor dicabut, stiker yang tadinya ada di monitor itu otomatis dipindah ke layar yang masih ada.
* **Menu Opsi Modern (Klik Kanan)**:
  * 👾 **Karakter Bawaan**: Pilihan instan animasi bawaan (*Herta Kurukuru*, *Stelle*, *Evernight Kacamata*, *Evernight Dance*, *Cyrene*, *Paimin*, *Tenor*, *Pikachu*, *Pikachu White BG*, *Eevee*, *Gengar*, *Gengar Green BG*).
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
