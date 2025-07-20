# -*- coding: utf-8 -*-
"""
Archive Discovery & Extractor
Profesyonel Archive.org içerik keşif ve çekme uygulaması
"""

# Windows encoding sorunlarını çöz
import sys
import os

import sys
import os
import locale

# Encoding ayarları
if sys.platform.startswith('win'):
    # Windows için encoding ayarları
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONLEGACYWINDOWSSTDIO'] = 'utf-8'
    try:
        locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254')
    except:
        try:
            locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_ALL, 'C.UTF-8')
            except:
                pass

import requests
import re
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QGroupBox, QMessageBox, 
    QListWidget, QListWidgetItem, QDialog, QGridLayout, QComboBox,
    QTextEdit, QScrollArea, QFrame, QProgressBar, QCheckBox, QDateEdit,
    QAbstractItemView, QFileDialog, QSpinBox, QInputDialog, QSizePolicy,
    QProgressDialog, QAbstractButton
)
from PySide6.QtCore import QThread, Signal, QTimer, Qt, QDate, QPropertyAnimation, QRectF, QSize, QObject, Slot
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QLinearGradient, QPainter
import xml.etree.ElementTree as ET
from xml.dom import minidom
from bs4 import BeautifulSoup
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
import time
from water_progressbar import WaterProgressBar
from os.path import basename
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from element_selector import SelectorDialog as FixedSelectorDialog

class QSwitch(QAbstractButton):
    def __init__(self, parent=None, label=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._label = label
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        # Daha geniş alan için genişliği artır
        self.setFixedWidth(70 if not label else 200)

    def sizeHint(self):
        return QSize(70 if not self._label else 200, 32)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track_rect = QRectF(10, 8, 44, 16)
        thumb_rect = QRectF(10 + (24 if self.isChecked() else 0), 6, 20, 20)
        
        # Pasif durum kontrolü
        is_enabled = self.isEnabled()
        
        # Track
        p.setPen(Qt.NoPen)
        if not is_enabled:
            # Pasif durum - soluk gri
            p.setBrush(QColor("#666666"))
        else:
            p.setBrush(QColor("#4ecdc4") if self.isChecked() else QColor("#b0b0b0"))
        p.drawRoundedRect(track_rect, 8, 8)
        
        # Thumb
        if not is_enabled:
            # Pasif durum - soluk beyaz
            p.setBrush(QColor("#cccccc"))
        else:
            p.setBrush(QColor("#ffffff"))
        p.drawEllipse(thumb_rect)
        
        # Label
        if self._label:
            if not is_enabled:
                # Pasif durum - soluk gri
                p.setPen(QColor("#888888"))
            else:
                p.setPen(QColor("white"))
            p.setFont(QFont("Arial", 11, QFont.Bold))
            p.drawText(60, 22, self._label)
        p.end()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.setChecked(not self.isChecked())
            self.clicked.emit()
        # super() çağrısını kaldır - bu hataya neden oluyor
        # super().mouseReleaseEvent(event)

    def setChecked(self, checked):
        super().setChecked(checked)
        self.update()

    def isChecked(self):
        return super().isChecked()

    def setLabel(self, label):
        self._label = label
        self.update()

    def label(self):
        return self._label

class ArchiveDiscovery(QThread):
    """Archive.org'dan domain keşfi yapan thread"""
    progress = Signal(str)
    discovery_complete = Signal(object)
    error = Signal(str)
    
    def __init__(self, domain, start_date=None, end_date=None, timeout_settings=None):
        super().__init__()
        self.domain = domain
        self.start_date = start_date
        self.end_date = end_date
        self.timeout_settings = timeout_settings or {'api_timeout': 60, 'retry_count': 3}
    
    def get_all_snapshots(self):
        """Tüm domain için tek seferde tüm snapshot'ları çeker"""
        try:
            self.progress.emit("Archive.org API'sine bağlanılıyor...")
            cdx_url = f"https://web.archive.org/cdx/search/cdx"
            params = {
                'url': self.domain + '/*',
                'output': 'json',
                'fl': 'timestamp,original',
                'limit': 100000
            }
            
            # Timeout ayarlarını kullan
            api_timeout = self.timeout_settings.get('api_timeout', 60)
            retry_count = self.timeout_settings.get('retry_count', 3)
            
            # Daha kısa timeout ve retry mekanizması
            for attempt in range(retry_count):
                try:
                    self.progress.emit(f"Snapshot'lar alınıyor... (Deneme {attempt + 1}/{retry_count})")
                    response = requests.get(cdx_url, params=params, timeout=api_timeout)
                    if response.status_code == 200:
                        break
                    elif response.status_code == 429:  # Rate limit
                        self.progress.emit("Rate limit! 30 saniye bekleniyor...")
                        time.sleep(30)
                    else:
                        self.progress.emit(f"HTTP Hatası: {response.status_code}")
                except requests.exceptions.Timeout:
                    self.progress.emit(f"Timeout! Deneme {attempt + 1}/{retry_count} başarısız")
                    if attempt == retry_count - 1:
                        raise Exception(f"Archive.org yanıt vermiyor (timeout: {api_timeout}s)")
                except requests.exceptions.ConnectionError:
                    self.progress.emit(f"Bağlantı hatası! Deneme {attempt + 1}/{retry_count}")
                    if attempt == retry_count - 1:
                        raise Exception("İnternet bağlantısı hatası")
            
            if response.status_code != 200:
                return []
                
            self.progress.emit("Veriler işleniyor...")
            data = response.json()
            if len(data) <= 1:
                return []
                
            snapshots = []
            total_rows = len(data) - 1
            for i, row in enumerate(data[1:], 1):
                if i % 1000 == 0:  # Her 1000 satırda bir ilerleme
                    self.progress.emit(f"Snapshot'lar işleniyor... {i}/{total_rows}")
                    
                if len(row) >= 2:
                    timestamp = row[0]
                    original_url = row[1]
                    archive_url = f"https://web.archive.org/web/{timestamp}/{original_url}"
                    snapshots.append({
                        'url': original_url,
                        'archive_url': archive_url,
                        'timestamp': timestamp,
                        'original_url': original_url  # Port dahil orijinal URL'yi sakla
                    })
            
            self.progress.emit(f"Toplam {len(snapshots)} snapshot alındı!")
            self.last_total_snapshots = len(snapshots)
            return snapshots
        except Exception as e:
            print(f"Snapshot alma hatası: {e}")
            return []

    def get_min_max_dates(self, snapshots):
        """Snapshot listesinden min ve max yıl-ay döndürür"""
        if not snapshots:
            return None, None
        timestamps = [s['timestamp'] for s in snapshots if len(s['timestamp']) >= 6]
        if not timestamps:
            return None, None
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        min_date = f"{min_ts[:4]}-{min_ts[4:6]}"
        max_date = f"{max_ts[:4]}-{max_ts[4:6]}"
        return min_date, max_date

    def run(self):
        try:
            self.progress.emit("Archive.org'dan domain bilgileri alınıyor...")
            all_snapshots = self.get_all_snapshots()
            if not all_snapshots:
                self.error.emit("Bu domain için hiç arşiv bulunamadı!")
                return
            min_date, max_date = self.get_min_max_dates(all_snapshots)
            self.available_dates = [min_date, max_date]
            self.progress.emit(f"Arşiv aralığı: {min_date} - {max_date}")
            # Tarih aralığı seçildiyse filtrele
            if self.start_date and self.end_date:
                filtered = []
                for snap in all_snapshots:
                    snap_date = datetime.strptime(snap['timestamp'][:6], "%Y%m")
                    # datetime.date ile datetime.datetime karşılaştırması için date() kullan
                    snap_date_only = snap_date.date()
                    if self.start_date <= snap_date_only <= self.end_date:
                        filtered.append(snap)
                used_snapshots = filtered
            else:
                used_snapshots = all_snapshots
            self.progress.emit(f"Toplam {len(used_snapshots)} snapshot bulundu, kategorize ediliyor...")
            categories = self.categorize_and_group_urls(used_snapshots)
            
            # Otomatik tespit artık URL listesinde buton ile yapılıyor
            
            self.progress.emit(f"Keşif tamamlandı! {len(used_snapshots)} snapshot bulundu")
            # --- YENİ: Toplam çekilen snapshot sayısını da gönder ---
            self.discovery_complete.emit((categories, len(all_snapshots), len(used_snapshots)))
            # --- SON YENİ ---
        except Exception as e:
            self.error.emit(f"Keşif hatası: {str(e)}")
    
    def normalize_url(self, url):
        """URL'yi normalize eder"""
        # Port numarasını kaldır - liste için normalize et
        parsed = urlparse(url)
        if parsed.port:
            netloc = parsed.netloc.split(':')[0]
            url = url.replace(f":{parsed.port}", "")
        return url
    
    def categorize_and_group_urls(self, snapshots):
        """URL'leri kategorilere ayırır ve aynı URL'nin tüm snapshot'larını gruplayarak döner (O(n) optimizasyonlu)"""
        categories = {
            'blog_posts': {},  # url: [snapshot, snapshot, ...]
            'pages': {},
            'images': {},
            'documents': {},
            'other': {}
        }
        # 1. Tüm snapshot'ları smart_url_key ile grupla
        url_to_snapshots = {}
        for snap in snapshots:
            url = self.normalize_url(snap['url'])
            if self.is_junk_url(url) or self.is_extra_junk(url):
                continue
            key = self.smart_url_key(url)
            url_to_snapshots.setdefault(key, []).append(snap)
        total = sum(len(snaps) for snaps in url_to_snapshots.values())
        processed = 0
        # 2. Her grup için kategorize et
        for key, snaps in url_to_snapshots.items():
            for snap in snaps:
                url = self.normalize_url(snap['url'])
                url_info = {
                    'url': key,
                    'archive_url': snap['archive_url'],
                    'timestamp': snap['timestamp'],
                    'all_snapshots': [s['timestamp'] for s in snaps],
                    'original_url': snap.get('original_url', snap['url'])  # Port dahil orijinal URL
                }
                if self.is_image(url):
                    categories['images'].setdefault(key, []).append(url_info)
                elif self.is_document(url):
                    categories['documents'].setdefault(key, []).append(url_info)
                elif self.is_blog_post(url):
                    categories['blog_posts'].setdefault(key, []).append(url_info)
                elif self.is_page(url):
                    categories['pages'].setdefault(key, []).append(url_info)
                else:
                    categories['other'].setdefault(key, []).append(url_info)
                processed += 1
                if processed % 1000 == 0 or processed == total:
                    msg = f"Kategorize ediliyor... {processed}/{total}"
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
                    if hasattr(self, 'progress'):
                        self.progress.emit(msg)
                    time.sleep(0.001)
        # Blog postları en güncel snapshot'a göre sırala ve grupla
        for key, snaps in categories['blog_posts'].items():
            snaps_sorted = sorted(snaps, key=lambda s: s['timestamp'], reverse=True)
            categories['blog_posts'][key] = snaps_sorted
        print('KATEGORİ DAĞILIMI:')
        for k, v in categories.items():
            print(f"  {k}: {len(v)}")
        return categories
    
    def is_junk_url(self, url):
        """İstenmeyen/sistem URL'lerini filtreler"""
        junk_patterns = [
            r'wp-login\.php', r'wp-admin', r'/feed/', r'/comments/feed/', 
            r'/sitemap\.xml', r'/robots\.txt', r'\.json$', r'\.xml$', r'\.css$', r'\.js$',
            r'\?replytocom', r'\.gz$', r'\.zip$', r'\.rar$', r'\.tar\.gz$'
        ]
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in junk_patterns)
    
    def is_blog_post(self, url):
        """Blog yazısı olup olmadığını kontrol eder (daha gevşek mantık)"""
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        # .html, .php, .asp, .aspx, .htm ile bitenler
        if re.search(r'\.(html|php|asp|aspx|htm)$', path):
            return True
        # /YYYY/MM/DD/ veya /YYYY/MM/ ile başlayanlar ve sonrasında bir şey olanlar
        if re.match(r'^/\d{4}/\d{2}/\d{2}/.+', path) or re.match(r'^/\d{4}/\d{2}/.+', path):
            return True
        # /blog/, /post/, /yazi/, /makale/, /haber/, /entry/, /story/ içerenler
        if any(x in path for x in ['/blog/', '/post/', '/yazi/', '/makale/', '/haber/', '/entry/', '/story/']):
            return True
        # Son segmenti sayı olmayanlar (ve path uzunluğu > 1)
        segments = [s for s in path.split('/') if s]
        if segments and not re.match(r'^\d+$', segments[-1]) and len(segments) > 1:
            return True
        return False
    
    def is_image(self, url):
        """Görsel olup olmadığını kontrol eder"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico']
        return any(url.lower().endswith(ext) for ext in image_extensions)
    
    def is_document(self, url):
        """Doküman olup olmadığını kontrol eder"""
        doc_extensions = ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.xls', '.xlsx', '.ppt', '.pptx']
        return any(url.lower().endswith(ext) for ext in doc_extensions)
    
    def is_page(self, url):
        """Sayfa olup olmadığını kontrol eder (Tarih bazlı arşivler dahil)"""
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        page_patterns = [
            r'/page/', r'/sayfa/', r'/index', r'/home',
            r'^/$', r'^/index\.html$', r'^/index\.php$',
            r'/kategori/', r'/category/', r'/etiket/', r'/tag/',
            r'/author/', r'/yazar/', r'/arsiv/', r'/archive/',
            r'/search/', r'\?s=', r'^/\d{4}/\d{2}(/\d{2})?/?$'
        ]
        return any(re.search(pattern, path) for pattern in page_patterns)
    
    def is_extra_junk(self, url):
        import re
        extra_junk_patterns = [
            r'wp-json', r'wp-includes', r'wp-content', r'contact-form-7', r'oembed',
            r'\.js$', r'\.css$', r'\.jpg$', r'\.jpeg$', r'\.png$', r'\.gif$', r'\.svg$', r'\.ico$', r'\.xml$', r'\.json$', r'\.woff$', r'\.ttf$', r'\.pdf$', r'\.zip$', r'\.gz$', r'\.tar$', r'\.mp4$', r'\.mp3$', r'\.webp$', r'\.avi$', r'\.mov$', r'\.wmv$', r'\.flv$', r'\.mkv$', r'\.apk$', r'\.exe$', r'\.bin$', r'\.dmg$', r'\.msi$', r'\.tar\.gz$', r'\.rar$'
        ]
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in extra_junk_patterns)
    
    # Otomatik tespit artık URL listesinde buton ile yapılıyor

    def smart_url_key(self, url):
        from urllib.parse import urlparse
        import re
        parsed = urlparse(url)
        path = parsed.path
        # Varyasyonları (feed, amp, embed, print, trackback) ana yazıya bağla
        for suffix in ['/feed', '/amp', '/embed', '/print', '/trackback']:
            if path.endswith(suffix):
                path = path[:-len(suffix)]
        # Sonunda / varsa kaldır (kök dizin hariç)
        if path.endswith('/') and path != '/':
            path = path[:-1]
        # index.html, index.php, index.htm kaldır
        for idx in ['index.html', 'index.php', 'index.htm']:
            if path.endswith('/'+idx):
                path = path[:-(len(idx)+1)]
        # .html, .htm kaldır
        for ext in ['.html', '.htm']:
            if path.endswith(ext):
                path = path[:-len(ext)]
        # www kaldır
        netloc = parsed.netloc.replace('www.', '')
        return f"{netloc}{path}".lower()

class ContentExtractor(QThread):
    """Seçilen içerikleri çeken thread"""
    progress = Signal(str)
    content_extracted = Signal(dict)
    extraction_complete = Signal(list)
    error = Signal(str)
    
    def __init__(self, selected_urls, timeout_settings=None, mainwindow=None):
        super().__init__()
        self.selected_urls = selected_urls
        self.extracted_content = []
        self.timeout_settings = timeout_settings or {'content_timeout': 20, 'retry_count': 2}
        self.mainwindow = mainwindow
        self.stop_requested = False
    
    def run(self):
        try:
            total = len(self.selected_urls)
            self.progress.emit(f"Toplam 0/{total} içerik çekilecek...")
            delay = self.timeout_settings.get('request_delay', 3)
            for i, url_info in enumerate(self.selected_urls, 1):
                self.progress.emit(f"Çekiliyor ({i}/{total}): {url_info['url']}")
                try:
                    content = self.extract_single_content(url_info)
                    if content:
                        self.extracted_content.append(content)
                        self.content_extracted.emit(content)
                        self.progress.emit(f"✅ Başarılı: {url_info['url']}")
                    else:
                        self.progress.emit(f"❌ Başarısız: {url_info['url']}")
                except Exception as e:
                    self.progress.emit(f"❌ Hata: {url_info['url']} - {e}")
                    continue
                time.sleep(delay)
            self.progress.emit(f"Çekme tamamlandı! {len(self.extracted_content)} içerik başarıyla çekildi!")
            self.extraction_complete.emit(self.extracted_content)
        except Exception as e:
            self.error.emit(f"Çekme hatası: {str(e)}")
    
    def extract_single_content(self, url_info):
        """Tek bir URL'den içerik çıkarır"""
        try:
            retry_count = self.timeout_settings.get('retry_count', 3)
            content_timeout = self.timeout_settings.get('content_timeout', 30)
            archive_dates = url_info.get('all_snapshots', [url_info['timestamp']])
            archive_dates = sorted(archive_dates, reverse=True)
            last_error = None
            self.progress.emit(f"🔍 {url_info['url']} için {len(archive_dates)} snapshot deneniyor")

            for date_index, archive_date in enumerate(archive_dates):
                self.progress.emit(f"🕒 Yeni snapshot deneniyor: {archive_date}")
                for attempt in range(retry_count):
                    if getattr(self, 'stop_requested', False):
                        return None
                    self.progress.emit(f"🔄 Deneme {attempt+1}/{retry_count} - Tarih: {archive_date}")
                    try:
                        # Her snapshot için doğru archive URL'sini oluştur
                        original_url = url_info.get('original_url', url_info['url'])
                        archive_url = f"https://web.archive.org/web/{archive_date}/{original_url}"
                        print(f"[DEBUG] Archive URL: {archive_url}")
                        print(f"[DEBUG] Original URL: {original_url}")
                        print(f"[DEBUG] Normalized URL: {url_info['url']}")
                        print(f"[DEBUG] Using snapshot date: {archive_date}")
                        
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        }
                        
                        if attempt > 0 or date_index > 0:
                            time.sleep(self.timeout_settings.get('request_delay', 3))
                        
                        response = requests.get(archive_url, headers=headers, timeout=content_timeout)
                        
                        print(f"[DEBUG] Response status: {response.status_code}")
                        print(f"[DEBUG] Content length: {len(response.content)} bytes")
                        
                        if getattr(self, 'stop_requested', False):
                            return None
                        
                        if response.status_code == 429:
                            self.progress.emit(f"⚠️ Rate limit! 30 saniye bekleniyor...")
                            time.sleep(30)
                            continue
                        
                        if response.status_code == 200:
                            # Encoding'i otomatik tespit et
                            if response.encoding == 'ISO-8859-1':
                                response.encoding = 'utf-8'
                            
                            content_length = len(response.content)
                            if content_length < 1000:
                                last_error = f"İçerik çok küçük ({content_length} bytes)"
                                continue
                            
                            # BeautifulSoup ile parse et - encoding'i düzelt
                            if response.encoding == 'ISO-8859-1':
                                response.encoding = 'utf-8'
                            
                            # HTML'i string olarak al ve parse et
                            html_content = response.text
                            print(f"[DEBUG] Raw HTML contains 'cat-links': {'cat-links' in html_content}")
                            print(f"[DEBUG] Raw HTML contains 'tags-links': {'tags-links' in html_content}")
                            
                            # Farklı parser'ları dene
                            soup = BeautifulSoup(html_content, 'lxml')
                            if not soup.select('.cat-links'):
                                print(f"[DEBUG] lxml parser ile .cat-links bulunamadı, html.parser deneniyor")
                                soup = BeautifulSoup(html_content, 'html.parser')
                            
                            # Debug: Parse edilen HTML'de .cat-links var mı kontrol et
                            print(f"[DEBUG] Parsed HTML contains 'cat-links': {'cat-links' in str(soup)}")
                            print(f"[DEBUG] Parsed HTML contains 'tags-links': {'tags-links' in str(soup)}")
                            
                            # Başlık çıkar
                            title = self.extract_title(soup, url_info)
                            if not title or title in ["Başlık Bulunamadı", "Başlık Çıkarılamadı"]:
                                last_error = "Başlık çıkarılamadı"
                                continue
                            
                            # Kategori ve etiketler - İÇERİK ÇIKARMADAN ÖNCE YAP!
                            # Başarılı olan archive URL'sini kullan - selector'lar bu URL ile kaydediliyor
                            print(f"[DEBUG] Calling extract_categories_and_tags_from_url with archive_url: {archive_url}")
                            categories, tags = self.extract_categories_and_tags_from_url(archive_url, soup, self.mainwindow)
                            
                            # İçerik çıkar - KATEGORİ ÇIKARMADAN SONRA YAP!
                            content = self.extract_main_content(soup)
                            if not content or len(content.strip()) < 200:
                                last_error = f"Yetersiz içerik ({len(content) if content else 0} karakter)"
                                continue
                            
                            # Meta description çıkar
                            meta_description = self.extract_meta_description(soup)
                            
                            # Yayın tarihi
                            publication_date = self.convert_archive_timestamp_to_date(archive_date)
                            if categories or tags:
                                self.progress.emit(f"🏷️ Kategoriler: {', '.join(categories)} | Etiketler: {', '.join(tags)}")
                            else:
                                self.progress.emit(f"⚠️ Kategori/etiket bulunamadı: {url_info['url']}")
                            
                            # Öne çıkan resim
                            featured_image = self.extract_featured_image(soup, url_info)
                            if featured_image:
                                self.progress.emit(f"🖼️ Öne çıkan resim bulundu: {featured_image}")
                            else:
                                self.progress.emit(f"⚠️ Öne çıkan resim bulunamadı: {url_info['url']}")
                            
                            # Yazar
                            author = self.extract_author(soup, url_info)
                            
                            self.progress.emit(f"✅ Başarılı: {title[:50]}...")
                            
                            return {
                                'url': url_info['url'],
                                'archive_url': archive_url,  # Başarılı olan archive URL'sini kullan
                                'timestamp': archive_date,   # Başarılı olan timestamp'i kullan
                                'title': title,
                                'content': content,
                                'meta_description': meta_description,
                                'publication_date': publication_date,
                                'categories': categories,
                                'tags': tags,
                                'featured_image': featured_image,
                                'author': author,
                                'soup': soup
                            }
                        else:
                            last_error = f"HTTP {response.status_code}"
                            continue
                        
                    except requests.Timeout:
                        last_error = "Timeout"
                        continue
                    except requests.ConnectionError:
                        last_error = "Bağlantı hatası"
                        continue
                    except Exception as e:
                        last_error = str(e)
                        continue
                    
                    if getattr(self, 'stop_requested', False):
                        return None
                    
                    if attempt < retry_count - 1:
                        time.sleep(0.5)
            
            self.progress.emit(f"❌ Başarısız: {url_info['url']} - {last_error if last_error else 'Bilinmeyen hata'} (Tüm snapshot ve denemeler tükendi)")
            url_info['failed'] = True
            url_info['fail_reason'] = last_error if last_error else 'Bilinmeyen hata'
            return None
        
        except Exception as e:
            self.progress.emit(f"❌ Başarısız: {url_info['url']} - {str(e)} (Kritik hata)")
            url_info['failed'] = True
            url_info['fail_reason'] = str(e)
            return None

    def extract_categories_and_tags_from_url(self, url, soup=None, mainwindow=None):
        """URL'den kategori ve etiketleri çıkarır (basitleştirilmiş)"""
        categories = set()
        tags = set()
        
        print(f"[DEBUG] extract_categories_and_tags_from_url called with URL: {url}")
        
        # URL'den domain'i çıkar (port dahil)
        from urllib.parse import urlparse
        parsed_url = urlparse(url if url.startswith('http') else f'http://{url}')
        
        # Eğer archive.org URL'si ise, orijinal domain'i çıkar
        if 'web.archive.org' in parsed_url.netloc:
            # Archive URL'den orijinal URL'yi çıkar
            path_parts = parsed_url.path.split('/')
            if len(path_parts) > 5:
                # /web/timestamp/http/www.domain.com/path formatından orijinal URL'yi al
                original_url = 'http://' + '/'.join(path_parts[5:])
                parsed_original = urlparse(original_url)
                domain = parsed_original.netloc
            else:
                domain = parsed_url.netloc
        else:
            domain = parsed_url.netloc  # Bu port'u da içerir
        
        print(f"[DEBUG] Extracted domain: {domain}")
        
        # Domain'i normalize et (www. kaldır) - selector'lar www. olmadan kaydediliyor
        domain = domain.lower().replace('www.', '')  # www. kaldır ve küçük harf yap
        print(f"[DEBUG] Normalized domain: {domain}")
        
        # Genel selector'ları al (URL'ye özel değil)
        if mainwindow and hasattr(mainwindow, 'global_selectors'):
            selected_categories = mainwindow.global_selectors.get('category', [])
            selected_tags = mainwindow.global_selectors.get('tag', [])
            print(f"[DEBUG] Global selectors - Categories: {selected_categories}, Tags: {selected_tags}")
        else:
            selected_categories = []
            selected_tags = []
            print(f"[DEBUG] No global selectors found")
        
        # Domain'e özel selector'ları al (port dahil domain ile)
        if mainwindow and hasattr(mainwindow, 'domain_selectors'):
            print(f"[DEBUG] Available domain selectors: {list(mainwindow.domain_selectors.keys())}")
            domain_categories = mainwindow.domain_selectors.get(domain, {}).get('category', [])
            domain_tags = mainwindow.domain_selectors.get(domain, {}).get('tag', [])
            print(f"[DEBUG] Domain selectors for '{domain}' - Categories: {domain_categories}, Tags: {domain_tags}")
            selected_categories.extend(domain_categories)
            selected_tags.extend(domain_tags)
        
        # Manuel kategorileri çıkar (otomatik tespit açık olsa bile)
        if selected_categories and soup:
            print(f"[DEBUG] Applying {len(selected_categories)} manual category selectors")
            # Debug: Sayfanın HTML'ini kontrol et
            print(f"[DEBUG] Page title: {soup.find('title').get_text() if soup.find('title') else 'No title'}")
            print(f"[DEBUG] Page has .cat-links: {bool(soup.select('.cat-links'))}")
            print(f"[DEBUG] Page has .tags-links: {bool(soup.select('.tags-links'))}")
            print(f"[DEBUG] Full HTML length: {len(str(soup))}")
            print(f"[DEBUG] HTML contains 'cat-links': {'cat-links' in str(soup)}")
            for selector in selected_categories:
                elements = soup.select(selector)
                print(f"[DEBUG] Selector '{selector}' found {len(elements)} elements")
                for element in elements:
                    a_tags = element.find_all('a')
                    if a_tags:
                        for a in a_tags:
                            txt = a.get_text(strip=True)
                            if txt and len(txt) > 1:
                                categories.add(txt.title())
                                print(f"[DEBUG] Added manual category: {txt.title()}")
                    else:
                        txt = element.get_text(strip=True)
                        if txt and len(txt) > 1:
                            categories.add(txt.title())
                            print(f"[DEBUG] Added manual category: {txt.title()}")
        
        # Manuel etiketleri çıkar
        if selected_tags and soup:
            print(f"[DEBUG] Applying {len(selected_tags)} manual tag selectors")
            for selector in selected_tags:
                elements = soup.select(selector)
                print(f"[DEBUG] Selector '{selector}' found {len(elements)} elements")
                for element in elements:
                    a_tags = element.find_all('a')
                    if a_tags:
                        for a in a_tags:
                            txt = a.get_text(strip=True)
                            if txt and len(txt) > 1:
                                tags.add(txt.title())
                                print(f"[DEBUG] Added manual tag: {txt.title()}")
                    else:
                        txt = element.get_text(strip=True)
                        if txt and len(txt) > 1:
                            tags.add(txt.title())
                            print(f"[DEBUG] Added manual tag: {txt.title()}")

        # Otomatik tespit - sadece ilgili switch açıkken
        if soup and mainwindow:
            print(f"[DEBUG] Running automatic detection")
            
            # Kategori tespiti - sadece kategori switch'i açıkken
            if getattr(mainwindow, 'advanced_category_detection', False):
                print(f"[DEBUG] Testing .cat-links a selector")
                cat_elements = soup.select('.cat-links a')
                if cat_elements:
                    print(f"[DEBUG] Found {len(cat_elements)} .cat-links a elements")
                    for el in cat_elements:
                        txt = el.get_text(strip=True)
                        if txt and len(txt) > 1:
                            categories.add(txt.title())
                            print(f"[DEBUG] Added .cat-links category: {txt.title()}")
                else:
                    print(f"[DEBUG] No .cat-links a elements found")
            else:
                print(f"[DEBUG] Kategori tespiti kapalı, atlanıyor")
            
            # Etiket tespiti - sadece etiket switch'i açıkken
            if getattr(mainwindow, 'advanced_tag_detection', False):
                print(f"[DEBUG] Testing .tags-links a selector")
                tag_elements = soup.select('.tags-links a')
                if tag_elements:
                    print(f"[DEBUG] Found {len(tag_elements)} .tags-links a elements")
                    for el in tag_elements:
                        txt = el.get_text(strip=True)
                        if txt and len(txt) > 1:
                            tags.add(txt.title())
                            print(f"[DEBUG] Added .tags-links tag: {txt.title()}")
                else:
                    print(f"[DEBUG] No .tags-links a elements found")
            else:
                print(f"[DEBUG] Etiket tespiti kapalı, atlanıyor")
            
            # Eğer yukarıdaki selector'lar bulunamazsa, diğer selector'ları dene
            if not categories and getattr(mainwindow, 'advanced_category_detection', False):
                print(f"[DEBUG] .cat-links a bulunamadı, diğer selector'lar deneniyor")
                cat_selectors = [
                    # Sadece makale içeriğindeki kategori selector'ları (sidebar/widget'ları hariç)
                    'article .category a', 'article .categories a', 
                    '.post .category a', '.post .categories a',
                    '.entry .category a', '.entry .categories a',
                    '.article .category a', '.article .categories a',
                    '.content .category a', '.content .categories a',
                    '.post-content .category a', '.post-content .categories a',
                    '.entry-content .category a', '.entry-content .categories a',
                    '.article-content .category a', '.article-content .categories a',
                    # Makale meta bilgileri
                    '.post-meta .category', '.entry-meta .category', '.article-meta .category',
                    '.post-info .category', '.entry-info .category', '.article-info .category',
                    # Breadcrumb'lar (sadece makale içindeki)
                    'article .breadcrumb a', 'article .breadcrumbs a',
                    '.post .breadcrumb a', '.post .breadcrumbs a',
                    '.entry .breadcrumb a', '.entry .breadcrumbs a',
                    '.article .breadcrumb a', '.article .breadcrumbs a',
                    # Kategori linkleri
                    '.cat-links a', '.entry-categories a', '.post-categories a', '.category a', '.categories a', '.category-links a',
                    '.post-category', '.entry-category', '.article-category',
                    # Microdata
                    '[itemprop="articleSection"]', '[itemprop="articleCategory"]'
                ]
                for selector in cat_selectors:
                    for el in soup.select(selector):
                        txt = el.get_text(strip=True)
                        if txt and len(txt) > 1 and len(txt) < 50:  # Çok uzun metinleri filtrele
                            categories.add(txt.title())
                            print(f"[DEBUG] Added fallback category: {txt.title()}")
                
                # URL'den kategori çıkarmaya çalış
                if not categories and url:
                    print(f"[DEBUG] URL'den kategori çıkarılmaya çalışılıyor: {url}")
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    path_parts = parsed.path.strip('/').split('/')
                    
                    # Path'teki kategori benzeri kelimeleri ara
                    category_keywords = ['bilgisayar', 'tablet', 'pc', 'laptop', 'telefon', 'mobil', 
                                       'teknoloji', 'haber', 'blog', 'makale', 'yazı', 'post',
                                       'category', 'kategori', 'cat', 'section', 'bolum']
                    
                    for part in path_parts:
                        part_lower = part.lower()
                        if any(keyword in part_lower for keyword in category_keywords):
                            if len(part) > 2:  # Çok kısa parçaları filtrele
                                category = part.replace('-', ' ').replace('_', ' ').title()
                                categories.add(category)
                                print(f"[DEBUG] Added URL-based category: {category}")
                                break
                
                # Gelişmiş otomatik kategori tespiti
                if not categories and soup:
                    print(f"[DEBUG] Gelişmiş otomatik kategori tespiti başlatılıyor")
                    
                    # 1. Breadcrumb'lardan kategori çıkar
                    breadcrumb_selectors = [
                        '.breadcrumb', '.breadcrumbs', '.nav-breadcrumb',
                        '.breadcrumb-nav', '.breadcrumb-trail',
                        '[class*="breadcrumb"]', '[class*="crumb"]'
                    ]
                    for selector in breadcrumb_selectors:
                        breadcrumbs = soup.select(selector)
                        for breadcrumb in breadcrumbs:
                            links = breadcrumb.find_all('a')
                            if len(links) >= 2:  # En az 2 link olmalı (ana sayfa + kategori)
                                # İkinci link genellikle kategori
                                category_link = links[1]
                                txt = category_link.get_text(strip=True)
                                if txt and len(txt) > 2 and len(txt) < 30:
                                    categories.add(txt.title())
                                    print(f"[DEBUG] Added breadcrumb category: {txt.title()}")
                                    break
                        if categories:
                            break
                    
                    # 2. Sidebar'dan kategori çıkarma kaldırıldı - sadece makale içeriğindeki kategoriler alınacak
                    
                    # 3. Meta tag'lerden kategori çıkar
                    if not categories:
                        meta_selectors = [
                            'meta[property="article:section"]',
                            'meta[name="category"]',
                            'meta[property="og:section"]',
                            'meta[name="section"]'
                        ]
                        for selector in meta_selectors:
                            meta = soup.select_one(selector)
                            if meta and meta.get('content'):
                                txt = meta['content'].strip()
                                if txt and len(txt) > 2 and len(txt) < 30:
                                    categories.add(txt.title())
                                    print(f"[DEBUG] Added meta category: {txt.title()}")
                                    break
                    
                    # 4. İçerikten kategori tahmin et
                    if not categories:
                        # Başlıktan kategori tahmin et
                        title = soup.find('title')
                        if title:
                            title_text = title.get_text(strip=True).lower()
                            # Kategori anahtar kelimeleri
                            tech_keywords = ['bilgisayar', 'tablet', 'pc', 'laptop', 'telefon', 'mobil', 'teknoloji']
                            news_keywords = ['haber', 'gündem', 'son dakika', 'spor', 'ekonomi']
                            blog_keywords = ['blog', 'makale', 'yazı', 'post', 'tutorial']
                            
                            if any(keyword in title_text for keyword in tech_keywords):
                                categories.add('Teknoloji')
                                print(f"[DEBUG] Added inferred category: Teknoloji")
                            elif any(keyword in title_text for keyword in news_keywords):
                                categories.add('Haber')
                                print(f"[DEBUG] Added inferred category: Haber")
                            elif any(keyword in title_text for keyword in blog_keywords):
                                categories.add('Blog')
                                print(f"[DEBUG] Added inferred category: Blog")
            
            # Etiketler için fallback selector'lar - sadece etiket switch'i açıkken
            if not tags and getattr(mainwindow, 'advanced_tag_detection', False):
                print(f"[DEBUG] .tags-links a bulunamadı, diğer etiket selector'ları deneniyor")
                tag_selectors = [
                    # Sadece yazıya özel etiket selector'ları (sidebar/widget'ları hariç tut)
                    'article .tag a', 'article .tags a', 
                    '.post .tag a', '.post .tags a',
                    '.entry .tag a', '.entry .tags a',
                    '.article .tag a', '.article .tags a',
                    '.content .tag a', '.content .tags a',
                    '.post-content .tag a', '.post-content .tags a',
                    '.entry-content .tag a', '.entry-content .tags a',
                    '.article-content .tag a', '.article-content .tags a',
                    # Post meta içindeki etiketler
                    '.post-meta .tag a', '.entry-meta .tag a', '.article-meta .tag a',
                    '.post-info .tag a', '.entry-info .tag a', '.article-info .tag a',
                    # Post footer içindeki etiketler
                    '.post-footer .tag a', '.entry-footer .tag a', '.article-footer .tag a',
                    # Microdata
                    'article [itemprop="keywords"] a', 'article [itemprop="tag"] a',
                    '.post [itemprop="keywords"] a', '.post [itemprop="tag"] a',
                    '.entry [itemprop="keywords"] a', '.entry [itemprop="tag"] a',
                    '.article [itemprop="keywords"] a', '.article [itemprop="tag"] a'
                ]
                for selector in tag_selectors:
                    for el in soup.select(selector):
                        txt = el.get_text(strip=True)
                        if txt and len(txt) > 1 and len(txt) < 50:  # Çok uzun metinleri filtrele
                            tags.add(txt.title())
                            print(f"[DEBUG] Added fallback tag: {txt.title()}")
            
            # Gelişmiş otomatik etiket tespiti
            if not tags and getattr(mainwindow, 'advanced_tag_detection', False) and soup:
                print(f"[DEBUG] Gelişmiş otomatik etiket tespiti başlatılıyor")
                
                # 1. Meta tag'lerden etiket çıkar (sadece yazıya özel)
                meta_tag_selectors = [
                    'meta[name="keywords"]',
                    'meta[property="article:tag"]',
                    'meta[name="tags"]',
                    'meta[property="og:tag"]'
                ]
                for selector in meta_tag_selectors:
                    meta = soup.select_one(selector)
                    if meta and meta.get('content'):
                        content = meta['content'].strip()
                        # Virgül veya noktalı virgülle ayrılmış etiketler
                        if ',' in content:
                            tag_list = [tag.strip() for tag in content.split(',')]
                        elif ';' in content:
                            tag_list = [tag.strip() for tag in content.split(';')]
                        else:
                            tag_list = [content]
                        
                        for tag in tag_list:
                            if tag and len(tag) > 2 and len(tag) < 30:
                                tags.add(tag.title())
                                print(f"[DEBUG] Added meta tag: {tag.title()}")
                
                # 2. Başlıktan akıllı etiket çıkar (sadece yazı başlığından)
                if not tags:
                    # Sadece yazı başlığından etiket çıkar, site başlığından değil
                    title_selectors = [
                        'article h1', '.post h1', '.entry h1', '.article h1',
                        'article .title', '.post .title', '.entry .title', '.article .title',
                        'article .post-title', '.post .post-title', '.entry .entry-title', '.article .article-title'
                    ]
                    
                    title_found = False
                    for selector in title_selectors:
                        title_el = soup.select_one(selector)
                        if title_el:
                            title_text = title_el.get_text(strip=True)
                            if title_text and len(title_text) > 5:
                                # Önemli kelimeleri çıkar
                                words = title_text.split()
                                for word in words:
                                    # Temizle
                                    clean_word = ''.join(c for c in word if c.isalnum() or c.isspace())
                                    if clean_word and len(clean_word) > 3 and len(clean_word) < 20:
                                        # Türkçe karakterleri düzelt
                                        clean_word = clean_word.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
                                        tags.add(clean_word.title())
                                        print(f"[DEBUG] Added title-based tag: {clean_word.title()}")
                                        if len(tags) >= 5:  # Maksimum 5 etiket
                                            break
                                title_found = True
                                break
                    
                    # Eğer yazı başlığı bulunamazsa, genel title'dan çıkar
                    if not title_found:
                        title = soup.find('title')
                        if title:
                            title_text = title.get_text(strip=True)
                            # Site adını temizle
                            if ' - ' in title_text:
                                title_text = title_text.split(' - ')[0]
                            elif ' | ' in title_text:
                                title_text = title_text.split(' | ')[0]
                            
                            words = title_text.split()
                            for word in words:
                                clean_word = ''.join(c for c in word if c.isalnum() or c.isspace())
                                if clean_word and len(clean_word) > 3 and len(clean_word) < 20:
                                    clean_word = clean_word.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
                                    tags.add(clean_word.title())
                                    print(f"[DEBUG] Added general title-based tag: {clean_word.title()}")
                                    if len(tags) >= 3:  # Maksimum 3 etiket
                                        break
                
                # 3. İçerikten etiket çıkar (sadece yazı içeriğinden)
                if not tags:
                    # Sadece yazı içeriğinden etiket çıkar
                    content_selectors = [
                        'article p', '.post p', '.entry p', '.article p',
                        'article .content p', '.post .content p', '.entry .content p', '.article .content p',
                        'article .post-content p', '.post .post-content p', '.entry .entry-content p', '.article .article-content p'
                    ]
                    
                    for selector in content_selectors:
                        first_p = soup.select_one(selector)
                        if first_p:
                            p_text = first_p.get_text(strip=True)
                            if p_text and len(p_text) > 20:  # En az 20 karakter olsun
                                words = p_text.split()
                                for word in words:
                                    clean_word = ''.join(c for c in word if c.isalnum() or c.isspace())
                                    if clean_word and len(clean_word) > 4 and len(clean_word) < 15:
                                        tags.add(clean_word.title())
                                        print(f"[DEBUG] Added content-based tag: {clean_word.title()}")
                                        if len(tags) >= 3:  # Maksimum 3 etiket
                                            break
                                break

        print(f"[DEBUG] Final result - Categories: {list(categories)}, Tags: {list(tags)}")
        print(f"[DEBUG] Domain used for selectors: {domain}")
        return list(categories), list(tags)
    
    def extract_title(self, soup, url_info=None):
        """Başlık çıkarır - gelişmiş ve kapsamlı"""
        try:
            # 1. <title> tag'i - en güvenilir
            title_tag = soup.find('title')
            if title_tag and title_tag.text.strip():
                title = title_tag.text.strip()
                # Site adını, yıl, tarih, tire, pipe, çift nokta, » gibi ayraçları temizle
                import re
                # Yıl ve tarihleri temizle
                title = re.sub(r'\b(19|20)\d{2}\b', '', title)
                title = re.sub(r'\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b', '', title)
                # Ayraçlarla böl ve en anlamlı kısmı seç
                separators = [' - ', ' | ', ' :: ', ' : ', ' » ', ' › ', ' — ', '–']
                for sep in separators:
                    if title and sep in title:
                        parts = [p.strip() for p in title.split(sep) if len(p.strip()) > 0]
                        # En uzun ve anlamlı kısmı seç
                        if parts:
                            parts = sorted(parts, key=len, reverse=True)
                            title = parts[0]
                        break
                # Çok kısa veya spam başlıkları filtrele
                if title and len(title) > 10 and len(title) < 200 and not title.lower().startswith('index of'):
                    return title
            # 2. <h1> tag'i - ana başlık
            h1_tags = soup.find_all('h1')
            for h1 in h1_tags:
                if h1 and h1.text.strip():
                    t = h1.text.strip()
                    if len(t) > 10 and len(t) < 200 and not t.lower().startswith('index of'):
                        return t
            # 3. Open Graph başlıkları
            og_selectors = [
                'meta[property="og:title"]',
                'meta[name="twitter:title"]',
                'meta[name="title"]',
                'meta[property="twitter:title"]'
            ]
            for selector in og_selectors:
                meta = soup.select_one(selector)
                if meta and meta.get('content') and meta['content'].strip():
                    t = meta['content'].strip()
                    if len(t) > 10 and len(t) < 200 and not t.lower().startswith('index of'):
                        return t
            # 4. Yaygın class/id'ler ve itemprop
            title_selectors = [
                '.post-title', '.entry-title', '.article-title', '.page-title', '.title',
                '.headline', '.post-headline', '.entry-headline', '.article-headline',
                '[itemprop="headline"]', '[itemprop="name"]', 
                '#title', '#post-title', '#entry-title', '#article-title',
                '.content-title', '.main-title', '.blog-title', '.news-title',
                'h1.post-title', 'h1.entry-title', 'h1.article-title',
                '.post h1', '.entry h1', '.article h1',
                'h2', 'h3', '.page-header', '.page-headline'
            ]
            for selector in title_selectors:
                el = soup.select_one(selector)
                if el and el.text.strip():
                    t = el.text.strip()
                    if len(t) > 10 and len(t) < 200 and not t.lower().startswith('index of'):
                        return t
            # 5. <h2>, <h3> başlıkları (ilk anlamlı olan)
            for tag in ['h2', 'h3']:
                headings = soup.find_all(tag)
                for heading in headings:
                    if heading and heading.text.strip():
                        t = heading.text.strip()
                        if len(t) > 10 and len(t) < 200 and not t.lower().startswith('index of'):
                            return t
            # 6. İçerikten başlık çıkarma (ilk anlamlı paragraf)
            main_content = self.extract_main_content(soup)
            if main_content:
                from bs4 import BeautifulSoup as BS
                content_soup = BS(main_content, 'html.parser')
                first_p = content_soup.find('p')
                if first_p and first_p.text.strip():
                    text = first_p.text.strip()
                    if len(text) > 20:
                        title = text[:60].strip()
                        if title.endswith('...'):
                            title = title[:-3]
                        return title
            # 7. Archive.org URL'den başlık çıkarma (özel)
            if url_info and 'archive_url' in url_info:
                archive_url = url_info['archive_url']
                if 'web.archive.org' in archive_url:
                    from urllib.parse import urlparse, unquote
                    import os
                    path_parts = urlparse(archive_url).path.split('/')
                    for i, part in enumerate(path_parts):
                        if part == 'web' and i + 1 < len(path_parts):
                            if i + 2 < len(path_parts):
                                original_url = '/'.join(path_parts[i+2:])
                                if original_url.startswith('http'):
                                    original_parsed = urlparse(original_url)
                                    path = original_parsed.path
                                    last = os.path.basename(path.strip('/'))
                                    if last:
                                        last = unquote(last)
                                        last = os.path.splitext(last)[0]
                                        title = last.replace('-', ' ').replace('_', ' ').title()
                                        # Spam/kısa başlıkları filtrele
                                        if len(title) > 5 and not title.lower().startswith('index of'):
                                            return title
                                    break
            # 8. Normal URL'den başlık çıkarma (fallback)
            url = ''
            if soup.find('meta', property='og:url'):
                url = soup.find('meta', property='og:url').get('content', '')
            elif soup.find('link', rel='canonical'):
                url = soup.find('link', rel='canonical').get('href', '')
            if url:
                from urllib.parse import urlparse, unquote
                import os
                path = urlparse(url).path
                last = os.path.basename(path.strip('/'))
                if last:
                    last = unquote(last)
                    last = os.path.splitext(last)[0]
                    title = last.replace('-', ' ').replace('_', ' ').title()
                    if len(title) > 5 and not title.lower().startswith('index of'):
                        return title
            return "Başlık Bulunamadı"
        except Exception as e:
            print(f"Başlık çıkarma hatası: {e}")
            return "Başlık Çıkarılamadı"
    
    def extract_main_content(self, soup):
        """Ana içerik çıkarır - HTML formatını koruyarak"""
        try:
            # Gereksiz elementleri temizle ama resimleri koru
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript', 'iframe']):
                element.decompose()
            
            # Ana içerik alanlarını ara - daha fazla selector ekle
            content_selectors = [
                'article', '.post-content', '.entry-content', '.content',
                '.main-content', '#content', '.article-content', 'div[itemprop="articleBody"]',
                'div[role="main"]', '#main', '#primary', '#singular-content',
                '.post-body', '.post-text', '.post-entry', '.entry-body',
                '.article-body', '.story-content', '.post-detail', '.content-area',
                'main', '.main', '.container', '.wrapper', '.page-content',
                '.blog-content', '.news-content', '.text-content',
                '.post', '.entry', '.article', '.story',
                '.content-wrapper', '.content-container', '.content-box',
                '.post-wrapper', '.entry-wrapper', '.article-wrapper'
            ]
            
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    # Gereksiz elementleri temizle
                    for unwanted in content_element(['script', 'style', 'nav', 'aside', 'form', 'noscript', 'iframe', '.sidebar', '.widget', '.advertisement', '.ads', '.social-share', '.related-posts', '.comments']):
                        unwanted.decompose()
                    
                    # Resimleri Archive.org URL'lerine çevir
                    self.fix_image_urls(content_element, soup)
                    
                    # HTML formatını koru
                    html_content = str(content_element)
                    if len(html_content) > 300:  # Yeterli içerik varsa
                        return html_content
            
            # Fallback: body'den çıkar ama gereksiz elementleri temizle
            body = soup.find('body')
            if body:
                # Body'den de gereksiz elementleri temizle
                for element in body(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript', 'iframe', 'ul.menu', 'div.sidebar', '.sidebar', '.menu', '.navigation', '.widget', '.advertisement', '.ads', '.social-share', '.related-posts', '.comments']):
                    element.decompose()
                
                # Resimleri Archive.org URL'lerine çevir
                self.fix_image_urls(body, soup)
                
                # HTML formatını koru
                html_content = str(body)
                if len(html_content) > 200:  # Çok düşük eşik değeri
                    return html_content
            
            # Son çare: Tüm paragrafları topla
            paragraphs = soup.find_all('p')
            if paragraphs:
                content_parts = []
                for p in paragraphs:
                    if p.text.strip() and len(p.text.strip()) > 20:
                        content_parts.append(f"<p>{p.text.strip()}</p>")
                
                if content_parts:
                    return ''.join(content_parts)
            
            return "<p>İçerik çıkarılamadı</p>"
            
        except Exception as e:
            print(f"İçerik çıkarma hatası: {e}")
            return "<p>İçerik çıkarılırken hata oluştu</p>"
    
    def fix_image_urls(self, element, soup):
        """Resim URL'lerini Archive.org URL'lerine çevirir"""
        images = element.find_all('img')
        for img in images:
            src = img.get('src', '')
            if src and not src.startswith('http'):
                # Relative URL'yi absolute yap
                if src.startswith('/'):
                    # Root-relative URL
                    base_url = soup.find('base', href=True)
                    if base_url:
                        src = base_url['href'].rstrip('/') + src
                    else:
                        # Archive.org URL'den domain çıkar
                        archive_url = soup.find('meta', {'property': 'og:url'})
                        if archive_url:
                            src = archive_url['content'].rsplit('/', 1)[0] + src
                else:
                    # Relative URL
                    base_url = soup.find('base', href=True)
                    if base_url:
                        src = base_url['href'].rstrip('/') + '/' + src
                
                # Archive.org URL'sine çevir
                if 'web.archive.org' in src:
                    img['src'] = src
                else:
                    # Orijinal URL'yi Archive.org'a çevir
                    timestamp = soup.find('meta', {'name': 'archive-timestamp'})
                    if timestamp:
                        archive_timestamp = timestamp['content']
                        original_url = src
                        archive_url = f"https://web.archive.org/web/{archive_timestamp}/{original_url}"
                        img['src'] = archive_url
    
    def extract_featured_image(self, soup, url_info):
        """Her yazı için öne çıkan görseli Archive.org'dan doğru şekilde bulur"""
        archive_url = url_info.get('url', '')
        title = url_info.get('title', 'Bilinmeyen Başlık')
        
        # Debug: Başlangıç log'u
        self.progress.emit(f"🔍 Öne çıkan görsel aranıyor: {title}")
        
        # 1. og:image (en güvenilir)
        og = soup.find('meta', {'property': 'og:image'})
        if og and og.get('content'):
            img_url = og['content']
            # Archive.org URL'sine çevir
            if not img_url.startswith('http'):
                # Relative URL'yi absolute Archive.org URL'sine çevir
                img_url = self.convert_to_archive_url(img_url, archive_url)
            elif not img_url.startswith('https://web.archive.org'):
                # Normal URL'yi Archive.org URL'sine çevir
                img_url = self.convert_to_archive_url(img_url, archive_url)
            
            self.progress.emit(f"✅ OG Image bulundu: {basename(img_url)}")
            return img_url
        
        # 2. twitter:image
        tw = soup.find('meta', {'name': 'twitter:image'})
        if tw and tw.get('content'):
            img_url = tw['content']
            if not img_url.startswith('http'):
                img_url = self.convert_to_archive_url(img_url, archive_url)
            elif not img_url.startswith('https://web.archive.org'):
                img_url = self.convert_to_archive_url(img_url, archive_url)
            
            self.progress.emit(f"✅ Twitter Image bulundu: {basename(img_url)}")
            return img_url
        
        # 3. İçerikteki ilk anlamlı img (daha akıllı seçim)
        imgs = soup.find_all('img')
        if imgs:
            self.progress.emit(f"🔍 {len(imgs)} resim bulundu, en iyisi aranıyor...")
            
            # Önce büyük resimleri ara
            for img in imgs:
                src = img.get('src', '')
                if src:
                    # Archive.org URL'sine çevir
                    if not src.startswith('http'):
                        src = self.convert_to_archive_url(src, archive_url)
                    elif not src.startswith('https://web.archive.org'):
                        src = self.convert_to_archive_url(src, archive_url)
                    
                    # Resim boyutlarını kontrol et
                    width = img.get('width', '0')
                    height = img.get('height', '0')
                    
                    # Eğer boyut bilgisi varsa ve büyükse
                    if width and height:
                        try:
                            w, h = int(width), int(height)
                            if w >= 300 and h >= 200:  # Minimum boyut
                                self.progress.emit(f"✅ Büyük resim bulundu ({w}x{h}): {basename(src)}")
                                return src
                        except ValueError:
                            pass
                    
                    # Alt text'e bak - öne çıkan resim olabilir
                    alt = img.get('alt', '').lower()
                    if any(word in alt for word in ['featured', 'hero', 'main', 'banner', 'header', 'kapak', 'ana']):
                        self.progress.emit(f"✅ Alt text'ten öne çıkan resim bulundu: {basename(src)}")
                        return src
            
            # Hiçbiri bulunamadıysa ilk resmi al
            if imgs[0].get('src', ''):
                src = imgs[0].get('src', '')
                if not src.startswith('http'):
                    src = self.convert_to_archive_url(src, archive_url)
                elif not src.startswith('https://web.archive.org'):
                    src = self.convert_to_archive_url(src, archive_url)
                
                self.progress.emit(f"✅ İlk resim seçildi: {basename(src)}")
                return src
        
        self.progress.emit(f"❌ Hiç resim bulunamadı: {title}")
        return ''
    
    def convert_to_archive_url(self, img_url, archive_url):
        """Resim URL'sini Archive.org URL'sine çevirir"""
        try:
            # Archive.org URL'sinden timestamp'i çıkar
            if 'web.archive.org/web/' in archive_url:
                # https://web.archive.org/web/20231201123456/http://example.com/page
                # Buradan timestamp'i al
                parts = archive_url.split('/web/')
                if len(parts) > 1:
                    timestamp_part = parts[1].split('/')[0]
                    original_url_part = '/'.join(parts[1].split('/')[1:])
                    
                    # Eğer img_url relative ise
                    if not img_url.startswith('http'):
                        # Base URL'yi bul
                        if original_url_part.startswith('http'):
                            base_url = original_url_part
                        else:
                            base_url = 'http://' + original_url_part
                        
                        # Relative URL'yi absolute yap
                        if img_url.startswith('/'):
                            absolute_img_url = base_url.rstrip('/') + img_url
                        else:
                            absolute_img_url = base_url.rstrip('/') + '/' + img_url
                    else:
                        absolute_img_url = img_url
                    
                    # Archive.org URL'sine çevir - daha temiz format
                    return f"https://web.archive.org/web/{timestamp_part}im_/{absolute_img_url}"
            
            return img_url
        except Exception as e:
            print(f"URL çevirme hatası: {e}")
            return img_url
    
    def extract_author(self, soup, url_info):
        """Yazar bilgisini çıkarır"""
        # Meta tag'lerden yazar ara
        author_meta = soup.find('meta', {'name': 'author'})
        if author_meta and author_meta.get('content'):
            return author_meta['content']
        
        # og:author
        og_author = soup.find('meta', {'property': 'og:author'})
        if og_author and og_author.get('content'):
            return og_author['content']
        
        # İçerikte yazar bilgisi ara
        author_selectors = [
            '.author', '.byline', '.post-author', '.entry-author',
            '[rel="author"]', '.author-name', '.writer'
        ]
        
        for selector in author_selectors:
            author_element = soup.select_one(selector)
            if author_element:
                author_text = author_element.get_text(strip=True)
                if author_text and len(author_text) < 100:  # Makul uzunlukta
                    return author_text
        
        # URL'den domain adını yazar olarak kullan
        domain = url_info.get('url', '').split('/')[2] if '://' in url_info.get('url', '') else 'ArchiveRadar'
        return domain.replace('www.', '').title()
    
    def extract_meta_description(self, soup):
        """Meta description çıkarır"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content']
        return ""

    def convert_archive_timestamp_to_date(self, timestamp):
        """Archive.org timestamp'ini tarihe çevirir"""
        try:
            return datetime.strptime(timestamp, '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            return timestamp

    def clean_archive_urls(self, content):
        """Archive.org URL'lerini temizler ve orijinal URL'lere çevirir"""
        import re
        
        # Archive.org URL pattern'leri
        archive_patterns = [
            r'https://web\.archive\.org/web/\d+/',
            r'https://web\.archive\.org/web/\d{8}\d{6}/',
            r'https://web\.archive\.org/web/\d{8}/',
        ]
        
        for pattern in archive_patterns:
            content = re.sub(pattern, '', content)
        
        return content

    def extract_categories_and_tags_bulk(self, all_contents):
        """Tüm yazılar için ortak kategori havuzu oluşturur ve akıllı atama yapar."""
        from collections import Counter, defaultdict
        import re
        # 1. Tüm yazılardan kategori adaylarını topla
        all_category_candidates = []
        for c in all_contents:
            soup = c.get('soup')
            url_info = c
            if soup:
                # HTML ve meta'dan
                cat_selectors = [
                    '[rel="category tag"]', '[rel="category"]', '[rel="tag"]',
                    'a.category', 'a.cat', 'a.kategori', 'a[data-category]',
                    'span.category', 'span.cat', 'span.kategori', 'span[data-category]',
                    'div.category', 'div.cat', 'div.kategori', 'div[data-category]',
                    'a[href*="/kategori/"]', 'a[href*="/category/"]', 'a[href*="category"]',
                    '.cat-links a', '.entry-categories a', '.post-categories a', '.category a', '.categories a', '.category-links a'
                ]
                for selector in cat_selectors:
                    for el in soup.select(selector):
                        txt = el.get_text(strip=True)
                        if txt and len(txt) > 1:
                            all_category_candidates.append(txt.title())
                # Meta tag'lerden
                for meta_name in ['category', 'categories', 'kategori']:
                    meta = soup.find('meta', {'name': meta_name})
                    if meta and meta.get('content'):
                        for kw in meta['content'].split(','):
                            kw = kw.strip()
                            if len(kw) > 2 and len(kw) < 30:
                                all_category_candidates.append(kw.title())
            # URL'den
            url_cats, _ = self.extract_categories_and_tags_from_url(url_info.get('url', ''))
            all_category_candidates.extend(url_cats)
            # Başlıktan
            title = c.get('title', '')
            if title:
                for word in re.sub(r'[^a-zA-Z0-9ğüşöçıİĞÜŞÖÇ ]', '', title).split():
                    if len(word) > 4:
                        all_category_candidates.append(word.title())
        # 2. En çok geçen 10 kategoriyi ana havuz olarak seç
        cat_counter = Counter([c for c in all_category_candidates if c and len(c) > 1])
        main_categories = [c for c, _ in cat_counter.most_common(10)]
        # 3. Her yazıya en uygun ana kategoriyi ata
        for c in all_contents:
            candidates = set()
            # HTML, meta, URL, başlık
            soup = c.get('soup')
            url_info = c
            if soup:
                cat_selectors = [
                    '[rel="category tag"]', '[rel="category"]', '[rel="tag"]',
                    'a.category', 'a.cat', 'a.kategori', 'a[data-category]',
                    'span.category', 'span.cat', 'span.kategori', 'span[data-category]',
                    'div.category', 'div.cat', 'div.kategori', 'div[data-category]',
                    'a[href*="/kategori/"]', 'a[href*="/category/"]', 'a[href*="category"]',
                    '.cat-links a', '.entry-categories a', '.post-categories a', '.category a', '.categories a', '.category-links a'
                ]
                for selector in cat_selectors:
                    for el in soup.select(selector):
                        txt = el.get_text(strip=True)
                        if txt and len(txt) > 1:
                            candidates.add(txt.title())
                for meta_name in ['category', 'categories', 'kategori']:
                    meta = soup.find('meta', {'name': meta_name})
                    if meta and meta.get('content'):
                        for kw in meta['content'].split(','):
                            kw = kw.strip()
                            if len(kw) > 2 and len(kw) < 30:
                                candidates.add(kw.title())
            url_cats, _ = self.extract_categories_and_tags_from_url(url_info.get('url', ''))
            candidates.update(url_cats)
            title = c.get('title', '')
            if title:
                for word in re.sub(r'[^a-zA-Z0-9ğüşöçıİĞÜŞÖÇ ]', '', title).split():
                    if len(word) > 4:
                        candidates.add(word.title())
            # En çok eşleşen ana kategoriyi ata
            assigned = None
            for main_cat in main_categories:
                if main_cat in candidates:
                    assigned = main_cat
                    break
            if not assigned and main_categories:
                assigned = main_categories[0]
            if not assigned:
                assigned = 'Genel'
            c['categories'] = [assigned]
            # Etiketler: başlık, meta desc, içerikten en çok geçen 5 kelime
            tags = set()
            meta_desc = c.get('meta_description', '')
            for text in [title, meta_desc]:
                if text:
                    for word in re.sub(r'[^a-zA-Z0-9ğüşöçıİĞÜŞÖÇ ]', '', text).split():
                        if len(word) > 3:
                            tags.add(word.title())
            content = c.get('content', '')
            if content:
                text = re.sub(r'<[^>]+>', ' ', content)
                text = re.sub(r'[^a-zA-Z0-9ğüşöçıİĞÜŞÖÇ ]', '', text)
                words = [w.title() for w in text.split() if len(w) > 3 and len(w) < 30]
                from collections import Counter
                for word, count in Counter(words).most_common(5):
                    tags.add(word)
            c['tags'] = list(tags)[:5]
        return all_contents

class UrlSelectionWindow(QDialog):
    def __init__(self, category_name, urls_with_snapshots, is_blog_post_func, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{category_name} - URL'leri Seç")
        self.setGeometry(200, 200, 1000, 700)
        self.urls_with_snapshots = urls_with_snapshots # {url: [snapshot1, snapshot2, ...]}
        self.selected_urls = [] # Seçilen URL ve snapshot bilgilerini tutacak
        self.is_blog_post = is_blog_post_func
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Arama kutusu
        search_layout = QHBoxLayout()
        search_label = QLabel("Ara:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("URL'de ara...")
        self.search_input.textChanged.connect(self.filter_urls)  # Yazarken anında filtrele
        self.search_input.returnPressed.connect(self.add_filter_tag)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        main_layout.addLayout(search_layout)

        # Etiketler için alan - Scroll Area ile
        from PySide6.QtWidgets import QScrollArea, QFrame
        from PySide6.QtCore import Qt
        
        # Scroll Area oluştur
        self.filter_scroll_area = QScrollArea()
        self.filter_scroll_area.setWidgetResizable(True)
        self.filter_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.filter_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.filter_scroll_area.setMaximumHeight(50)  # Daha küçük maksimum yükseklik
        self.filter_scroll_area.setMinimumHeight(25)  # Daha küçük minimum yükseklik
        self.filter_scroll_area.setFrameShape(QFrame.NoFrame)
        self.filter_scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #34495e;
                border-radius: 4px;
                background-color: #2c3e50;
            }
            QScrollBar:horizontal {
                border: none;
                background: #34495e;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #4ecdc4;
                border-radius: 4px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #45b7af;
            }
            QScrollBar:vertical {
                border: none;
                background: #34495e;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #4ecdc4;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #45b7af;
            }
        """)
        
        # İç widget ve layout
        self.filter_tag_widget = QWidget()
        self.filter_tag_layout = QHBoxLayout(self.filter_tag_widget)
        self.filter_tag_layout.setContentsMargins(5, 5, 5, 5)
        self.filter_tag_layout.setSpacing(5)
        
        self.filter_scroll_area.setWidget(self.filter_tag_widget)
        main_layout.addWidget(self.filter_scroll_area)
        self.active_filters = []

        # Filtreleme davranışı için combobox
        from PySide6.QtWidgets import QComboBox
        self.filter_mode_combo = QComboBox()
        self.filter_mode_combo.addItem("Filtrelenenleri listeden kaldır")
        self.filter_mode_combo.addItem("Sadece filtreye uyanları göster")
        self.filter_mode_combo.currentIndexChanged.connect(self.filter_urls)
        main_layout.addWidget(self.filter_mode_combo)

        # Sol taraf: URL Listesi
        self.url_list_widget = QListWidget()
        self.url_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.url_list_widget.itemSelectionChanged.connect(self.display_snapshots_for_selected_url)
        self.url_list_widget.itemSelectionChanged.connect(self.update_add_selected_button_state)
        main_layout.addWidget(self.url_list_widget)
        
        # Sağ taraf: Snapshot Detayları (gizli)
        self.snapshot_detail_group = QGroupBox("Snapshot Detayları")
        self.snapshot_detail_group.setVisible(False)
        detail_layout = QVBoxLayout(self.snapshot_detail_group)
        
        self.current_url_label = QLabel("")
        self.current_url_label.setStyleSheet("font-weight: bold;")
        detail_layout.addWidget(self.current_url_label)
        
        self.snapshot_combo = QComboBox()
        self.snapshot_combo.currentIndexChanged.connect(self.update_snapshot_display)
        detail_layout.addWidget(self.snapshot_combo)
        
        # Kategori, etiket, görsel, yazar, tarih detayları için alanlar
        self.detail_info_label = QLabel("")
        self.detail_info_label.setWordWrap(True)
        self.detail_info_label.setStyleSheet("color: #f1c40f; font-size: 13px; margin-top: 5px;")
        detail_layout.addWidget(self.detail_info_label)
        
        # Arşiv URL'si ve kopyala butonu
        url_copy_layout = QHBoxLayout()
        self.snapshot_url_label = QLineEdit("")
        self.snapshot_url_label.setReadOnly(True)
        self.snapshot_url_label.setStyleSheet("font-style: italic; color: #bbbbbb;")
        url_copy_layout.addWidget(self.snapshot_url_label)
        self.copy_url_button = QPushButton("Kopyala")
        self.copy_url_button.setToolTip("Arşiv URL'sini kopyala")
        self.copy_url_button.clicked.connect(self.copy_archive_url)
        url_copy_layout.addWidget(self.copy_url_button)
        detail_layout.addLayout(url_copy_layout)
        
        self.view_in_browser_button = QPushButton("Tarayıcıda Görüntüle")
        self.view_in_browser_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                font-size: 13px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.view_in_browser_button.clicked.connect(self.open_archive_url_in_browser)
        self.view_in_browser_button.setEnabled(False) # Başlangıçta pasif
        detail_layout.addWidget(self.view_in_browser_button)
        
        main_layout.addWidget(self.snapshot_detail_group)
        
        # Otomatik Tespit Butonu
        auto_detect_layout = QHBoxLayout()
        
        self.auto_detect_button = QPushButton("🔍 Akıllı Kategori/Etiket Tespit Et")
        self.auto_detect_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
                transform: scale(1.02);
            }
            QPushButton:pressed {
                background-color: #1e8449;
                transform: scale(0.98);
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        self.auto_detect_button.clicked.connect(self.start_auto_detection)
        auto_detect_layout.addWidget(self.auto_detect_button)
        
        # İlerleme etiketi
        self.auto_detect_progress = QLabel("")
        self.auto_detect_progress.setStyleSheet("color: #f39c12; font-weight: bold;")
        auto_detect_layout.addWidget(self.auto_detect_progress)
        
        auto_detect_layout.addStretch()
        main_layout.addLayout(auto_detect_layout)
        
        # Kategori ve Etiket Seçim Butonları
        selector_button_layout = QHBoxLayout()
        
        self.category_selector_button = QPushButton("🎯 Kategori Element Seç")
        self.category_selector_button.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                padding: 8px 15px;
                font-size: 13px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d35400;
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background-color: #c0392b;
                transform: scale(0.95);
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
                border: 2px solid #bdc3c7;
            }
        """)
        self.category_selector_button.clicked.connect(self.open_category_selector)
        self.category_selector_button.setEnabled(False)  # Başlangıçta pasif
        selector_button_layout.addWidget(self.category_selector_button)
        
        self.tag_selector_button = QPushButton("🏷️ Etiket Element Seç")
        self.tag_selector_button.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                padding: 8px 15px;
                font-size: 13px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8e44ad;
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background-color: #7d3c98;
                transform: scale(0.95);
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
                border: 2px solid #bdc3c7;
            }
        """)
        self.tag_selector_button.clicked.connect(self.open_tag_selector)
        self.tag_selector_button.setEnabled(False)  # Başlangıçta pasif
        selector_button_layout.addWidget(self.tag_selector_button)
        
        main_layout.addLayout(selector_button_layout)
        
        # Butonlar
        button_layout = QHBoxLayout()
        
        self.add_selected_button = QPushButton("✅ Seçilenleri Ekle")
        self.add_selected_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: 2px solid #2ecc71;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
                border-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                border-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.add_selected_button.clicked.connect(self.add_selected_items)
        self.add_selected_button.setEnabled(False) # Başlangıçta pasif
        button_layout.addWidget(self.add_selected_button)
        
        self.ok_button = QPushButton("✅ Tamam")
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: 2px solid #5dade2;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #5dade2;
                border-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #2980b9;
            }
        """)
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("❌ İptal")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: 2px solid #ec7063;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #ec7063;
                border-color: #e74c3c;
            }
            QPushButton:pressed {
                background-color: #c0392b;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        
        self.populate_url_list()

    def populate_url_list(self):
        """URL listesini doldurur - HIZLI VERSİYON"""
        self.url_list_widget.clear()
        self.url_to_snapshots = self.urls_with_snapshots
        
        # Parent window'ı bul
        parent_window = self.parent()
        while parent_window and not hasattr(parent_window, 'detected_categories_cache'):
            parent_window = parent_window.parent()
        
        for i, (url, snapshots) in enumerate(self.url_to_snapshots.items(), 1):
            # En yeni snapshot'ın tarihini göster
            latest = max(snapshots, key=lambda s: s['timestamp'])
            try:
                date_obj = datetime.strptime(latest['timestamp'], '%Y%m%d%H%M%S')
                formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
            except:
                formatted_date = latest['timestamp']
            
            # Title değişkenini tanımla (şimdilik None)
            title = None
            
            # Sadece cache'den kategori/etiket bilgilerini al
            selector_info = ""
            if parent_window and hasattr(parent_window, 'detected_categories_cache') and url in parent_window.detected_categories_cache:
                cached_data = parent_window.detected_categories_cache[url]
                cached_categories = cached_data.get('categories', [])
                cached_tags = cached_data.get('tags', [])
                if cached_categories or cached_tags:
                    selector_info = f" | 🔍"
                    if cached_categories:
                        cat_preview = ", ".join(cached_categories[:2])
                        if len(cached_categories) > 2:
                            cat_preview += f" (+{len(cached_categories)-2})"
                        selector_info += f" 📂 {cat_preview}"
                    if cached_tags:
                        tag_preview = ", ".join(cached_tags[:2])
                        if len(cached_tags) > 2:
                            tag_preview += f" (+{len(cached_tags)-2})"
                        selector_info += f" 🏷️ {tag_preview}"
            
            # Domain'i URL'den çıkar
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower().replace('www.', '')
            
            # Selector bilgilerini kontrol et
            selector_info = ""
            
            # 1. GLOBAL SELECTOR'LARI KONTROL ET
            global_selector_info = ""
            if parent_window and hasattr(parent_window, 'global_selectors'):
                global_cat_selectors = parent_window.global_selectors.get('category', [])
                global_tag_selectors = parent_window.global_selectors.get('tag', [])
                if global_cat_selectors or global_tag_selectors:
                    global_selector_info = f" | 🌍"
                    if global_cat_selectors:
                        # Kategori isimlerini göster (ilk 3 tanesi)
                        cat_names = []
                        for selector in global_cat_selectors[:3]:
                            # Selector'dan kategori ismini çıkar (| işaretinden sonrası)
                            if '|' in selector:
                                cat_name = selector.split('|')[1].strip()[:15]
                                if cat_name and not cat_name.startswith('.'):  # CSS selector değilse
                                    cat_names.append(cat_name)
                            else:
                                # CSS selector ise atla
                                continue
                        if cat_names:
                            cat_display = ", ".join(cat_names)
                            if len(global_cat_selectors) > 3:
                                cat_display += f" (+{len(global_cat_selectors)-3})"
                            global_selector_info += f" 📂 {cat_display}"
                        else:
                            global_selector_info += f" 📂 {len(global_cat_selectors)}"
                    if global_tag_selectors:
                        tag_names = []
                        for selector in global_tag_selectors[:3]:
                            if '|' in selector:
                                tag_name = selector.split('|')[1].strip()[:15]
                                if tag_name and not tag_name.startswith('.'):
                                    tag_names.append(tag_name)
                            else:
                                continue
                        if tag_names:
                            tag_display = ", ".join(tag_names)
                            if len(global_tag_selectors) > 3:
                                tag_display += f" (+{len(global_tag_selectors)-3})"
                            global_selector_info += f" 🏷️ {tag_display}"
                        else:
                            global_selector_info += f" 🏷️ {len(global_tag_selectors)}"
            
            # 2. URL BAZLI SEÇİMLERİ KONTROL ET
            url_selections = ""
            selector_count_info = ""
            if parent_window and hasattr(parent_window, 'url_selections'):
                if url in parent_window.url_selections:
                    url_selectors = parent_window.url_selections[url]
                    cat_selections = url_selectors.get('category', [])
                    tag_selections = url_selectors.get('tag', [])
                    if cat_selections or tag_selections:
                        url_selections = f" | ✅"
                        if cat_selections:
                            cat_preview = ", ".join(cat_selections[:2])
                            if len(cat_selections) > 2:
                                cat_preview += f" (+{len(cat_selections)-2})"
                            url_selections += f" 📂 {cat_preview}"
                        if tag_selections:
                            tag_preview = ", ".join(tag_selections[:2])
                            if len(tag_selections) > 2:
                                tag_preview += f" (+{len(tag_selections)-2})"
                            url_selections += f" 🏷️ {tag_preview}"
                        selector_count_info = f"Seçilen Kategori/Etiket: {len(cat_selections)}/{len(tag_selections)}"
            
            # 3. DOMAIN BAZLI SELECTOR'LARI KONTROL ET
            domain_selector_info = ""
            if parent_window and hasattr(parent_window, 'domain_selectors'):
                if domain in parent_window.domain_selectors:
                    selectors = parent_window.domain_selectors[domain]
                    cat_selectors = selectors.get('category', [])
                    tag_selectors = selectors.get('tag', [])
                    if cat_selectors or tag_selectors:
                        domain_selector_info = f" | 🎯"
                        if cat_selectors:
                            cat_preview = ", ".join(cat_selectors[:2])
                            if len(cat_selectors) > 2:
                                cat_preview += f" (+{len(cat_selectors)-2})"
                            domain_selector_info += f" 📂 {cat_preview}"
                        if tag_selectors:
                            tag_preview = ", ".join(tag_selectors[:2])
                            if len(tag_selectors) > 2:
                                tag_preview += f" (+{len(tag_selectors)-2})"
                            domain_selector_info += f" 🏷️ {tag_preview}"
            
            # 4. ÖNCELİK SIRASI: URL > CACHE > DOMAIN > GLOBAL
            auto_detection = getattr(parent_window, 'auto_category_tag_detection', True)
            
            # --- YENİ: CACHE'DEN OTOMATİK TESPİT EDİLEN KATEGORİ/ETİKETLERİ GÖSTER ---
            cache_selector_info = ""
            if parent_window and hasattr(parent_window, 'detected_categories_cache') and url in parent_window.detected_categories_cache:
                cached_data = parent_window.detected_categories_cache[url]
                cached_categories = cached_data.get('categories', [])
                cached_tags = cached_data.get('tags', [])
                if cached_categories or cached_tags:
                    cache_selector_info = f" | 🔍"
                    if cached_categories:
                        cat_preview = ", ".join(cached_categories[:2])
                        if len(cached_categories) > 2:
                            cat_preview += f" (+{len(cached_categories)-2})"
                        cache_selector_info += f" 📂 {cat_preview}"
                    if cached_tags:
                        tag_preview = ", ".join(cached_tags[:2])
                        if len(cached_tags) > 2:
                            tag_preview += f" (+{len(cached_tags)-2})"
                        cache_selector_info += f" 🏷️ {tag_preview}"
            # --- SON YENİ ---
            
            if url_selections:
                selector_info = url_selections
            elif cache_selector_info:
                selector_info = cache_selector_info
            elif domain_selector_info and (not auto_detection or (auto_detection and not global_selector_info)):
                selector_info = domain_selector_info
            elif global_selector_info:
                selector_info = global_selector_info
            else:
                selector_info = ""
            
            # Otomatik tespit edilenleri ekle (cache'den)
            if parent_window and hasattr(parent_window, 'auto_detection_cache'):
                if url in parent_window.auto_detection_cache:
                    cache_data = parent_window.auto_detection_cache[url]
                    otomatik_categories = cache_data.get('categories', [])
                    otomatik_tags = cache_data.get('tags', [])
                    if otomatik_categories or otomatik_tags:
                        otomatik_info = " | 🤖"
                        if otomatik_categories:
                            otomatik_info += f" 📂 {', '.join(otomatik_categories[:2])}"
                            if len(otomatik_categories) > 2:
                                otomatik_info += f" (+{len(otomatik_categories)-2})"
                        if otomatik_tags:
                            otomatik_info += f" 🏷️ {', '.join(otomatik_tags[:2])}"
                            if len(otomatik_tags) > 2:
                                otomatik_info += f" (+{len(otomatik_tags)-2})"
                        selector_info += otomatik_info
            
            # Başlık varsa ekle
            if title:
                item_text = f"{i}. {title}\n   🌐 {url}  ({len(snapshots)} sürüm){selector_info}\n   📅 {formatted_date}"
            else:
                item_text = f"{i}. {url}  ({len(snapshots)} sürüm){selector_info}\n   📅 {formatted_date}"
            if selector_count_info:
                item_text += f"\n   {selector_count_info}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, url)
            self.url_list_widget.addItem(item)

    def add_filter_tag(self):
        text = self.search_input.text().strip()
        if text and text not in self.active_filters:
            self.active_filters.append(text)
            self.update_filter_tags()
            self.search_input.clear()
            self.filter_urls()

    def update_filter_tags(self):
        # Önce eski etiketleri temizle
        while self.filter_tag_layout.count():
            child = self.filter_tag_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Yeni etiketleri ekle
        for tag in self.active_filters:
            tag_widget = QWidget()
            tag_layout = QHBoxLayout(tag_widget)
            tag_layout.setContentsMargins(1, 1, 1, 1)
            tag_layout.setSpacing(1)
            
            # Etiket metni - daha kısa maksimum uzunluk
            display_text = tag[:15] + "..." if len(tag) > 15 else tag
            label = QLabel(display_text)
            label.setToolTip(tag)  # Tam metni tooltip'te göster
            label.setStyleSheet("""
                color: #4ecdc4; 
                font-size: 9px;
                font-weight: bold;
                padding: 1px 3px;
                margin-right: 2px;
                background: transparent;
                border: none;
            """)
            
            # Silme butonu - daha küçük ve sade
            remove_btn = QPushButton("×")
            remove_btn.setFixedSize(10, 10)
            remove_btn.setStyleSheet("""
                background: transparent; 
                color: #e74c3c; 
                border: none; 
                font-weight: bold;
                font-size: 10px;
            """)
            remove_btn.clicked.connect(lambda _, t=tag: self.remove_filter_tag(t))
            
            tag_layout.addWidget(label)
            tag_layout.addWidget(remove_btn)
            
            # Widget'ı layout'a ekle
            self.filter_tag_layout.addWidget(tag_widget)
        
        # Stretch ekle
        self.filter_tag_layout.addStretch()
        
        # Scroll area'yı güncelle
        self.filter_scroll_area.updateGeometry()

    def remove_filter_tag(self, tag):
        if tag in self.active_filters:
            self.active_filters.remove(tag)
            self.update_filter_tags()
            self.filter_urls()

    def filter_urls(self):
        self.url_list_widget.clear()
        row_number = 1
        filters = [f.lower() for f in self.active_filters]
        # Arama kutusundaki anlık kelimeyi de ekle (boş değilse ve etiketlerde yoksa)
        current_text = self.search_input.text().strip().lower()
        if current_text and current_text not in filters:
            filters.append(current_text)
        filter_mode = self.filter_mode_combo.currentIndex()  # 0: gizle, 1: sadece göster
        
        # Parent window'dan domain_selectors'a eriş
        parent_window = self.parent()
        while parent_window and not hasattr(parent_window, 'domain_selectors'):
            parent_window = parent_window.parent()
        
        for i, (url, snapshots) in enumerate(self.url_to_snapshots.items(), 1):
            match = False
            if filters:
                for keyword in filters:
                    if keyword in url.lower():
                        match = True
                        break
            if filter_mode == 0:
                # Filtreye uyanları gizle
                if match:
                    continue
            elif filter_mode == 1:
                # Sadece filtreye uyanları göster
                if not match:
                    continue
            latest = max(snapshots, key=lambda s: s['timestamp'])
            try:
                date_obj = datetime.strptime(latest['timestamp'], '%Y%m%d%H%M%S')
                formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
            except:
                formatted_date = latest['timestamp']
            
            # Title değişkenini tanımla (şimdilik None)
            title = None
            
            # Domain'i URL'den çıkar
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower().replace('www.', '')
            
            # Selector bilgilerini kontrol et
            selector_info = ""
            
            # 1. GLOBAL SELECTOR'LARI KONTROL ET
            global_selector_info = ""
            if parent_window and hasattr(parent_window, 'global_selectors'):
                global_cat_selectors = parent_window.global_selectors.get('category', [])
                global_tag_selectors = parent_window.global_selectors.get('tag', [])
                if global_cat_selectors or global_tag_selectors:
                    global_selector_info = f" | 🌍"
                    if global_cat_selectors:
                        # Kategori isimlerini göster (ilk 3 tanesi)
                        cat_names = []
                        for selector in global_cat_selectors[:3]:
                            # Selector'dan kategori ismini çıkar (| işaretinden sonrası)
                            if '|' in selector:
                                cat_name = selector.split('|')[1].strip()[:15]
                                if cat_name and not cat_name.startswith('.'):  # CSS selector değilse
                                    cat_names.append(cat_name)
                            else:
                                # CSS selector ise atla
                                continue
                        if cat_names:
                            cat_display = ", ".join(cat_names)
                            if len(global_cat_selectors) > 3:
                                cat_display += f" (+{len(global_cat_selectors)-3})"
                            global_selector_info += f" 📂 {cat_display}"
                        else:
                            global_selector_info += f" 📂 {len(global_cat_selectors)}"
                    if global_tag_selectors:
                        tag_names = []
                        for selector in global_tag_selectors[:3]:
                            if '|' in selector:
                                tag_name = selector.split('|')[1].strip()[:15]
                                if tag_name and not tag_name.startswith('.'):
                                    tag_names.append(tag_name)
                            else:
                                continue
                        if tag_names:
                            tag_display = ", ".join(tag_names)
                            if len(global_tag_selectors) > 3:
                                tag_display += f" (+{len(global_tag_selectors)-3})"
                            global_selector_info += f" 🏷️ {tag_display}"
                        else:
                            global_selector_info += f" 🏷️ {len(global_tag_selectors)}"
            
            # 2. URL BAZLI SEÇİMLERİ KONTROL ET
            url_selections = ""
            selector_count_info = ""
            if parent_window and hasattr(parent_window, 'url_selections'):
                if url in parent_window.url_selections:
                    url_selectors = parent_window.url_selections[url]
                    cat_selections = url_selectors.get('category', [])
                    tag_selections = url_selectors.get('tag', [])
                    if cat_selections or tag_selections:
                        url_selections = f" | ✅"
                        if cat_selections:
                            cat_preview = ", ".join(cat_selections[:2])
                            if len(cat_selections) > 2:
                                cat_preview += f" (+{len(cat_selections)-2})"
                            url_selections += f" 📂 {cat_preview}"
                        if tag_selections:
                            tag_preview = ", ".join(tag_selections[:2])
                            if len(tag_selections) > 2:
                                tag_preview += f" (+{len(tag_selections)-2})"
                            url_selections += f" 🏷️ {tag_preview}"
                        selector_count_info = f"Seçilen Kategori/Etiket: {len(cat_selections)}/{len(tag_selections)}"
            
            # 3. DOMAIN BAZLI SELECTOR'LARI KONTROL ET
            domain_selector_info = ""
            if parent_window and hasattr(parent_window, 'domain_selectors'):
                if domain in parent_window.domain_selectors:
                    selectors = parent_window.domain_selectors[domain]
                    cat_selectors = selectors.get('category', [])
                    tag_selectors = selectors.get('tag', [])
                    if cat_selectors or tag_selectors:
                        domain_selector_info = f" | 🎯"
                        if cat_selectors:
                            cat_preview = ", ".join(cat_selectors[:2])
                            if len(cat_selectors) > 2:
                                cat_preview += f" (+{len(cat_selectors)-2})"
                            domain_selector_info += f" 📂 {cat_preview}"
                        if tag_selectors:
                            tag_preview = ", ".join(tag_selectors[:2])
                            if len(tag_selectors) > 2:
                                tag_preview += f" (+{len(tag_selectors)-2})"
                            domain_selector_info += f" 🏷️ {tag_preview}"
            
            # 4. ÖNCELİK SIRASI: URL > CACHE > DOMAIN > GLOBAL
            auto_detection = getattr(parent_window, 'auto_category_tag_detection', True)
            
            # --- YENİ: CACHE'DEN OTOMATİK TESPİT EDİLEN KATEGORİ/ETİKETLERİ GÖSTER ---
            cache_selector_info = ""
            if parent_window and hasattr(parent_window, 'detected_categories_cache') and url in parent_window.detected_categories_cache:
                cached_data = parent_window.detected_categories_cache[url]
                cached_categories = cached_data.get('categories', [])
                cached_tags = cached_data.get('tags', [])
                if cached_categories or cached_tags:
                    cache_selector_info = f" | 🔍"
                    if cached_categories:
                        cat_preview = ", ".join(cached_categories[:2])
                        if len(cached_categories) > 2:
                            cat_preview += f" (+{len(cached_categories)-2})"
                        cache_selector_info += f" 📂 {cat_preview}"
                    if cached_tags:
                        tag_preview = ", ".join(cached_tags[:2])
                        if len(cached_tags) > 2:
                            tag_preview += f" (+{len(cached_tags)-2})"
                        cache_selector_info += f" 🏷️ {tag_preview}"
            # --- SON YENİ ---
            
            if url_selections:
                selector_info = url_selections
            elif cache_selector_info:
                selector_info = cache_selector_info
            elif domain_selector_info and (not auto_detection or (auto_detection and not global_selector_info)):
                selector_info = domain_selector_info
            elif global_selector_info:
                selector_info = global_selector_info
            else:
                selector_info = ""
            
            # Otomatik tespit edilenleri ekle (cache'den)
            if parent_window and hasattr(parent_window, 'auto_detection_cache'):
                if url in parent_window.auto_detection_cache:
                    cache_data = parent_window.auto_detection_cache[url]
                    otomatik_categories = cache_data.get('categories', [])
                    otomatik_tags = cache_data.get('tags', [])
                    if otomatik_categories or otomatik_tags:
                        otomatik_info = " | 🤖"
                        if otomatik_categories:
                            otomatik_info += f" 📂 {', '.join(otomatik_categories[:2])}"
                            if len(otomatik_categories) > 2:
                                otomatik_info += f" (+{len(otomatik_categories)-2})"
                        if otomatik_tags:
                            otomatik_info += f" 🏷️ {', '.join(otomatik_tags[:2])}"
                            if len(otomatik_tags) > 2:
                                otomatik_info += f" (+{len(otomatik_tags)-2})"
                        selector_info += otomatik_info
            
            # Başlık varsa ekle
            if title:
                item_text = f"{i}. {title}\n   🌐 {url}  ({len(snapshots)} sürüm){selector_info}\n   📅 {formatted_date}"
            else:
                item_text = f"{i}. {url}  ({len(snapshots)} sürüm){selector_info}\n   📅 {formatted_date}"
            if selector_count_info:
                item_text += f"\n   {selector_count_info}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, url)
            self.url_list_widget.addItem(item)

    def display_snapshots_for_selected_url(self):
        selected_items = self.url_list_widget.selectedItems()
        self.snapshot_combo.clear()
        self.snapshot_url_label.clear()
        self.view_in_browser_button.setEnabled(bool(selected_items))
        
        if selected_items:
            self.snapshot_detail_group.setVisible(True)
            selected_url = selected_items[0].data(Qt.UserRole)
            self.current_url_label.setText(f"Seçilen URL: {selected_url}")
            # Tüm snapshot'ları combo box'a ekle
            snapshots = self.url_to_snapshots[selected_url]
            
            # Snapshot'ları özel sıralama: önce seçili URL'ye en yakın olanlar
            def sort_key(snap):
                original_url = snap['original_url']
                
                # 1. Öncelik: Tam eşleşme (normalize edilmiş URL ile)
                # normalize_url metodunu burada tanımla
                def normalize_url(url):
                    parsed = urlparse(url)
                    if parsed.port:
                        netloc = parsed.netloc.split(':')[0]
                        url = url.replace(f":{parsed.port}", "")
                    return url
                
                normalized_original = normalize_url(original_url)
                if normalized_original == selected_url:
                    return (0, -int(snap['timestamp']))  # En yeni timestamp'i önce göster
                
                # 2. Öncelik: Port numarası olmayan versiyon
                parsed_original = urlparse(original_url)
                if parsed_original.port is None:
                    return (1, -int(snap['timestamp']))  # En yeni timestamp'i önce göster
                else:
                    return (2, -int(snap['timestamp']))  # En yeni timestamp'i önce göster
            
            sorted_snapshots = sorted(snapshots, key=sort_key, reverse=True)
            
            for snap in sorted_snapshots:
                try:
                    timestamp_dt = datetime.strptime(snap['timestamp'], '%Y%m%d%H%M%S')
                    formatted_date = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted_date = snap['timestamp']
                
                # URL'yi de göster ki kullanıcı hangi versiyonu seçtiğini bilsin
                display_text = f"{formatted_date} - {snap['original_url']}"
                self.snapshot_combo.addItem(display_text, snap)
            
            self.snapshot_combo.setCurrentIndex(0)
            self.update_snapshot_display()
            
            # Debug: İlk seçili snapshot'ı göster
            if sorted_snapshots:
                first_snapshot = sorted_snapshots[0]
                print(f"🔍 İlk seçili snapshot: {first_snapshot['original_url']}")
                print(f"🔍 Archive URL: {first_snapshot['archive_url']}")
                print(f"🔍 Timestamp: {first_snapshot['timestamp']}")
        else:
            self.snapshot_detail_group.setVisible(False)

    def update_snapshot_display(self):
        selected_snapshot_data = self.snapshot_combo.currentData()
        if selected_snapshot_data:
            self.snapshot_url_label.setText(selected_snapshot_data['archive_url'])
            self.view_in_browser_button.setEnabled(True)
            
            # Detay bilgilerini göster
            original_url = selected_snapshot_data['original_url']
            timestamp = selected_snapshot_data['timestamp']
            try:
                timestamp_dt = datetime.strptime(timestamp, '%Y%m%d%H%M%S')
                formatted_date = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                formatted_date = timestamp
            
            detail_text = f"Orijinal URL: {original_url}\nTarih: {formatted_date}"
            self.detail_info_label.setText(detail_text)
        else:
            self.snapshot_url_label.clear()
            self.view_in_browser_button.setEnabled(False)
            self.detail_info_label.setText("")

    def open_archive_url_in_browser(self):
        """Seçilen snapshot'ın arşiv URL'sini varsayılan tarayıcıda açar"""
        selected_snapshot_data = self.snapshot_combo.currentData()
        if selected_snapshot_data and 'archive_url' in selected_snapshot_data:
            QDesktopServices.openUrl(QUrl(selected_snapshot_data['archive_url']))
        else:
            QMessageBox.warning(self, "Uyarı", "Görüntülenecek bir arşiv URL'si seçili değil.")

    def add_selected_items(self):
        try:
            print("📋 Seçilen URL'ler ekleniyor...")
            selected_urls = []
            
            for item in self.url_list_widget.selectedItems():
                selected_url = item.data(Qt.UserRole)
                print(f"🎯 Seçilen URL: {selected_url}")
                
                # Her URL için kendi snapshot'larını al
                if selected_url in self.url_to_snapshots:
                    snapshots = self.url_to_snapshots[selected_url]
                    if snapshots:
                        # En yeni snapshot'ı seç
                        latest_snapshot = max(snapshots, key=lambda s: s['timestamp'])
                        
                        # Bu snapshot zaten eklenmiş mi kontrol et
                        already_added = False
                        for existing in self.selected_urls:
                            if (existing['original_url'] == latest_snapshot['original_url'] and 
                                existing['timestamp'] == latest_snapshot['timestamp']):
                                already_added = True
                                break
                        
                        if not already_added:
                            selected_urls.append(latest_snapshot)
                            print(f"✅ Snapshot eklendi: {latest_snapshot['archive_url']}")
                            print(f"📝 Orijinal URL: {latest_snapshot['original_url']}")
                            print(f"🕐 Timestamp: {latest_snapshot['timestamp']}")
                            print(f"🔗 Archive URL: {latest_snapshot['archive_url']}")
                        else:
                            print(f"⚠️ Snapshot zaten eklenmiş: {latest_snapshot['original_url']}")
                    else:
                        print(f"❌ URL için snapshot bulunamadı: {selected_url}")
                else:
                    print(f"❌ URL bulunamadı: {selected_url}")
            
            self.selected_urls.extend(selected_urls)
            print(f"✅ {len(selected_urls)} adet içerik seçildi. Toplam {len(self.selected_urls)} içerik hazır.")
            print(f"🎯 Ana pencereye dönüp 'Seçilenleri Çek' butonuna basabilirsiniz.")
            
            parent_window = self.parent()
            while parent_window and not hasattr(parent_window, 'domain_selectors'):
                parent_window = parent_window.parent()
            if parent_window:
                parent_window.setEnabled(True)
                parent_window.raise_()
                parent_window.activateWindow()
                print("✅ Ana pencere aktif edildi ve öne getirildi")
            self.accept()
        except Exception as e:
            print(f"❌ add_selected_items hatası: {e}")
            import traceback
            traceback.print_exc()
            try:
                parent_window = self.parent()
                while parent_window and not hasattr(parent_window, 'domain_selectors'):
                    parent_window = parent_window.parent()
                if parent_window:
                    parent_window.setEnabled(True)
                    parent_window.raise_()
                    parent_window.activateWindow()
            except:
                pass
            self.accept()

    def get_selected_urls(self):
        return self.selected_urls

    def copy_archive_url(self):
        url = self.snapshot_url_label.text()
        if url:
            QApplication.clipboard().setText(url)

    def update_add_selected_button_state(self):
        has_selection = len(self.url_list_widget.selectedItems()) > 0
        self.add_selected_button.setEnabled(has_selection)
        
        # Parent window'dan gelişmiş ayarları al
        parent_window = self.parent()
        while parent_window and not hasattr(parent_window, 'advanced_category_detection'):
            parent_window = parent_window.parent()
        
        # Kategori butonu: URL seçili VE kategori tespiti açık olmalı
        category_enabled = has_selection and parent_window and getattr(parent_window, 'advanced_category_detection', False)
        self.category_selector_button.setEnabled(category_enabled)
        
        # Etiket butonu: URL seçili VE etiket tespiti açık olmalı
        tag_enabled = has_selection and parent_window and getattr(parent_window, 'advanced_tag_detection', False)
        self.tag_selector_button.setEnabled(tag_enabled)
    
    def open_category_selector(self):
        """Kategori seçim modunu açar"""
        selected_items = self.url_list_widget.selectedItems()
        if not selected_items:
            return
        
        selected_url = selected_items[0].data(Qt.UserRole)
        snapshots = self.url_to_snapshots[selected_url]
        if snapshots:
            # En yeni snapshot'ın archive URL'sini kullan
            latest_snapshot = max(snapshots, key=lambda s: s['timestamp'])
            archive_url = latest_snapshot['archive_url']
            
            # Ana pencereyi disable et
            self.setEnabled(False)
            
            # Selector dialog'u doğrudan aç
            # Ana pencereyi bul
            parent_window = self.parent()
            while parent_window and not hasattr(parent_window, 'url_selections'):
                parent_window = parent_window.parent()
            
            dialog = FixedSelectorDialog(archive_url, mode="category", parent=parent_window)  # Ana pencereyi parent olarak ver
            dialog.setModal(False)  # Non-modal yap
            dialog.finished.connect(lambda result: self.on_selector_dialog_finished(result))
            dialog.show()
    
    def open_tag_selector(self):
        """Etiket seçim modunu açar"""
        selected_items = self.url_list_widget.selectedItems()
        if not selected_items:
            return
        
        selected_url = selected_items[0].data(Qt.UserRole)
        snapshots = self.url_to_snapshots[selected_url]
        if snapshots:
            # En yeni snapshot'ın archive URL'sini kullan
            latest_snapshot = max(snapshots, key=lambda s: s['timestamp'])
            archive_url = latest_snapshot['archive_url']
            
            # Ana pencereyi disable et
            self.setEnabled(False)
            
            # Selector dialog'u doğrudan aç
            # Ana pencereyi bul
            parent_window = self.parent()
            while parent_window and not hasattr(parent_window, 'url_selections'):
                parent_window = parent_window.parent()
            
            dialog = FixedSelectorDialog(archive_url, mode="tag", parent=parent_window)  # Ana pencereyi parent olarak ver
            dialog.setModal(False)  # Non-modal yap
            dialog.finished.connect(lambda result: self.on_selector_dialog_finished(result))
            dialog.show()

    def start_auto_detection(self):
        """Otomatik kategori/etiket tespiti başlatır"""
        try:
            # URL sayısını kontrol et
            if not self.url_to_snapshots:
                self.auto_detect_progress.setText("❌ İşlenecek URL bulunamadı!")
                return
            
            total_urls = len(self.url_to_snapshots)
            self.auto_detect_progress.setText(f"📊 {total_urls} URL için tespit başlatılıyor...")
            
            self.auto_detect_button.setEnabled(False)
            self.auto_detect_button.setText("🔍 Akıllı Tespit Ediliyor...")
            
            # Tespit thread'ini başlat
            self.auto_detect_thread = AutoDetectionThread(self.url_to_snapshots, self.parent())
            self.auto_detect_thread.progress.connect(self.update_auto_detect_progress)
            self.auto_detect_thread.finished.connect(self.auto_detection_finished)
            self.auto_detect_thread.start()
            
        except Exception as e:
            self.auto_detect_progress.setText(f"Hata: {str(e)}")
            self.auto_detect_button.setEnabled(True)
            self.auto_detect_button.setText("🔍 Akıllı Kategori/Etiket Tespit Et")
    
    def update_auto_detect_progress(self, message):
        """Otomatik tespit ilerlemesini günceller"""
        self.auto_detect_progress.setText(message)
    
    def auto_detection_finished(self):
        """Otomatik tespit tamamlandığında çağrılır"""
        self.auto_detect_button.setEnabled(True)
        self.auto_detect_button.setText("🔍 Otomatik Kategori/Etiket Tespit Et")
        self.auto_detect_progress.setText("✅ Akıllı tespit tamamlandı!")
        
        # URL listesini yenile
        self.populate_url_list()
    
    def on_selector_dialog_finished(self, result):
        """Selector dialog kapatıldığında çağrılır"""
        try:
            # Ana pencereyi tekrar enable et
            self.setEnabled(True)
            
            # Detaylı debug mesajları
            if result == 1:  # Accepted (Kaydet)
                print("✅ Selector dialog KAYDET ile kapatıldı, ana pencere tekrar aktif")
            elif result == 0:  # Rejected (İptal)
                print("❌ Selector dialog İPTAL ile kapatıldı, ana pencere tekrar aktif")
            else:
                print(f"⚠️ Selector dialog {result} ile kapatıldı, ana pencere tekrar aktif")
            
            # Butonların durumunu kontrol et
            print(f"🔍 Kategori butonu aktif: {self.category_selector_button.isEnabled()}")
            print(f"🔍 Etiket butonu aktif: {self.tag_selector_button.isEnabled()}")
            print(f"🔍 Ana pencere aktif: {self.isEnabled()}")
            
            # URL listesini yenile (selector sayılarını göstermek için)
            self.populate_url_list()  # Bu pencereyi yenile
            
            # Pencereyi öne getir
            self.raise_()
            self.activateWindow()
            
        except Exception as e:
            print(f"❌ on_selector_dialog_finished hatası: {e}")
            # Hata olsa bile ana pencereyi aktif et
            self.setEnabled(True)

    def closeEvent(self, event):
        """Dialog kapatılırken temizlik yapar"""
        # Tüm thread'leri ve timer'ları temizle
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
        
        # Web view'ları temizle
        if hasattr(self, 'web_view'):
            self.web_view.deleteLater()
        
        event.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        w, h = 1100, 750
        w = min(w, screen_rect.width() - 40)
        h = min(h, screen_rect.height() - 80)
        self.resize(w, h)
        self.setMinimumSize(900, 600)
        self.setMaximumSize(screen_rect.width(), screen_rect.height())
        self.show()  # Pencereyi göster ki frameGeometry doğru çalışsın
        frame_geom = self.frameGeometry()
        center_point = screen_rect.center()
        frame_geom.setWidth(w)
        frame_geom.setHeight(h)
        frame_geom.moveCenter(center_point)
        self.move(frame_geom.topLeft())
        self.live_progress_bar = None  # Her durumda tanımlı
        # --- stats sözlüğü en başta tanımlanıyor ---
        self.stats = {
            'total_snapshots': 0,
            'processed_snapshots': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'start_time': None
        }
        self.setup_ui()
        
        # Progress animasyonu için
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.animate_progress)
        self.progress_dots = 0
        self.base_message = ""
        
        # Thread'ler
        self.discovery_thread = None
        self.extraction_thread = None
        self.analysis_thread = None
        
        # Veri
        self.extracted_content = []
        self.available_dates = []
        
        self.discovered_categories = {}
        self.final_extracted_data = [] # İçerik çekildikten sonraki tam veriyi tutar
        
        # Selector storage - global kategori ve etiket selector'larını saklar (domain fark etmez)
        self.global_selectors = {'category': [], 'tag': []}  # Sadece HTML etiketleri
        
        # Domain bazlı selector'ları sakla
        self.domain_selectors = {}  # {domain: {'category': [seçilenler], 'tag': [seçilenler]}}
        
        # URL bazlı kategori/etiket seçimlerini sakla
        self.url_selections = {}  # {url: {'category': [seçilenler], 'tag': [seçilenler]}}
        
        # --- YENİ: Otomatik tespit cache'i ---
        self.detected_categories_cache = {}  # {url: {'categories': [], 'tags': []}}
        # --- SON YENİ ---
        
        # Açık URL seçim pencerelerini takip etmek için
        self.url_selection_windows = []
        
        # Thread ID'leri için
        self.current_analysis_id = 0
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #4ecdc4;
                border-radius: 6px;
                text-align: center;
                background-color: #2c3e50;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4ecdc4;
                border-radius: 4px;
            }
        """)
        
        # İstatistik değişkenleri
        self.stats = {
            'total_snapshots': 0,
            'processed_snapshots': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'start_time': None
        }
    
    def setup_ui(self):
        """UI'yi kurar"""
        self.setWindowTitle("Arşiv Radar - Professional Archive.org Discovery Tool")
        self.setGeometry(100, 100, 1200, 700)  # Daha büyük ve profesyonel
        
        # Program simgesi
        try:
            from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QLinearGradient
            pixmap = QPixmap(48, 48)
            pixmap.fill(QColor(0, 0, 0, 0))  # Transparent
            painter = QPainter(pixmap)
            
            # Gradient arka plan
            gradient = QLinearGradient(0, 0, 48, 48)
            gradient.setColorAt(0, QColor(78, 205, 196))
            gradient.setColorAt(1, QColor(52, 73, 94))
            painter.fillRect(pixmap.rect(), gradient)
            
            # İkon
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            painter.drawText(pixmap.rect(), Qt.AlignCenter, "🔍")
            painter.end()
            self.setWindowIcon(QIcon(pixmap))
        except:
            pass
        
        # Ana widget
        central_widget = QWidget()
        # Ana layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Başlık alanı
        title_container = QWidget()
        title_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2c3e50, stop:1 #34495e);
                border-radius: 12px;
                padding: 8px 20px 8px 20px; /* Yüksekliği ciddi şekilde azalttık */
                margin-bottom: 8px;
            }
        """)
        title_layout = QVBoxLayout(title_container)
        title_layout.setSpacing(2)
        # Başlık
        title_label = QLabel("Archive Insight Pro")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 26px;
                font-weight: bold;
                color: #4ecdc4;
                margin: 0;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(title_label)
        # Alt başlık
        subtitle_label = QLabel("Intelligent Web Archive Content Discovery & Extraction Suite")
        subtitle_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #bdc3c7;
                margin: 0;
                font-style: italic;
            }
        """)
        subtitle_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(subtitle_label)
        main_layout.addWidget(title_container)
        
        # Ana içerik alanı - yan yana
        content_layout = QHBoxLayout()
        content_layout.setSpacing(25)
        
        # SOL PANEL - Kontroller
        left_panel = QWidget()
        left_panel.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        left_panel.setFixedWidth(420)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(20)
        
        # Domain girişi
        domain_group = QGroupBox("🌐 Domain Analizi")
        domain_group.setAlignment(Qt.AlignLeft)
        domain_group.setFixedWidth(420)
        domain_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 15px;
                border: 2px solid #34495e;
                border-radius: 10px;
                margin-top: 10px;
                padding: 15px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #34495e, stop:1 #2c3e50);
                color: #4ecdc4;
                text-align: left;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 0px;
                padding: 0 10px 0 10px;
                color: #4ecdc4;
                background-color: #2c3e50;
                font-size: 15px;
                text-align: left;
            }
        """)
        
        domain_layout = QVBoxLayout(domain_group)
        domain_layout.setSpacing(15)
        
        # Domain input
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("örnek: example.com (www olmadan)")
        self.domain_input.setStyleSheet("""
            QLineEdit {
                padding: 15px;
                border: 2px solid #34495e;
                border-radius: 8px;
                background-color: #34495e;
                color: white;
                font-size: 15px;
                font-weight: 500;
            }
            QLineEdit:focus {
                border-color: #4ecdc4;
                background-color: #3a5a6b;
            }
            QLineEdit::placeholder {
                color: #95a5a6;
                font-style: italic;
            }
        """)
        self.domain_input.returnPressed.connect(self.analyze_domain)
        domain_layout.addWidget(self.domain_input)
        
        # Analiz butonu
        self.analyze_button = QPushButton("🔍 DOMAIN ANALİZ ET")
        self.analyze_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #e74c3c, stop:1 #c0392b);
                color: white;
                border: none;
                padding: 18px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 10px;
                margin: 10px 0;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #c0392b, stop:1 #a93226);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #a93226, stop:1 #922b21);
            }
            QPushButton:disabled {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #7f8c8d, stop:1 #6c7b7d);
            }
        """)
        self.analyze_button.clicked.connect(self.analyze_domain)
        domain_layout.addWidget(self.analyze_button)
        
        # Tarih analizi sonuçları
        self.date_analysis_widget = QWidget()
        self.date_analysis_widget.setVisible(False)
        self.date_analysis_widget.setMaximumWidth(400)
        date_analysis_layout = QVBoxLayout(self.date_analysis_widget)
        
        self.date_analysis_label = QLabel("")
        self.date_analysis_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #34495e, stop:1 #2c3e50);
                padding: 15px;
                border-radius: 8px;
                border: 2px solid #f39c12;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        self.date_analysis_label.setWordWrap(True)
        self.date_analysis_label.setMaximumWidth(400)
        date_analysis_layout.addWidget(self.date_analysis_label)
        
        domain_layout.addWidget(self.date_analysis_widget)
        
        # Tarih seçimi
        self.date_selection_widget = QWidget()
        self.date_selection_widget.setVisible(False)
        date_selection_layout = QVBoxLayout(self.date_selection_widget)
        
        date_group = QGroupBox("📅 Tarih Aralığı")
        date_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #34495e;
                border-radius: 10px;
                margin-top: 15px;
                padding: 20px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #34495e, stop:1 #2c3e50);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px 0 10px;
                color: #4ecdc4;
                background-color: #2c3e50;
                font-size: 16px;
            }
        """)
        
        date_layout = QVBoxLayout(date_group)
        date_layout.setSpacing(15)
        
        # Checkbox'lar
        self.all_dates_checkbox = QCheckBox("📋 Tüm Tarihleri Tara")
        self.all_dates_checkbox.setStyleSheet("""
            QCheckBox {
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #4ecdc4;
                background-color: #2c3e50;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4ecdc4;
                background-color: #4ecdc4;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUw0LjUgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
            }
            QCheckBox:hover {
                background-color: rgba(78, 205, 196, 0.1);
                border-radius: 4px;
            }
        """)
        self.all_dates_checkbox.setChecked(True)
        self.all_dates_checkbox.toggled.connect(self.toggle_date_inputs)
        date_layout.addWidget(self.all_dates_checkbox)
        
        self.specific_dates_checkbox = QCheckBox("Belirli Tarih Aralığı")
        self.specific_dates_checkbox.setStyleSheet("""
            QCheckBox {
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #4ecdc4;
                background-color: #2c3e50;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4ecdc4;
                background-color: #4ecdc4;
                border-radius: 4px;
            }
        """)
        self.specific_dates_checkbox.toggled.connect(self.toggle_date_inputs)
        date_layout.addWidget(self.specific_dates_checkbox)
        
        # Tarih input'ları
        date_input_layout = QVBoxLayout()
        date_input_layout.setSpacing(12)
        # Başlangıç
        start_date_label = QLabel("Başlangıç:")
        start_date_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px; margin-bottom: 2px;")
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-6))
        self.start_date_edit.setStyleSheet("""
            QDateEdit {
                padding: 8px;
                border: 2px solid #34495e;
                border-radius: 6px;
                background-color: #34495e;
                color: white;
                font-size: 13px;
                margin-bottom: 8px;
            }
        """)
        self.start_date_edit.setEnabled(False)
        date_input_layout.addWidget(start_date_label)
        date_input_layout.addWidget(self.start_date_edit)
        # Bitiş
        end_date_label = QLabel("Bitiş:")
        end_date_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px; margin-bottom: 2px;")
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setStyleSheet("""
            QDateEdit {
                padding: 8px;
                border: 2px solid #34495e;
                border-radius: 6px;
                background-color: #34495e;
                color: white;
                font-size: 13px;
                margin-bottom: 8px;
            }
        """)
        self.end_date_edit.setEnabled(False)
        date_input_layout.addWidget(end_date_label)
        date_input_layout.addWidget(self.end_date_edit)
        date_layout.addLayout(date_input_layout)
        
        date_selection_layout.addWidget(date_group)
        domain_layout.addWidget(self.date_selection_widget)
        
        left_layout.addWidget(domain_group)
        
        # Progress label - iki kutu arasına taşındı
        self.progress_label = QLabel("Domain girin ve analiz edin    ")
        self.progress_label.setWordWrap(True)
        self.progress_label.setStyleSheet("""
            QLabel {
                color: #4ecdc4;
                font-weight: bold;
                padding: 18px 20px;
                background-color: #23272e;
                border-radius: 10px;
                border: 2px solid #4ecdc4;
                font-size: 10px;
                min-width: 350px;
                max-width: 600px;
            }
        """)
        self.progress_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.progress_label)
        
        # Timeout Ayarları
        timeout_group = QGroupBox("⚡ Gelişmiş Ayarlar")
        timeout_group.setAlignment(Qt.AlignLeft)
        timeout_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #34495e;
                border-radius: 10px;
                margin-top: 15px;
                padding: 20px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #34495e, stop:1 #2c3e50);
                color: #4ecdc4;
                text-align: left;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 0px;
                padding: 0 10px 0 10px;
                color: #4ecdc4;
                background-color: #2c3e50;
                font-size: 16px;
                text-align: left;
            }
            QSpinBox {
                background-color: #23272e;
                color: #4ecdc4;
                border: 2px solid #4ecdc4;
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
                padding: 6px 12px;
                min-width: 80px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0;
                height: 0;
                border: none;
                background: transparent;
            }
        """)
        timeout_layout = QGridLayout(timeout_group)
        timeout_layout.setHorizontalSpacing(12)
        timeout_layout.setVerticalSpacing(16)
        # API Timeout
        self.api_timeout_spin = QSpinBox()
        self.api_timeout_spin.setRange(10, 300)
        self.api_timeout_spin.setValue(90)  # Default: 90 saniye (Archive.org için güvenli)
        api_label = QLabel("API Timeout")
        api_info = QLabel("ℹ️")
        api_info.setToolTip("Archive.org API'sından veri çekerken beklenen maksimum süre (saniye). Çok düşük timeout veya çok yüksek retry, arşivden ban yemenize veya yavaşlamaya sebep olabilir.")
        api_info.setStyleSheet("color: #4ecdc4; font-size: 16px; margin-left: 8px; margin-right: 0px; background: transparent;")
        timeout_layout.addWidget(api_label, 0, 0)
        timeout_layout.addWidget(self.api_timeout_spin, 0, 1)
        timeout_layout.addWidget(api_info, 0, 2)
        # Content Timeout
        self.content_timeout_spin = QSpinBox()
        self.content_timeout_spin.setRange(10, 180)
        self.content_timeout_spin.setValue(45)  # Default: 45 saniye (Archive.org için güvenli)
        content_label = QLabel("İçerik Timeout")
        content_info = QLabel("ℹ️")
        content_info.setToolTip("Bir içeriği çekerken beklenen maksimum süre (saniye). Çok düşük timeout veya çok yüksek retry, arşivden ban yemenize veya yavaşlamaya sebep olabilir.")
        content_info.setStyleSheet("color: #4ecdc4; font-size: 16px; margin-left: 8px; margin-right: 0px; background: transparent;")
        timeout_layout.addWidget(content_label, 1, 0)
        timeout_layout.addWidget(self.content_timeout_spin, 1, 1)
        timeout_layout.addWidget(content_info, 1, 2)
        # Retry
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(1, 15)
        self.retry_spin.setValue(5)  # Default: 5 deneme (Archive.org için güvenli)
        retry_label = QLabel("Retry")
        retry_info = QLabel("ℹ️")
        retry_info.setToolTip("Başarısız olursa kaç kez tekrar denensin? Çok düşük timeout veya çok yüksek retry, arşivden ban yemenize veya yavaşlamaya sebep olabilir.")
        retry_info.setStyleSheet("color: #4ecdc4; font-size: 16px; margin-left: 8px; margin-right: 0px; background: transparent;")
        timeout_layout.addWidget(retry_label, 2, 0)
        timeout_layout.addWidget(self.retry_spin, 2, 1)
        timeout_layout.addWidget(retry_info, 2, 2)
        # İstekler Arası Bekleme (saniye)
        self.request_delay_spin = QSpinBox()
        self.request_delay_spin.setRange(1, 30)
        self.request_delay_spin.setValue(2)  # Default: 2 saniye (Archive.org için önerilen)
        delay_label = QLabel("Bekleme (saniye)")
        delay_label.setWordWrap(True)
        delay_info = QLabel("ℹ️")
        delay_info.setToolTip("Her içerik isteği arasında bekleme süresi (saniye). Çok düşük ayarlarsanız IP'niz geçici olarak engellenebilir. 3-5 saniye önerilir.")
        delay_info.setStyleSheet("color: #4ecdc4; font-size: 16px; margin-left: 8px; margin-right: 0px; background: transparent;")
        timeout_layout.addWidget(delay_label, 3, 0)
        timeout_layout.addWidget(self.request_delay_spin, 3, 1)
        timeout_layout.addWidget(delay_info, 3, 2)
        # Default Ayarları Yükle butonu
        self.reset_defaults_button = QPushButton("Default Ayarları Yükle")
        self.reset_defaults_button.setText("Varsayılan")
        self.reset_defaults_button.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; border-radius: 6px; padding: 8px; margin-top: 10px;")
        self.reset_defaults_button.clicked.connect(self.set_default_timeouts)
        timeout_layout.addWidget(self.reset_defaults_button, 4, 0, 1, 3)
        
        # --- Gelişmiş Kategori/Etiket Tespiti Switch'leri ---
        self.advanced_category_detection = True
        self.advanced_tag_detection = True
        self.auto_category_tag_detection = True  # Yeni: Otomatik tespit switch'i
        
        # Otomatik Kategori/Etiket Tespiti Checkbox
        auto_detection_layout = QHBoxLayout()
        self.auto_detection_checkbox = QCheckBox("Otomatik Kategori/Etiket Tespiti")
        self.auto_detection_checkbox.setChecked(True)  # Default açık
        self.auto_detection_checkbox.stateChanged.connect(self.on_auto_detection_checkbox_changed)
        # Checkbox genişliğini artır
        self.auto_detection_checkbox.setMinimumWidth(300)
        self.auto_detection_checkbox.setStyleSheet("QCheckBox { font-size: 12px; }")
        auto_detection_layout.addWidget(self.auto_detection_checkbox)
        
        auto_detection_info = QLabel("ℹ️")
        auto_detection_info.setToolTip("Açık: Önce selector ile seçilmiş varsa onları kullan, yoksa otomatik bul.\nKapalı: Sadece selector ile seçilmiş olanları kullan.")
        auto_detection_info.setStyleSheet("color: #4ecdc4; font-size: 16px; margin-left: 5px; background: transparent;")
        auto_detection_layout.addWidget(auto_detection_info)
        timeout_layout.addLayout(auto_detection_layout, 5, 0, 1, 2)
        
        # Switch'leri checkbox'ın altına taşı
        # Kategori Tespiti Switch (QSwitch)
        category_switch_layout = QHBoxLayout()
        self.advanced_category_switch = QSwitch(label="Kategori Tespiti")
        self.advanced_category_switch.setChecked(True)
        self.advanced_category_switch.clicked.connect(self.on_category_switch_changed)
        category_switch_layout.addWidget(self.advanced_category_switch)
        
        category_info = QLabel("ℹ️")
        category_info.setToolTip("Açık: Kategori seçimi için sayfadan element seçmeniz gerekir.\nKapalı: Kategori çıkarımı yapılmaz.")
        category_info.setStyleSheet("color: #4ecdc4; font-size: 16px; margin-left: 5px; background: transparent;")
        category_switch_layout.addWidget(category_info)
        timeout_layout.addLayout(category_switch_layout, 6, 0, 1, 2)
        
        # Etiket Tespiti Switch (QSwitch)
        tag_switch_layout = QHBoxLayout()
        self.advanced_tag_switch = QSwitch(label="Etiket Tespiti")
        self.advanced_tag_switch.setChecked(True)
        self.advanced_tag_switch.clicked.connect(self.on_tag_switch_changed)
        tag_switch_layout.addWidget(self.advanced_tag_switch)
        
        tag_info = QLabel("ℹ️")
        tag_info.setToolTip("Açık: Etiket seçimi için sayfadan element seçmeniz gerekir.\nKapalı: Etiket çıkarımı yapılmaz.")
        tag_info.setStyleSheet("color: #4ecdc4; font-size: 16px; margin-left: 5px; background: transparent;")
        tag_switch_layout.addWidget(tag_info)
        timeout_layout.addLayout(tag_switch_layout, 7, 0, 1, 2)
        
        # Kategori/Etiket Atama Seçeneği
        # cat_tag_label = QLabel("Kategori/Etiket Atama")
        # cat_tag_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px; margin-top: 10px;")
        # timeout_layout.addWidget(cat_tag_label, 5, 0)
        # cat_tag_info = QLabel("ℹ️")
        # cat_tag_info.setToolTip("Python: Akıllı kategori gruplama ve yazıya özel etiketler. Kapalı: Sadece temel kategori/etiket çıkarma.")
        # cat_tag_info.setStyleSheet("color: #4ecdc4; font-size: 16px; margin-left: 8px; margin-right: 0px; background: transparent;")
        # timeout_layout.addWidget(cat_tag_info, 5, 2)
        
        # ... mevcut kod ...
        # Başarısız içerikler listesi
        self.failed_urls_group = QGroupBox("❌ Başarısız İçerikler")
        self.failed_urls_group.setVisible(False)
        failed_layout = QVBoxLayout(self.failed_urls_group)
        self.failed_urls_list = QListWidget()
        self.failed_urls_list.setSelectionMode(QAbstractItemView.MultiSelection)
        failed_layout.addWidget(self.failed_urls_list)
        self.retry_failed_button = QPushButton("Seçili Başarısızları Tekrar Çek")
        self.retry_failed_button.setStyleSheet("background-color:#e67e22;color:white;font-weight:bold;border-radius:6px;padding:8px;")
        self.retry_failed_button.clicked.connect(self.retry_failed_urls)
        failed_layout.addWidget(self.retry_failed_button)
        # ... mevcut kod ...
        left_layout.addWidget(timeout_group)
        left_layout.addWidget(self.failed_urls_group)
        
        # Keşif butonu
        self.discover_button = QPushButton("Keşfet")
        self.discover_button.setStyleSheet("""
            QPushButton {
                background-color: #4ecdc4;
                color: white;
                border: none;
                padding: 15px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #45b7af;
            }
            QPushButton:pressed {
                background-color: #3da89f;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
            }
        """)
        self.discover_button.clicked.connect(self.start_discovery)
        self.discover_button.setEnabled(False)
        left_layout.addWidget(self.discover_button)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #4ecdc4;
                border-radius: 6px;
                text-align: center;
                background-color: #2c3e50;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4ecdc4;
                border-radius: 4px;
            }
        """)
        left_layout.addWidget(self.progress_bar)
        
        left_layout.addStretch()
        
        # SAĞ PANEL - Sonuçlar
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(15)
        
        # Kategoriler
        self.category_widget = QWidget()
        self.category_widget.setVisible(False)  # Başlangıçta gizli
        category_layout = QVBoxLayout(self.category_widget)
        category_title = QLabel("Bulunan Kategoriler")
        category_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #4ecdc4;
                margin: 10px 0;
            }
        """)
        category_title.setAlignment(Qt.AlignCenter)
        category_layout.addWidget(category_title)
        self.category_grid = QGridLayout()
        category_layout.addLayout(self.category_grid)
        # right_layout.addWidget(self.category_widget)  # BAŞLANGIÇTA EKLENMİYOR
        self.right_panel = right_panel  # referans kaybolmasın diye
        
        right_layout.addWidget(self.category_widget)
        
        # Seçilen içerikler
        selected_group = QGroupBox("Seçilen İçerikler")
        selected_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #34495e;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px 10px 10px 10px;
                background-color: #2c3e50;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                color: #4ecdc4;
                background-color: #2c3e50;
            }
        """)
        selected_layout = QVBoxLayout(selected_group)
        selected_layout.setSpacing(8)
        self.selected_count_label = QLabel("Henüz içerik seçilmedi")
        self.selected_count_label.setStyleSheet("color: #4ecdc4; font-weight: bold;")
        selected_layout.addWidget(self.selected_count_label)
        button_layout = QHBoxLayout()
        self.extract_button = QPushButton("İçerikleri Çek")
        self.extract_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
            }
        """)
        self.extract_button.setEnabled(False)
        self.extract_button.clicked.connect(self.toggle_extraction)
        self.export_button = QPushButton("WordPress'e Aktar")
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
            }
        """)
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_to_wordpress)
        button_layout.addWidget(self.extract_button)
        button_layout.addWidget(self.export_button)
        selected_layout.addLayout(button_layout)
        right_layout.addWidget(selected_group)
        
        # Canlı Bilgi Ekranı (Sağ alt)
        log_group = QGroupBox("📊 Canlı Bilgi Ekranı")
        log_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #34495e;
                border-radius: 8px;
                margin-top: 8px;
                padding: 8px 8px 8px 8px;
                background-color: #2c3e50;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                color: #4ecdc4;
                background-color: #2c3e50;
            }
        """)
        log_layout = QVBoxLayout(log_group)
        log_layout.setSpacing(6)
        clear_log_button = QPushButton("🗑️ Logları Temizle")
        clear_log_button.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                padding: 7px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """)
        clear_log_button.clicked.connect(self.clear_log_display)
        log_layout.addWidget(clear_log_button)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #00ff00;
                border: 2px solid #4ecdc4;
                border-radius: 6px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                padding: 7px;
            }
        """)
        self.log_display.setMinimumHeight(240)
        self.log_display.setMaximumHeight(360)
        log_layout.addWidget(self.log_display)
        
        # İstatistikler
        stats_group = QGroupBox("📈 İstatistikler")
        stats_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #4ecdc4;
                border-radius: 10px;
                background-color: #2c3e50;
                margin-top: 10px;
                padding: 8px 0 8px 0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 0;
                right: 0;
                padding: 0 8px 0 8px;
                color: #2de3c4;
                background-color: #2c3e50;
                font-size: 16px;
                text-align: center;
            }
        """)
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setContentsMargins(8, 8, 8, 8)
        stats_layout.setSpacing(0)
        # --- YENİ: Yan yana istatistikler için QHBoxLayout ---
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(18)
        self.stats_row.setAlignment(Qt.AlignHCenter)
        self.stat_time = QLabel("⏱️ Süre: 00:00:00")
        self.stat_total = QLabel("📊 Toplam: 0")
        self.stat_processed = QLabel("🔄 İşlenen: 0")
        self.stat_success = QLabel("✅ Başarılı: 0")
        self.stat_failed = QLabel("❌ Başarısız: 0")
        for lbl in [self.stat_time, self.stat_total, self.stat_processed, self.stat_success, self.stat_failed]:
            lbl.setStyleSheet("color: #ecf0f1; font-size: 13px; font-weight: bold; background: transparent;")
            lbl.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.stats_row.addWidget(lbl)
        stats_layout.addLayout(self.stats_row)
        stats_group.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        right_layout.addWidget(stats_group)
        # --- Güncelleme fonksiyonu ---
        def update_stats_row():
            elapsed = "00:00:00"
            if self.stats['start_time']:
                elapsed = str(datetime.now() - self.stats['start_time']).split('.')[0]
            self.stat_time.setText(f"⏱️ Süre: {elapsed}")
            self.stat_total.setText(f"📊 Toplam: {self.stats.get('total_snapshots', 0)}")
            self.stat_processed.setText(f"🔄 İşlenen: {self.stats.get('processed_snapshots', 0)}")
            self.stat_success.setText(f"✅ Başarılı: {self.stats.get('successful_extractions', 0)}")
            self.stat_failed.setText(f"❌ Başarısız: {self.stats.get('failed_extractions', 0)}")
        self.update_stats_row = update_stats_row
        self.update_stats_row()
        # --- YENİ: Çekilen içeriklerin listesi ayrı kutuda ve numaralı ---
        self.extracted_content_group = QGroupBox("Çekilen İçerikler")
        self.extracted_content_group.setStyleSheet("""
            QGroupBox {
                border: 2.5px solid #27ae60;
                border-radius: 16px;
                background-color: #23272e;
                margin-top: 12px;
                padding: 18px 18px 18px 18px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 18px;
                padding: 0 12px 0 12px;
                color: #27ae60;
                background-color: #23272e;
                font-size: 18px;
                font-weight: bold;
                text-align: left;
            }
        """)
        extracted_content_layout = QVBoxLayout(self.extracted_content_group)
        extracted_content_layout.setSpacing(8)
        self.extracted_content_list = QListWidget()
        self.extracted_content_list.setStyleSheet("""
            QListWidget {
                background-color: #23272e;
                color: #4ecdc4;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                padding: 16px;
            }
            QListWidget::item {
                padding: 12px 10px;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background: #34495e;
                color: #fff;
            }
        """)
        self.extracted_content_list.setMinimumHeight(80)
        self.extracted_content_list.setMaximumHeight(200)
        extracted_content_layout.addWidget(self.extracted_content_list)
        self.extracted_content_list.clear()
        empty_item = QListWidgetItem("Henüz içerik çekilmedi.")
        empty_item.setTextAlignment(Qt.AlignHCenter)
        self.extracted_content_list.addItem(empty_item)
        right_layout.addWidget(self.extracted_content_group)
        
        # Log ve istatistik gruplarını ekle
        right_layout.addWidget(log_group)
        right_layout.addWidget(stats_group)
        
        # Ana layout'a panelleri ekle
        content_layout.addWidget(left_panel, 1)
        content_layout.addWidget(right_panel, 2)
        
        main_layout.addLayout(content_layout)
        
        # ScrollArea ile sarmala
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(central_widget)
        self.setCentralWidget(scroll)
        
        # Status bar
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #2c3e50;
                color: #4ecdc4;
                border-top: 1px solid #4ecdc4;
            }
        """)
        
        # Dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #34495e;
            }
            QWidget {
                background-color: #34495e;
                color: white;
            }
        """)
        
        # Progress bar (canlı bilgi ekranı altına)
        self.live_progress_bar = WaterProgressBar()
        self.live_progress_bar.setVisible(False)
        log_layout.addWidget(self.live_progress_bar)
    
    def toggle_date_inputs(self, checked):
        """Tarih input'larını etkinleştir/devre dışı bırak"""
        if self.sender() == self.all_dates_checkbox:
            if checked:
                self.specific_dates_checkbox.setChecked(False)
                self.start_date_edit.setEnabled(False)
                self.end_date_edit.setEnabled(False)
        elif self.sender() == self.specific_dates_checkbox:
            if checked:
                self.all_dates_checkbox.setChecked(False)
                self.start_date_edit.setEnabled(True)
                self.end_date_edit.setEnabled(True)
    
    def analyze_domain(self):
        """Domain'i analiz eder ve tarih aralığını bulur"""
        domain = self.domain_input.text().strip()
        if not domain:
            self.progress_label.setText("Lütfen bir domain girin!")
            self.add_log_message("Domain girilmedi!", "ERROR")
            return
        
        # Domain'i temizle
        if domain.startswith('http://'):
            domain = domain[7:]
        elif domain.startswith('https://'):
            domain = domain[8:]
        if domain.startswith('www.'):
            domain = domain[4:]
        
        self.add_log_message(f"Domain analizi başlatılıyor: {domain}", "INFO")
        self.reset_stats()
        self.stats['start_time'] = datetime.now()
        
        # Eski progress timer'ı durdur ve temizle
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
        
        # Eski thread'leri temizle (sadece kontrol et, zorla kapatma)
        if hasattr(self, 'discovery_thread') and self.discovery_thread and self.discovery_thread.isRunning():
            self.discovery_thread.quit()
        if hasattr(self, 'extraction_thread') and self.extraction_thread and self.extraction_thread.isRunning():
            self.extraction_thread.quit()
        if hasattr(self, 'analysis_thread') and self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.quit()
        
        # Eski verileri temizle
        self.extracted_content = []
        self.final_extracted_data = []
        self.discovered_categories = {}
        self.available_dates = []
        
        # UI'yi temizle
        self.category_widget.setVisible(False)
        self.extract_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.discover_button.setEnabled(False)
        self.selected_count_label.setText("Henüz içerik seçilmedi")
        
        # Tarih analiz widget'larını gizle
        self.date_analysis_widget.setVisible(False)
        self.date_selection_widget.setVisible(False)
        
        # Date analysis label'ı temizle
        self.date_analysis_label.setText("")
        
        # Analiz butonunu devre dışı bırak
        self.analyze_button.setEnabled(False)
        self.analyze_button.setText("Analiz Ediliyor...")
        
        # Domain analysis thread'ini başlat
        self.current_analysis_id += 1
        self.analysis_thread = DomainAnalysisThread(domain, self.current_analysis_id)
        self.analysis_thread.progress.connect(self.update_progress_label)
        self.analysis_thread.analysis_complete.connect(self.domain_analysis_finished)
        self.analysis_thread.error.connect(self.domain_analysis_error)
        self.analysis_thread.start()
    
    def start_discovery(self):
        """Keşif işlemini başlatır"""
        if not self.available_dates:
            self.progress_label.setText("Önce domain analizi yapın!")
            self.add_log_message("Domain analizi yapılmadı!", "ERROR")
            return
        
        self.add_log_message("İçerik keşfi başlatılıyor...", "INFO")
        
        # Tarih aralığını belirle
        start_date = None
        end_date = None
        
        if self.specific_dates_checkbox.isChecked():
            start_date = self.start_date_edit.date().toPython()
            end_date = self.end_date_edit.date().toPython()
            self.add_log_message(f"Tarih aralığı: {start_date} - {end_date}", "INFO")
        else:
            self.add_log_message("Tüm tarihler taranacak", "INFO")
        
        # Timeout ayarlarını al
        timeout_settings = self.get_timeout_settings()
        self.add_log_message(f"Timeout ayarları: API={timeout_settings['api_timeout']}s, Retry={timeout_settings['retry_count']}x", "INFO")
        
        # Keşif butonunu devre dışı bırak
        self.discover_button.setEnabled(False)
        self.discover_button.setText("Keşif Yapılıyor...")
        
        # Discovery thread'ini başlat
        self.discovery_thread = ArchiveDiscovery(self.domain_input.text().strip(), start_date, end_date, timeout_settings)
        self.discovery_thread.progress.connect(self.update_progress_label)
        self.discovery_thread.discovery_complete.connect(self.discovery_finished)
        self.discovery_thread.error.connect(self.discovery_error)
        self.discovery_thread.start()
    
    def toggle_extraction(self):
        if hasattr(self, 'extraction_thread') and self.extraction_thread and self.extraction_thread.isRunning():
            # Durdur
            self.extraction_thread.stop_requested = True
            self.extract_button.setText("Durduruluyor...")
            self.extract_button.setEnabled(False)
        else:
            self.start_extraction()
            self.extract_button.setText("Durdur")
            self.extract_button.setEnabled(True)

    def start_extraction(self, url_infos=None):
        if url_infos is None:
            url_infos = self.extracted_content
        if not url_infos:
            QMessageBox.information(self, "Bilgi", "Çekilecek içerik seçilmedi.")
            return
        self.extract_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.progress_label.setText(f"Toplam 0/{len(url_infos)} içerik çekiliyor")
        self.add_log_message(f"Toplam {len(url_infos)} içerik çekilecek.", "INFO")
        timeout_settings = self.get_timeout_settings()
        self.extraction_thread = ContentExtractor(url_infos, timeout_settings=timeout_settings, mainwindow=self)
        self.extraction_thread.progress.connect(self.update_progress_label)
        self.extraction_thread.content_extracted.connect(self.content_extracted)
        self.extraction_thread.extraction_complete.connect(self.extraction_finished)
        self.extraction_thread.error.connect(self.extraction_error)
        self.extraction_thread.start()
        if self.live_progress_bar:
            self.live_progress_bar.setVisible(True)
            self.live_progress_bar.setValue(0)
            self.live_progress_bar.setMaximum(len(url_infos))
    
    def update_progress_label(self, message):
        # Dinamik içerik çekme durumu
        if message.startswith("Çekiliyor ("):
            import re
            match = re.match(r"Çekiliyor \\((\\d+)/(\\d+)\\):", message)
            if match:
                current = int(match.group(1))
                total = int(match.group(2))
                self.progress_label.setText(f"Toplam {current}/{total} içerik çekiliyor")
                return  # Bu mesajı progress label'da göster, log'da değil
        # Başlangıç mesajını da yakala
        elif message.startswith("Toplam 0/"):
            self.progress_label.setText(message)
            return  # Bu mesajı progress label'da göster, log'da değil
        
        # Diğer mesajlar için normal akış
        self.progress_label.setText(message)
        # Başarısız içerik logu
        if message.startswith("❌ Başarısız:"):
            self.add_log_message(message, "ERROR")
        
        # Log mesajı tipini belirle
        if "hata" in message.lower() or "error" in message.lower():
            message_type = "ERROR"
        elif "başarılı" in message.lower() or "tamamlandı" in message.lower():
            message_type = "SUCCESS"
        elif "uyarı" in message.lower() or "warning" in message.lower():
            message_type = "WARNING"
        else:
            message_type = "INFO"
        
        # Log ekranına ekle
        self.add_log_message(message, message_type)
        
        # İstatistikleri güncelle
        if "snapshot" in message.lower():
            if "toplam" in message.lower():
                # Toplam snapshot sayısını çıkar
                import re
                match = re.search(r'(\d+)', message)
                if match:
                    self.update_stats(total_snapshots=int(match.group(1)))
            elif "işleniyor" in message.lower():
                # İşlenen snapshot sayısını çıkar
                import re
                match = re.search(r'(\d+)/(\d+)', message)
                if match:
                    self.update_stats(processed_snapshots=int(match.group(1)))
        
        # Progress animasyonu
        if not hasattr(self, 'progress_timer') or not self.progress_timer.isActive():
            self.progress_timer.start(500)
            self.base_message = message
            self.progress_dots = 0
    
    def animate_progress(self):
        """Progress mesajına nokta animasyonu ekler"""
        self.progress_dots = (self.progress_dots + 1) % 4
        dots = '.' * self.progress_dots
        dots = dots.ljust(4)  # 4 karakterlik sabit genişlik
        self.progress_label.setText(self.base_message + dots)
    
    def discovery_finished(self, result):
        """Keşif tamamlandığında çağrılır"""
        # Timer'ı durdur
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
        self.discover_button.setEnabled(True)
        self.extract_button.setEnabled(False)
        # --- YENİ: Sonuçları unpack et ---
        if isinstance(result, tuple):
            categories, total_snapshots_all, total_snapshots_used = result
        else:
            categories = result
            total_snapshots_all = None
            total_snapshots_used = None
        # --- SON YENİ ---
        
        # --- YENİ: Otomatik tespit cache'ini mainwindow'a aktar ---
        if hasattr(self.discovery_thread, 'detected_categories_cache'):
            self.detected_categories_cache = self.discovery_thread.detected_categories_cache
            self.add_log_message(f"🎯 {len(self.detected_categories_cache)} URL'de otomatik kategori/etiket tespit edildi", "SUCCESS")
        # --- SON YENİ ---
        
        # Toplam snapshot ve benzersiz URL sayısını göster
        total_snapshots_categorized = sum(len(snaps) for cat in categories.values() for snaps in cat.values())
        unique_urls = sum(len(cat) for cat in categories.values())
        # --- YENİ: Kullanıcı dostu özet ---
        msg = "Keşif tamamlandı!\n"
        if total_snapshots_all is not None:
            msg += f"Archive.org'dan çekilen snapshot: {total_snapshots_all}\n"
        if total_snapshots_used is not None:
            msg += f"Filtrelenip kategorize edilen snapshot: {total_snapshots_used}\n"
        msg += f"Kategorilere ayrılan (kullanılabilir) snapshot: {total_snapshots_categorized}\n"
        msg += f"Benzersiz URL: {unique_urls}"
        self.progress_label.setText(msg)
        QMessageBox.information(self, "Keşif Tamamlandı", msg)
        # Kategorileri göster
        self.show_categories_for_selection(categories)
    
    def discovery_error(self, error_message):
        """Keşif hatası durumunda çağrılır"""
        # Timer'ı durdur
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
        
        self.discover_button.setEnabled(True)
        self.progress_label.setText(f"Keşif hatası: {error_message}")
        QMessageBox.critical(self, "Keşif Hatası", error_message)
    
    def show_categories_for_selection(self, categories):
        """Kategorileri UI'da gösterir ve seçim butonu ekler"""
        # Mevcut widget'ları temizle
        for i in reversed(range(self.category_grid.count())):
            item = self.category_grid.itemAt(i)
            if item and item.widget() is not None:
                item.widget().setParent(None)
        # Kategori widget'ı daha önce eklenmişse çıkar
        if self.category_widget.parent() is not None:
            self.right_panel.layout().removeWidget(self.category_widget)
            self.category_widget.setParent(None)
        # Kategori widget'ını layout'a ekle
        if self.right_panel.layout():
            self.right_panel.layout().insertWidget(0, self.category_widget)
        self.category_widget.setVisible(True)
        
        # Toplam snapshot sayısını hesapla
        total_snapshots = sum(len(urls) for urls in categories.values())
        
        # Progress label'ı güncelle
        self.progress_label.setText(f"Keşif tamamlandı! Toplam {total_snapshots} snapshot bulundu.")
        
        # Her kategori için bir grup oluştur - 2 sütun
        row = 0
        col = 0
        max_cols = 2
        
        for category_key, urls_with_snapshots in categories.items():
            if not urls_with_snapshots:
                continue
                
            # Kategori adını Türkçe'ye çevir
            category_name = {
                'blog_posts': '📝 Yazılar',
                'pages': '📄 Sayfalar',
                'images': '🖼️ Görseller',
                'documents': '📁 Dokümanlar',
                'other': '🔗 Diğer'
            }.get(category_key, category_key)
            
            # Kategori grubu
            group = QGroupBox(f"{category_name} ({len(urls_with_snapshots)})")
            group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #34495e;
                    border-radius: 8px;
                    margin: 5px;
                    padding: 15px;
                    background-color: #2c3e50;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 6px 0 6px;
                    color: #4ecdc4;
                    background-color: #2c3e50;
                }
            """)
            
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(10)
            
            # Açıklama
            description = QLabel(f"Bu kategoride {len(urls_with_snapshots)} URL bulundu")
            description.setStyleSheet("color: #ecf0f1; font-size: 12px;")
            description.setWordWrap(True)
            group_layout.addWidget(description)
            
            # Seçim butonu
            select_button = QPushButton("İncele ve Seç")
            select_button.setStyleSheet("""
                QPushButton {
                    background-color: #e67e22;
                    color: white;
                    border: none;
                    padding: 10px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #d35400;
                }
            """)
            select_button.clicked.connect(lambda checked, key=category_key, urls=urls_with_snapshots: self.open_url_selection_window(key, urls))
            group_layout.addWidget(select_button)
            
            # Grid'e ekle
            self.category_grid.addWidget(group, row, col)
            
            # Sütun ve satır güncelle
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
    
    def content_extracted(self, content):
        # Progress bar'ı güncelle
        current_value = self.progress_bar.value()
        self.progress_bar.setValue(current_value + 1)
        # Bilgi kutusunu güncelle
        idx = self.live_progress_bar.value() + 1 if self.live_progress_bar else 1
        total = self.live_progress_bar.maximum() if self.live_progress_bar else 1
        url = content.get('url', '')
        # Progress label'ı güncelle - update_progress_label ile senkronize et
        self.progress_label.setText(f"Toplam {idx}/{total} içerik çekiliyor")
        # UI'daki listeyi güncelle (duplicate kontrolü)
        already_listed = False
        for i in range(self.extracted_content_list.count()):
            item = self.extracted_content_list.item(i)
            if url in item.text():
                already_listed = True
                break
        if not already_listed:
            title = content.get('title')
            if not title or title.strip().lower() in ['başlık yok', 'başlık bulunamadı', '', None]:
                title = f"Başlık Bulunamadı (ID: {idx})"
            else:
                title = title[:40]
            failed = content.get('failed', False)
            fail_reason = content.get('fail_reason', '')
            item = QListWidgetItem(f"{idx}. {title} | {url[:60]}")
            if failed:
                item.setForeground(QColor('#e74c3c'))  # Kırmızı
                item.setToolTip(f"Başarısız: {fail_reason if fail_reason else 'Bilinmeyen hata'}")
            else:
                item.setForeground(QColor('#27ae60'))  # Yeşil
                item.setToolTip("Başarılı")
            self.extracted_content_list.addItem(item)
        # Seçilen içerik sayısını güncelle - sadece seçim yapıldığında
        self.selected_count_label.setText(f"{len(self.extracted_content)} içerik seçildi")
        self.extract_button.setEnabled(bool(self.extracted_content))
        if self.live_progress_bar:
            self.live_progress_bar.setValue(self.live_progress_bar.value() + 1)
        # --- Kategori ve etiketleri bilgi ekranına yaz ---
        cats = content.get('categories', [])
        tags = content.get('tags', [])
        if cats and tags:
            self.add_log_message(f"✅ {url} | Kategoriler: {', '.join(cats)} | Etiketler: {', '.join(tags)}", "INFO")
        elif not cats and not tags:
            self.add_log_message(f"⚠️ {url} | Kategori bulunamadı, Etiket bulunamadı", "WARNING")
        elif not cats:
            self.add_log_message(f"⚠️ {url} | Kategori bulunamadı", "WARNING")
        elif not tags:
            self.add_log_message(f"⚠️ {url} | Etiket bulunamadı", "WARNING")
    
    def extraction_finished(self, all_content):
        """Çekme işlemi tamamlandığında çağrılır"""
        from bs4 import BeautifulSoup
        for c in all_content:
            if c.get('content') and not c.get('soup'):
                try:
                    c['soup'] = BeautifulSoup(c['content'], 'html.parser')
                except Exception:
                    c['soup'] = None
        self.final_extracted_data = [c for c in all_content if not c.get('failed', False)]
        # Sadece gerçek kategori/etiket çıkarımı
        for content in self.final_extracted_data:
            if content.get('soup'):
                categories, tags = self.extract_categories_from_content(content['soup'], content)
                # Eğer zaten manuel kategori/etiket varsa, üzerine yazma
                if not content.get('categories') or not content['categories']:
                    content['categories'] = categories
                if not content.get('tags') or not content['tags']:
                    content['tags'] = tags
        # UI güncellemeleri
        self.extract_button.setEnabled(True)
        self.extract_button.setText("İçerikleri Çek")
        self.export_button.setEnabled(bool(self.final_extracted_data))
        self.progress_label.setText(f"Toplam {len(self.final_extracted_data)}/{len(all_content)} içerik çekildi")
        # Başarısız URL'leri ve nedenlerini listele
        failed_infos = [(url_info['url'], url_info.get('fail_reason', 'Bilinmeyen hata')) for url_info in all_content if url_info.get('failed', False)]
        self.failed_urls_list.clear()
        if failed_infos:
            self.failed_urls_group.setVisible(True)
            self.retry_failed_button.setVisible(True)
            for url, reason in failed_infos:
                self.failed_urls_list.addItem(f"{url}  |  {reason}")
        else:
            self.failed_urls_group.setVisible(False)
            self.retry_failed_button.setVisible(False)
        
        # Timer'ı durdur
        self.progress_timer.stop()
        self.progress_bar.setVisible(False)
        if self.live_progress_bar:
            self.live_progress_bar.setVisible(False)
        
        # Kullanıcıya bildir
        if failed_infos:
            QMessageBox.warning(self, "Aktarılamayan İçerikler", f"{len(failed_infos)} içerik aktarılmadı! Sadece başarıyla çekilenler aktarılacak.")
        else:
            QMessageBox.information(self, "Çekme Tamamlandı", f"{len(self.final_extracted_data)} içerik başarıyla çekildi!")
        
        # Çekilen içerikler kutusunu güncelle - DOĞRU YER
        self.update_extracted_list()
        # Seçilen içerik sayısını da güncelle - çekme tamamlandığında
        self.selected_count_label.setText(f"{len(self.final_extracted_data)} içerik çekildi")
        self.add_log_message("✅ İçerik çekme tamamlandı!", "SUCCESS")
    
    def extraction_error(self, error_message):
        """Çekme hatası"""
        self.progress_timer.stop() # Timer'ı durdur
        self.progress_bar.setVisible(False) # Progress bar'ı gizle
        self.extract_button.setEnabled(True)
        self.export_button.setEnabled(len(self.extracted_content) > 0) # Hata olsa bile çekilenleri dışa aktarabilir
        QMessageBox.critical(self, "Hata", error_message)
    
    def update_progress(self):
        """Progress animasyonu"""
        self.progress_counter += 1
        self.progress_bar.setValue(self.progress_counter)
    
    def export_to_wordpress(self):
        total_content = len(self.final_extracted_data)
        if total_content == 0:
            QMessageBox.warning(self, "Uyarı", "Dışa aktarılacak içerik yok!")
            return
        
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        
        # Her zaman kullanıcıya seçenek sun
        part_count, ok = QInputDialog.getInt(
            self, 
            "WordPress'e Aktar", 
            f"Toplam {total_content} içerik var.\n\n"
            f"Seçenekler:\n"
            f"• 0 = Otomatik bölme (önerilen)\n"
            f"• 1 = Tek dosya\n"
            f"• 2+ = Manuel parça sayısı\n\n"
            f"Kaç parçaya bölmek istersiniz? (0 = Otomatik)", 
            0, 0, total_content
        )
        if not ok:
            return
        
        auto_mode = False
        if part_count == 0:
            # Otomatik bölme mantığı
            if total_content <= 10:
                part_count = 1
            elif total_content <= 50:
                part_count = 2
            elif total_content <= 100:
                part_count = 3
            elif total_content <= 200:
                part_count = 4
            elif total_content <= 500:
                part_count = 8
            else:
                part_count = 12
            auto_mode = True
        elif part_count < 1:
            part_count = 1
        
        part_size = (total_content + part_count - 1) // part_count
        
        # Kullanıcıya bilgi ver
        if auto_mode:
            QMessageBox.information(
                self, 
                "Otomatik Bölme", 
                f"Toplam {total_content} içerik {part_count} parçaya otomatik bölünecek.\n"
                f"Her dosyada yaklaşık {part_size} içerik olacak."
            )
        else:
            QMessageBox.information(
                self, 
                "Manuel Bölme", 
                f"Toplam {total_content} içerik {part_count} parçaya bölünecek.\n"
                f"Her dosyada yaklaşık {part_size} içerik olacak."
            )
        
        # İlk dosya adını al
        from PySide6.QtWidgets import QFileDialog, QProgressDialog
        
        # Default dosya adını domain ile oluştur
        domain = self.domain_input.text().strip()
        if domain:
            # Domain'den geçersiz karakterleri temizle
            safe_domain = domain.replace('http://', '').replace('https://', '').replace('www.', '')
            safe_domain = safe_domain.replace('/', '_').replace('.', '_')
            default_filename = f"{safe_domain}_wordpress.xml"
        else:
            default_filename = "wordpress.xml"
        
        filename, _ = QFileDialog.getSaveFileName(self, "WordPress XML Kaydet", default_filename, "XML Files (*.xml)")
        if not filename:
            return
        
        # Progress bar başlat
        progress = QProgressDialog("WordPress dosyaları kaydediliyor...", "", 0, part_count, self)
        progress.setWindowTitle("Dışa Aktarım")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        base, ext = filename.rsplit('.', 1) if '.' in filename else (filename, 'xml')
        
        try:
            for i in range(part_count):
                part_data = self.final_extracted_data[i*part_size:(i+1)*part_size]
                if not part_data:
                    continue
                if i == 0:
                    part_filename = filename
                else:
                    part_filename = f"{base}_{i+1}.{ext}"
                self.create_wordpress_xml(part_filename, part_data)
                progress.setValue(i+1)
                if progress.wasCanceled():
                    break
            progress.close()
            QMessageBox.information(self, "Dışa Aktarım Tamamlandı", f"{total_content} içerik başarıyla {part_count} dosyaya dışa aktarıldı.")
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Hata", f"XML oluşturulurken hata oluştu:\n{str(e)}")
    
    def create_wordpress_xml(self, filename, content_list):
        """WordPress'e uyumlu WXR XML oluşturur"""
        try:
            # XML'i manuel olarak oluştur - daha güvenli
            xml_content = '<?xml version="1.0" encoding="UTF-8" ?>\n'
            xml_content += '<rss version="2.0" xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:wfw="http://wellformedweb.org/CommentAPI/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:wp="http://wordpress.org/export/1.2/">\n'
            xml_content += '  <channel>\n'
            # WXR zorunlu alanlar
            xml_content += '    <wp:wxr_version>1.2</wp:wxr_version>\n'
            xml_content += '    <generator>https://github.com/arsivradar</generator>\n'
            # WordPress author bloğu
            xml_content += '    <wp:author>\n'
            xml_content += '      <wp:author_id>1</wp:author_id>\n'
            xml_content += '      <wp:author_login>ArchiveRadar</wp:author_login>\n'
            xml_content += '      <wp:author_email>arsivradar@example.com</wp:author_email>\n'
            xml_content += '      <wp:author_display_name>ArchiveRadar</wp:author_display_name>\n'
            xml_content += '      <wp:author_first_name></wp:author_first_name>\n'
            xml_content += '      <wp:author_last_name></wp:author_last_name>\n'
            xml_content += '    </wp:author>\n'
            # Channel bilgileri
            xml_content += f'    <title>Archive.org Export - {self.domain_input.text()}</title>\n'
            xml_content += f'    <link>https://{self.domain_input.text()}</link>\n'
            xml_content += f'    <description>Archive.org\'dan çekilen içerikler - {self.domain_input.text()}</description>\n'
            # Kategori ve etiketleri topla
            all_cats = set()
            all_tags = set()
            for c in content_list:
                all_cats.update(c.get('categories', []))
                all_tags.update(c.get('tags', []))
            # Debug: Toplam kategori ve etiket sayısını logla
            self.add_log_message(f"📊 XML Export: {len(all_cats)} kategori, {len(all_tags)} etiket bulundu")
            if all_cats:
                self.add_log_message(f"🏷️ Kategoriler: {', '.join(all_cats)}")
            if all_tags:
                self.add_log_message(f"🏷️ Etiketler: {', '.join(all_tags)}")
            # Kategorileri channel'a ekle
            for cat in all_cats:
                if cat and cat.strip():
                    xml_content += f'    <wp:category>\n'
                    xml_content += f'      <wp:cat_name>{cat}</wp:cat_name>\n'
                    xml_content += f'      <wp:category_nicename>{cat.lower().replace(" ", "-")}</wp:category_nicename>\n'
                    xml_content += f'    </wp:category>\n'
            # Etiketleri channel'a ekle
            for tag in all_tags:
                if tag and tag.strip():
                    xml_content += f'    <wp:tag>\n'
                    xml_content += f'      <wp:tag_name>{tag}</wp:tag_name>\n'
                    xml_content += f'      <wp:tag_slug>{tag.lower().replace(" ", "-")}</wp:tag_slug>\n'
                    xml_content += f'    </wp:tag>\n'
            # Her içerik için item oluştur
            for i, content_data in enumerate(content_list, 1):
                xml_content += '    <item>\n'
                # Başlık ve içeriği temizle
                safe_title = self.clean_text_for_xml(content_data.get('title', 'Başlık Yok'))
                safe_content = self.clean_html_content_for_xml(content_data.get('content', 'İçerik Yok'))
                safe_description = self.clean_text_for_xml(content_data.get('meta_description', ''))
                xml_content += f'      <title>{safe_title}</title>\n'
                xml_content += f'      <link>{content_data.get("url", "")}</link>\n'
                # Tarih formatı düzeltme
                pub_date = content_data.get('publication_date', '')
                if not pub_date:
                    pub_date = content_data.get('extraction_date', '')
                # WordPress için tarih formatı: YYYY-MM-DD HH:MM:SS
                if pub_date and len(pub_date) == 10:  # YYYY-MM-DD formatı
                    pub_date = f"{pub_date} 12:00:00"
                elif pub_date and 'T' in pub_date:
                    pub_date = pub_date.replace('T', ' ')
                xml_content += f'      <pubDate>{pub_date}</pubDate>\n'
                # GUID
                unique_id = f"archive-{i}-{abs(hash(content_data.get('url', ''))) % 1000000}"
                xml_content += f'      <guid isPermaLink="false">{unique_id}</guid>\n'
                # Description
                description_text = safe_description or safe_content[:200]
                xml_content += f'      <description>{description_text}</description>\n'
                # Content - HTML formatını koru ama temizle
                xml_content += f'      <content:encoded><![CDATA[{safe_content}]]></content:encoded>\n'
                # WordPress özel alanları
                xml_content += f'      <wp:post_id>{i}</wp:post_id>\n'
                xml_content += f'      <wp:post_date>{pub_date}</wp:post_date>\n'
                xml_content += f'      <wp:post_date_gmt>{pub_date}</wp:post_date_gmt>\n'
                xml_content += '      <wp:comment_status>open</wp:comment_status>\n'
                xml_content += '      <wp:ping_status>open</wp:ping_status>\n'
                xml_content += f'      <wp:post_name>archive-post-{i}</wp:post_name>\n'
                xml_content += '      <wp:status>publish</wp:status>\n'
                xml_content += '      <wp:post_parent>0</wp:post_parent>\n'
                xml_content += '      <wp:menu_order>0</wp:menu_order>\n'
                xml_content += '      <wp:post_type>post</wp:post_type>\n'
                xml_content += '      <wp:post_password></wp:post_password>\n'
                xml_content += '      <wp:is_sticky>0</wp:is_sticky>\n'
                # Creator
                author_name = content_data.get('author', 'ArchiveRadar')
                xml_content += f'      <dc:creator>{author_name}</dc:creator>\n'
                # Kategoriler (her yazıya özel)
                categories = content_data.get('categories', [])
                if categories:
                    self.add_log_message(f"📂 Post {i} için kategoriler ekleniyor: {categories}")
                for cat in categories:
                    if cat and cat.strip():
                        xml_content += f'      <category domain="category" nicename="{cat.lower().replace(" ", "-")}"><![CDATA[{cat}]]></category>\n'
                # Etiketler (her yazıya özel)
                tags = content_data.get('tags', [])
                if tags:
                    self.add_log_message(f"🏷️ Post {i} için etiketler ekleniyor: {tags}")
                for tag in tags:
                    if tag and tag.strip():
                        xml_content += f'      <category domain="post_tag" nicename="{tag.lower().replace(" ", "-")}"><![CDATA[{tag}]]></category>\n'
                # Öne çıkan görsel - Archive.org URL'si olarak ekle
                featured_image = content_data.get('featured_image', '')
                if featured_image:
                    # Her yazı için attachment post_id'si: 10000 + i
                    attachment_post_id = 10000 + i
                    xml_content += '      <wp:postmeta>\n'
                    xml_content += '        <wp:meta_key>_thumbnail_id</wp:meta_key>\n'
                    xml_content += f'        <wp:meta_value><![CDATA[{attachment_post_id}]]></wp:meta_value>\n'
                    xml_content += '      </wp:postmeta>\n'
                    # Ayrıca öne çıkan görsel URL'sini de ekle
                    xml_content += '      <wp:postmeta>\n'
                    xml_content += '        <wp:meta_key>_featured_image_url</wp:meta_key>\n'
                    xml_content += f'        <wp:meta_value><![CDATA[{featured_image}]]></wp:meta_value>\n'
                    xml_content += '      </wp:postmeta>\n'
                xml_content += '    </item>\n'
            # Attachment olarak öne çıkan görselleri ekle
            for i, content_data in enumerate(content_list, 1):
                featured_image = content_data.get('featured_image', '')
                if featured_image:
                    attachment_post_id = 10000 + i
                    xml_content += '    <item>\n'
                    xml_content += f'      <title>Featured Image - Post {i}</title>\n'
                    xml_content += f'      <link>{featured_image}</link>\n'
                    xml_content += f'      <pubDate>{content_data.get("publication_date", "")}</pubDate>\n'
                    xml_content += f'      <guid isPermaLink="false">featured-{i}-{abs(hash(featured_image)) % 1000000}</guid>\n'
                    xml_content += f'      <description>Featured image for post {i}</description>\n'
                    xml_content += f'      <content:encoded><![CDATA[<img src="{featured_image}" alt="Featured Image" />]]></content:encoded>\n'
                    xml_content += f'      <wp:post_id>{attachment_post_id}</wp:post_id>\n'
                    xml_content += f'      <wp:post_date>{content_data.get("publication_date", "")}</wp:post_date>\n'
                    xml_content += f'      <wp:post_date_gmt>{content_data.get("publication_date", "")}</wp:post_date_gmt>\n'
                    xml_content += '      <wp:comment_status>closed</wp:comment_status>\n'
                    xml_content += '      <wp:ping_status>closed</wp:ping_status>\n'
                    xml_content += f'      <wp:post_name>featured-image-{i}</wp:post_name>\n'
                    xml_content += '      <wp:status>inherit</wp:status>\n'
                    xml_content += f'      <wp:post_parent>{i}</wp:post_parent>\n'
                    xml_content += '      <wp:menu_order>0</wp:menu_order>\n'
                    xml_content += '      <wp:post_type>attachment</wp:post_type>\n'
                    xml_content += '      <wp:post_password></wp:post_password>\n'
                    xml_content += '      <wp:is_sticky>0</wp:is_sticky>\n'
                    xml_content += '      <dc:creator>ArchiveRadar</dc:creator>\n'
                    xml_content += f'      <wp:attachment_url>{featured_image}</wp:attachment_url>\n'
                    xml_content += '    </item>\n'
            xml_content += '  </channel>\n'
            xml_content += '</rss>'
            # XML'i dosyaya yaz
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(xml_content)
        except Exception as e:
            raise Exception(f"XML oluşturulurken hata: {str(e)}")

    def clean_text_for_xml(self, text):
        """XML için metni temizler ve güvenli hale getirir"""
        if not text:
            return ""
        
        # HTML içeriği ise sadece kontrol karakterlerini temizle
        if '<' in text and '>' in text:
            # HTML içeriği - sadece kontrol karakterlerini temizle
            import re
            # Kontrol karakterlerini kaldır (HTML tag'lerini bozmadan)
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
            return text
        else:
            # Düz metin - XML escape et
            import re
            # Kontrol karakterlerini kaldır
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
            # Çok uzun boşlukları tek boşluğa çevir
            text = re.sub(r'\s+', ' ', text)
            # Başındaki ve sonundaki boşlukları kaldır
            text = text.strip()
            
            # XML'de sorun yaratabilecek özel karakterleri escape et
            text = text.replace('&', '&amp;')
            text = text.replace('<', '&lt;')
            text = text.replace('>', '&gt;')
            text = text.replace('"', '&quot;')
            text = text.replace("'", '&apos;')
            
            return text

    def clean_html_content_for_xml(self, html_content):
        """HTML içeriği XML için temizler"""
        if not html_content:
            return ""
        
        import re
        # Kontrol karakterlerini kaldır (HTML tag'lerini bozmadan)
        html_content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', html_content)
        
        # Çok uzun boşlukları temizle
        html_content = re.sub(r'\s+', ' ', html_content)
        
        return html_content.strip()



    def open_url_selection_window(self, category_key, urls_with_snapshots):
        """URL seçim penceresini açar"""
        category_name = {
            'blog_posts': '📝 Yazılar',
            'pages': '📄 Sayfalar',
            'images': '🖼️ Görseller',
            'documents': '📁 Dokümanlar',
            'other': '🔗 Diğer'
        }.get(category_key, category_key)
        # Sahte is_blog_post fonksiyonu oluştur
        def is_blog_post(url):
            return True
        dialog = UrlSelectionWindow(category_name, urls_with_snapshots, is_blog_post, parent=self)
        dialog.setModal(False)  # Non-modal yap
        
        # Açılan pencereyi listeye ekle
        self.url_selection_windows.append(dialog)
        
        # Dialog kapatıldığında çağrılacak fonksiyon
        def on_dialog_finished(result):
            # Dialog'u listeden çıkar
            if dialog in self.url_selection_windows:
                self.url_selection_windows.remove(dialog)
            
            if result == QDialog.Accepted:
                newly_selected = dialog.get_selected_urls()
                for url_info in newly_selected:
                    if url_info not in self.extracted_content:
                        self.extracted_content.append(url_info)
                # Seçilen içerik sayısını güncelle - sadece seçim yapıldığında
                self.selected_count_label.setText(f"{len(self.extracted_content)} içerik seçildi")
                self.extract_button.setEnabled(bool(self.extracted_content))
                self.export_button.setEnabled(bool(self.extracted_content))
            
            # Dialog kapandıktan sonra UI'ı güncelle - SADECE seçim sayısını güncelle, kutuyu doldurma
            # self.update_extracted_list()  # BU SATIRI KALDIR - yanlış yerde çağrılıyor
            self.add_log_message(f"URL seçim penceresi kapatıldı. Toplam {len(self.extracted_content)} içerik seçildi.", "INFO")
            
            # Ana pencereyi aktif et
            self.setEnabled(True)
            self.raise_()
            self.activateWindow()
        
        dialog.finished.connect(on_dialog_finished)
        dialog.show()

    def add_log_message(self, message, message_type="INFO"):
        """Log ekranına mesaj ekler"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Mesaj tipine göre renk ve prefix belirle
        if "❌" in message or "Başarısız" in message or "Hata" in message or "Kritik hata" in message:
            color = "#ff6b6b"  # Kırmızı
            message_type = "ERROR"
        elif "✅" in message or "Başarılı" in message:
            color = "#51cf66"  # Yeşil
            message_type = "SUCCESS"
        elif "⚠️" in message or "Yetersiz" in message or "çok küçük" in message:
            color = "#ffd43b"  # Sarı
            message_type = "WARNING"
        elif "🔄" in message or "Deneme" in message:
            color = "#ffa500"  # Turuncu
            message_type = "RETRY"
        elif "⏳" in message or "bekleniyor" in message:
            color = "#74c0fc"  # Mavi
            message_type = "WAIT"
        elif "⏱️" in message or "Timeout" in message:
            color = "#ff922b"  # Turuncu
            message_type = "TIMEOUT"
        elif "🔌" in message or "Bağlantı" in message:
            color = "#ff922b"  # Turuncu
            message_type = "CONNECTION"
        else:
            color = "#adb5bd"  # Gri
            message_type = "INFO"
        
        # Mesajı formatla
        formatted_message = f'<span style="color: {color}; font-family: \'Courier New\', monospace;">[{timestamp}] {message}</span><br>'
        
        # Log ekranına ekle
        self.log_display.append(formatted_message)
        
        # Otomatik scroll
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Terminal'e de yazdır
        print(f"[{timestamp}] {message}")
    
    def clear_log_display(self):
        """Log ekranını temizler"""
        self.log_display.clear()
        self.add_log_message("Log ekranı temizlendi", "INFO")
    
    def update_stats(self, **kwargs):
        """İstatistikleri günceller"""
        for key, value in kwargs.items():
            if key in self.stats:
                self.stats[key] = value
        
        # İstatistik etiketini güncelle
        self.update_stats_row()
    
    def reset_stats(self):
        """İstatistikleri sıfırlar"""
        self.stats = {
            'total_snapshots': 0,
            'processed_snapshots': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'start_time': None
        }
        self.update_stats()
        # Kategori kutusunu tamamen kaldır (boşluk bırakmasın)
        if self.category_widget.parent() is not None and self.right_panel.layout():
            self.right_panel.layout().removeWidget(self.category_widget)
            self.category_widget.setParent(None)
    
    def domain_analysis_finished(self, available_dates, analysis_id):
        """Domain analizi tamamlandığında çağrılır"""
        # Sadece güncel thread'in sonuçlarını kabul et
        if analysis_id != self.current_analysis_id:
            return
            
        # Timer'ı durdur
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
        
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("🔍 DOMAIN ANALİZ ET")
        self.available_dates = available_dates
        
        if available_dates:
            date_range = f"{available_dates[0]} - {available_dates[-1]}"
            date_info = f"📅 Domain {len(available_dates)} farklı tarihte arşivlenmiş\n📆 Tarih aralığı: {date_range}\n✅ Analiz tamamlandı, şimdi tarih seçimi yapabilirsiniz"
            self.date_analysis_label.setText(date_info)
            self.date_analysis_widget.setVisible(True)
            self.date_selection_widget.setVisible(True)
            
            # Tarih seçimlerini güncelle
            if len(available_dates) > 0:
                first_date = datetime.strptime(available_dates[0], "%Y-%m")
                last_date = datetime.strptime(available_dates[-1], "%Y-%m")
                
                self.start_date_edit.setDate(QDate(first_date.year, first_date.month, 1))
                self.end_date_edit.setDate(QDate(last_date.year, last_date.month, 1))
            
            self.discover_button.setEnabled(True)
            self.progress_label.setText("Domain analizi tamamlandı! Tarih seçimi yapın ve 'Keşfet' butonuna basın.")
            self.add_log_message(f"Domain analizi tamamlandı! {len(available_dates)} tarih bulundu", "SUCCESS")
        else:
            self.progress_label.setText("Bu domain için hiç arşiv bulunamadı!")
            self.add_log_message("Bu domain için hiç arşiv bulunamadı!", "WARNING")
    
    def domain_analysis_error(self, error_message):
        """Domain analizi hatası durumunda çağrılır"""
        # Timer'ı durdur
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
        
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("🔍 DOMAIN ANALİZ ET")
        self.progress_label.setText(f"Domain analizi hatası: {error_message}")
        self.add_log_message(f"Domain analizi hatası: {error_message}", "ERROR")
        QMessageBox.critical(self, "Analiz Hatası", error_message)
    
    def reset_timeout_settings(self):
        """Timeout ayarlarını varsayılan değerlere sıfırlar"""
        self.api_timeout_spin.setValue(60)
        self.content_timeout_spin.setValue(20)
        self.retry_spin.setValue(3)
        self.add_log_message("Timeout ayarları varsayılan değerlere sıfırlandı", "INFO")
    
    def get_timeout_settings(self):
        """UI'dan timeout ayarlarını alır"""
        return {
            'api_timeout': self.api_timeout_spin.value(),
            'content_timeout': self.content_timeout_spin.value(),
            'retry_count': self.retry_spin.value(),
            'request_delay': self.request_delay_spin.value()
        }

    def retry_failed_urls(self):
        """Seçili başarısız URL'leri tekrar çek"""
        selected_items = self.failed_urls_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Bilgi", "Tekrar çekmek için en az bir URL seçin.")
            return
        retry_urls = [item.text() for item in selected_items]
        # Seçili URL'leri tekrar çekmek için extraction başlat
        retry_url_infos = [url_info for url_info in self.extracted_content if url_info['url'] in retry_urls]
        if retry_url_infos:
            self.start_extraction(retry_url_infos)

    def set_default_timeouts(self):
        # Archive.org API limitlerine uygun güvenli değerler
        self.api_timeout_spin.setValue(120)  # API timeout'u artır
        self.content_timeout_spin.setValue(60)  # İçerik timeout'u artır
        self.retry_spin.setValue(3)  # Retry sayısını azalt (çok fazla deneme yapıyor)
        self.request_delay_spin.setValue(1)  # Request delay'i azalt
        self.add_log_message("Timeout ayarları varsayılan değerlere sıfırlandı", "INFO")

    def update_extracted_list(self):
        self.extracted_content_list.clear()
        
        # Hangi listeyi göstereceğini belirle
        # Eğer içerik çekme işlemi tamamlanmışsa final_extracted_data'yı kullan
        # Aksi halde kutu boş olsun
        data_to_show = getattr(self, 'final_extracted_data', [])
        
        if not data_to_show:
            self.extracted_content_list.setVisible(False)
            return
        self.extracted_content_list.setVisible(True)
        items = []
        for i, c in enumerate(data_to_show):
            title = c.get('title', '')
            url = c.get('url', '')
            categories = c.get('categories', [])
            tags = c.get('tags', [])
            failed = c.get('failed', False)
            fail_reason = c.get('fail_reason', '')
            
            # Başlık kontrolü
            if not title or title.strip().lower() in ['başlık yok', 'başlık bulunamadı', '', None]:
                title = f"Başlık Bulunamadı (ID: {i+1})"
            else:
                title = title[:50]  # Biraz daha uzun başlık
            
            # URL'yi kısalt
            short_url = url[:40] + "..." if len(url) > 40 else url
            
            # Kategori ve etiket bilgilerini hazırla
            cat_info = ""
            tag_info = ""
            
            if categories:
                cat_text = ", ".join(categories[:3])  # İlk 3 kategori
                if len(categories) > 3:
                    cat_text += f" (+{len(categories)-3})"
                cat_info = f"📂 {cat_text}"
            
            if tags:
                tag_text = ", ".join(tags[:3])  # İlk 3 etiket
                if len(tags) > 3:
                    tag_text += f" (+{len(tags)-3})"
                tag_info = f"🏷️ {tag_text}"
            
            # Ana metin
            main_text = f"{i+1}. {title}"
            
            # Alt bilgi
            sub_text = f"🌐 {short_url}"
            if cat_info:
                sub_text += f" | {cat_info}"
            if tag_info:
                sub_text += f" | {tag_info}"
            
            # Tooltip için detaylı bilgi
            tooltip_text = f"Başlık: {title}\nURL: {url}"
            if categories:
                tooltip_text += f"\nKategoriler: {', '.join(categories)}"
            if tags:
                tooltip_text += f"\nEtiketler: {', '.join(tags)}"
            
            # Ana item
            item = QListWidgetItem(main_text)
            item.setData(Qt.UserRole, {'url': url, 'categories': categories, 'tags': tags})
            
            # Alt bilgi için ikinci item
            sub_item = QListWidgetItem(f"   {sub_text}")
            sub_item.setData(Qt.UserRole, {'url': url, 'categories': categories, 'tags': tags})
            
            # Renk ve tooltip ayarla
            if failed:
                item.setForeground(QColor('#e74c3c'))  # Kırmızı
                sub_item.setForeground(QColor('#e74c3c'))
                item.setToolTip(f"❌ Başarısız: {fail_reason if fail_reason else 'Bilinmeyen hata'}\n{tooltip_text}")
                sub_item.setToolTip(f"❌ Başarısız: {fail_reason if fail_reason else 'Bilinmeyen hata'}\n{tooltip_text}")
            else:
                item.setForeground(QColor('#27ae60'))  # Yeşil
                sub_item.setForeground(QColor('#95a5a6'))  # Gri (alt bilgi)
                item.setToolTip(f"✅ Başarılı\n{tooltip_text}")
                sub_item.setToolTip(f"✅ Başarılı\n{tooltip_text}")
            
            items.extend([item, sub_item])
        
        # Sadece ilk 20 içerik (40 item) göster, fazlası için buton
        if len(items) > 40:
            for it in items[:40]:
                self.extracted_content_list.addItem(it)
            # "Tümünü göster" butonu ekle
            show_all_item = QListWidgetItem("... Tümünü görmek için tıklayın ...")
            show_all_item.setForeground(QColor('#3498db'))
            show_all_item.setToolTip("Tüm çekilen içerikleri göster")
            self.extracted_content_list.addItem(show_all_item)
        else:
            for it in items:
                self.extracted_content_list.addItem(it)

    def show_all_extracted_items(self):
        self.extracted_content_list.clear()
        items = []
        for i, c in enumerate(self.extracted_content):
            title = c.get('title', '')
            url = c.get('url', '')
            categories = c.get('categories', [])
            tags = c.get('tags', [])
            failed = c.get('failed', False)
            fail_reason = c.get('fail_reason', '')
            
            # Başlık kontrolü
            if not title or title.strip().lower() in ['başlık yok', 'başlık bulunamadı', '', None]:
                title = f"Başlık Bulunamadı (ID: {i+1})"
            else:
                title = title[:50]  # Biraz daha uzun başlık
            
            # URL'yi kısalt
            short_url = url[:40] + "..." if len(url) > 40 else url
            
            # Kategori ve etiket bilgilerini hazırla
            cat_info = ""
            tag_info = ""
            
            if categories:
                cat_text = ", ".join(categories[:3])  # İlk 3 kategori
                if len(categories) > 3:
                    cat_text += f" (+{len(categories)-3})"
                cat_info = f"📂 {cat_text}"
            
            if tags:
                tag_text = ", ".join(tags[:3])  # İlk 3 etiket
                if len(tags) > 3:
                    tag_text += f" (+{len(tags)-3})"
                tag_info = f"🏷️ {tag_text}"
            
            # Ana metin
            main_text = f"{i+1}. {title}"
            
            # Alt bilgi
            sub_text = f"🌐 {short_url}"
            if cat_info:
                sub_text += f" | {cat_info}"
            if tag_info:
                sub_text += f" | {tag_info}"
            
            # Tooltip için detaylı bilgi
            tooltip_text = f"Başlık: {title}\nURL: {url}"
            if categories:
                tooltip_text += f"\nKategoriler: {', '.join(categories)}"
            if tags:
                tooltip_text += f"\nEtiketler: {', '.join(tags)}"
            
            # Ana item
            item = QListWidgetItem(main_text)
            item.setData(Qt.UserRole, {'url': url, 'categories': categories, 'tags': tags})
            
            # Alt bilgi için ikinci item
            sub_item = QListWidgetItem(f"   {sub_text}")
            sub_item.setData(Qt.UserRole, {'url': url, 'categories': categories, 'tags': tags})
            
            # Renk ve tooltip ayarla
            if failed:
                item.setForeground(QColor('#e74c3c'))  # Kırmızı
                sub_item.setForeground(QColor('#e74c3c'))
                item.setToolTip(f"❌ Başarısız: {fail_reason if fail_reason else 'Bilinmeyen hata'}\n{tooltip_text}")
                sub_item.setToolTip(f"❌ Başarısız: {fail_reason if fail_reason else 'Bilinmeyen hata'}\n{tooltip_text}")
            else:
                item.setForeground(QColor('#27ae60'))  # Yeşil
                sub_item.setForeground(QColor('#95a5a6'))  # Gri (alt bilgi)
                item.setToolTip(f"✅ Başarılı\n{tooltip_text}")
                sub_item.setToolTip(f"✅ Başarılı\n{tooltip_text}")
            
            items.extend([item, sub_item])
        
        for it in items:
            self.extracted_content_list.addItem(it)

    def extract_categories_from_content(self, soup, url_info):
        """Yazının HTML içeriğinden kategori ve etiketleri çıkarır (gelişmiş)"""
        categories = []
        tags = []
        try:
            # Gereksiz kelimeleri filtrele
            junk_words = ['home', 'index', 'main', 'default', 'page', 'post', 'article', 'entry', 'content', 'text']
            
            # 1. Kategori için yaygın selectorlar - sadece makale içeriğindeki kategoriler
            cat_selectors = [
                # Sadece makale içeriğindeki kategori selector'ları
                'article [rel="category tag"]', 'article [rel="category"]',
                'article a.category', 'article a.cat', 'article a.kategori',
                '.post [rel="category tag"]', '.post [rel="category"]',
                '.post a.category', '.post a.cat', '.post a.kategori',
                '.entry [rel="category tag"]', '.entry [rel="category"]',
                '.entry a.category', '.entry a.cat', '.entry a.kategori',
                '.article [rel="category tag"]', '.article [rel="category"]',
                '.article a.category', '.article a.cat', '.article a.kategori',
                # Makale meta bilgileri
                '.post-meta .category', '.entry-meta .category', '.article-meta .category',
                '.post-info .category', '.entry-info .category', '.article-info .category',
                # Kategori linkleri
                '.cat-links a', '.entry-categories a', '.post-categories a', '.category a', '.categories a', '.category-links a',
                '.post-category', '.entry-category', '.article-category'
            ]
            
            for selector in cat_selectors:
                for el in soup.select(selector):
                    txt = el.get_text(strip=True)
                    if txt and len(txt) > 2 and len(txt) < 50 and txt.lower() not in junk_words:
                        categories.append(txt)
            
            # 2. Meta tag'lerden kategori
            meta_categories = ['category', 'categories', 'section', 'department']
            for meta_name in meta_categories:
                meta = soup.find('meta', {'name': meta_name})
                if meta and meta.get('content'):
                    for kw in meta['content'].split(','):
                        kw = kw.strip()
                        if len(kw) > 2 and len(kw) < 50 and kw.lower() not in junk_words:
                            categories.append(kw)
            
            # 3. Etiket için yaygın selectorlar
            tag_selectors = [
                '[rel="tag"]',
                'a.tag', 'a.etiket', 'a[data-tag]',
                'span.tag', 'span.etiket', 'span[data-tag]',
                'div.tag', 'div.etiket', 'div[data-tag]',
                '.tag-links a', '.entry-tags a', '.post-tags a', '.tags a', '.etiketler a', '.etiket a', '.tag a', '.tags a',
                '.tag-cloud a', '.tag-list a', '.tag-menu a', '.tag-nav a'
            ]
            
            for selector in tag_selectors:
                for el in soup.select(selector):
                    txt = el.get_text(strip=True)
                    if txt and len(txt) > 2 and len(txt) < 30 and txt.lower() not in junk_words:
                        tags.append(txt)
            
            # 4. Meta tag'lerden etiket
            meta_tags = ['keywords', 'tags', 'etiketler', 'labels']
            for meta_name in meta_tags:
                meta = soup.find('meta', {'name': meta_name})
                if meta and meta.get('content'):
                    for kw in meta['content'].split(','):
                        kw = kw.strip()
                        if len(kw) > 2 and len(kw) < 30 and kw.lower() not in junk_words:
                            tags.append(kw)
            
            # 5. Open Graph ve Twitter meta tag'lerinden
            og_meta = soup.find('meta', {'property': 'article:section'})
            if og_meta and og_meta.get('content'):
                cat = og_meta['content'].strip()
                if len(cat) > 2 and len(cat) < 50 and cat.lower() not in junk_words:
                    categories.append(cat)
            
            # 6. YENİ: Başlıktan kategori çıkarma
            title = soup.find('title')
            if title and title.get_text():
                title_text = title.get_text().strip()
                # Başlıktan anlamlı kelimeleri al
                import re
                words = re.findall(r'\b\w{4,}\b', title_text.lower())
                for word in words:
                    if word not in junk_words and len(word) > 3:
                        # Türkçe karakterleri düzelt
                        word = word.replace('i', 'ı').replace('I', 'I')
                        tags.append(word.title())
            
            # 7. YENİ: İçerikten anahtar kelimeleri çıkar
            content_text = soup.get_text()
            if content_text:
                import re
                # Sadece Türkçe kelimeleri al
                turkish_words = re.findall(r'\b[a-zA-ZğüşöçıİĞÜŞÖÇ]{4,}\b', content_text.lower())
                from collections import Counter
                word_freq = Counter(turkish_words)
                # En çok geçen 5 kelimeyi etiket olarak al
                for word, count in word_freq.most_common(5):
                    if word not in junk_words and len(word) > 3:
                        # Türkçe karakterleri düzelt
                        word = word.replace('i', 'ı').replace('I', 'I')
                        tags.append(word.title())
            
            # 8. Tekilleştir ve temizle
            categories = list(dict.fromkeys([c.strip() for c in categories if c.strip()]))[:5]
            tags = list(dict.fromkeys([t.strip() for t in tags if t.strip()]))[:10]
            
            # 9. Debug log
            if categories or tags:
                print(f"[DEBUG] HTML'den bulunan kategoriler: {categories}")
                print(f"[DEBUG] HTML'den bulunan etiketler: {tags}")
            
        except Exception as e:
            print(f"HTML kategori/etiket çıkarma hatası: {e}")
        
        return categories, tags

    def open_selector_window(self, url, mode="category"):
        dialog = FixedSelectorDialog(url, mode, self)
        dialog.exec()
        # Seçilen selector'leri kaydetme ve kullanma sonraki adımda eklenecek
    
    def on_category_switch_changed(self, checked):
        """Kategori switch'i değiştiğinde çağrılır"""
        self.advanced_category_detection = checked
        print(f"🔧 Kategori tespiti {'açıldı' if checked else 'kapatıldı'}")
        
        # Açık olan URL seçim pencerelerindeki butonları güncelle
        for child in self.findChildren(QDialog):
            if hasattr(child, 'update_add_selected_button_state'):
                child.update_add_selected_button_state()
    
    def on_auto_detection_checkbox_changed(self, state):
        """Otomatik kategori/etiket tespiti checkbox'ı değiştiğinde çağrılır"""
        checked = state == Qt.Checked
        self.auto_category_tag_detection = checked
        print(f"🔧 Otomatik kategori/etiket tespiti {'açıldı' if checked else 'kapatıldı'}")
        
        # Switch'lerin durumunu güncelle
        if checked:
            # Checkbox açıldığında switch'ler aktif olur ve ON'a geçer
            self.advanced_category_switch.setEnabled(True)
            self.advanced_tag_switch.setEnabled(True)
            self.advanced_category_switch.setChecked(True)
            self.advanced_tag_switch.setChecked(True)
            self.advanced_category_detection = True
            self.advanced_tag_detection = True
        else:
            # Checkbox kapandığında switch'ler pasif olur ve OFF'a geçer
            self.advanced_category_switch.setChecked(False)
            self.advanced_tag_switch.setChecked(False)
            self.advanced_category_switch.setEnabled(False)
            self.advanced_tag_switch.setEnabled(False)
            self.advanced_category_detection = False
            self.advanced_tag_detection = False
        
        # Açık olan URL seçim pencerelerindeki butonları güncelle
        for child in self.findChildren(QDialog):
            if hasattr(child, 'update_add_selected_button_state'):
                child.update_add_selected_button_state()
    
    def on_tag_switch_changed(self, checked):
        """Etiket switch'i değiştiğinde çağrılır"""
        self.advanced_tag_detection = checked
        print(f"🔧 Etiket tespiti {'açıldı' if checked else 'kapatıldı'}")
        
        # Açık olan URL seçim pencerelerindeki butonları güncelle
        for child in self.findChildren(QDialog):
            if hasattr(child, 'update_add_selected_button_state'):
                child.update_add_selected_button_state()
    
    def closeEvent(self, event):
        """Ana pencere kapatılırken temizlik yapar"""
        # Tüm thread'leri durdur
        if hasattr(self, 'discovery_thread') and self.discovery_thread and self.discovery_thread.isRunning():
            self.discovery_thread.stop_requested = True
            self.discovery_thread.wait(5000)  # 5 saniye bekle
        
        if hasattr(self, 'extraction_thread') and self.extraction_thread and self.extraction_thread.isRunning():
            self.extraction_thread.stop_requested = True
            self.extraction_thread.wait(5000)  # 5 saniye bekle
        
        if hasattr(self, 'analysis_thread') and self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.wait(5000)  # 5 saniye bekle
        
        # Timer'ları durdur
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
        
        event.accept()

class SelectorDialog(QDialog):
    """HTML element seçici dialog - tag_test_minimal mantığı"""
    
    def __init__(self, url, mode="category", parent=None):
        super().__init__(parent)
        self.url = url
        self.mode = mode  # "category" veya "tag"
        self.selected_selectors = []
        self.setup_ui()
        
        # ESKİ SEÇİMLERİ YÜKLE
        self.load_previous_selections()
        
        self.load_page()
    
    def setup_ui(self):
        self.setWindowTitle(f"HTML Element Seçici - {self.mode.title()}")
        self.setMinimumSize(1000, 700)
        
        layout = QVBoxLayout(self)
        
        # Başlık
        title_label = QLabel(f"🎯 {self.mode.title()} Seçim Modu")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4ecdc4; margin: 10px;")
        layout.addWidget(title_label)
        
        # Açıklama
        desc_label = QLabel("Sayfadaki elementlere tıklayarak kategori/etiket seçicilerini tanımlayın")
        desc_label.setStyleSheet("color: #e0e0e0; margin: 5px;")
        layout.addWidget(desc_label)
        
        # Web view
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)
        
        # Seçilen selector'lar listesi
        selector_group = QGroupBox("Seçilen Elementler")
        selector_layout = QVBoxLayout(selector_group)
        
        self.selector_list = QListWidget()
        self.selector_list.setStyleSheet("font-size: 13px; padding: 6px; min-height: 60px; max-height: 120px; background: #23272e; color: #e0e0e0; border-radius: 6px;")
        self.selector_list.setMinimumHeight(80)
        self.selector_list.setMaximumHeight(140)
        self.selector_list.setWordWrap(True)
        selector_layout.addWidget(self.selector_list)
        
        # Butonlar
        button_layout = QHBoxLayout()
        
        self.delete_button = QPushButton("Seçiliyi Sil")
        self.delete_button.clicked.connect(self.delete_selected_selector)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)
        
        self.clear_button = QPushButton("Tümünü Temizle")
        self.clear_button.clicked.connect(self.clear_all_selectors)
        button_layout.addWidget(self.clear_button)
        
        button_layout.addStretch()
        
        self.save_button = QPushButton("Kaydet ve Kapat")
        self.save_button.clicked.connect(self.save_and_close)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("İptal")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        selector_layout.addLayout(button_layout)
        layout.addWidget(selector_group)
        
        # Bağlantılar
        self.selector_list.itemSelectionChanged.connect(self.update_delete_button_state)
        
        # Title değişikliklerini dinle
        self.web_view.titleChanged.connect(self.show_element_info)
    
    def load_previous_selections(self):
        """Daha önce seçilmiş selector'ları yükler"""
        try:
            # Parent window'dan url_selections'a eriş
            parent_window = self.parent()
            print(f"[DEBUG] Parent window: {parent_window}")
            
            # Ana pencereyi bul
            while parent_window:
                print(f"[DEBUG] Parent window type: {type(parent_window)}")
                if hasattr(parent_window, 'global_selectors'):
                    print(f"[DEBUG] global_selectors bulundu!")
                    break
                parent_window = parent_window.parent()
                if not parent_window:
                    print(f"[DEBUG] Ana pencere bulunamadı!")
                    break
            
            if parent_window and hasattr(parent_window, 'global_selectors'):
                print(f"[DEBUG] Global seçimler kontrol ediliyor: {self.mode}")
                if self.mode in parent_window.global_selectors and parent_window.global_selectors[self.mode]:
                    # Eski seçimleri yükle
                    for selector in parent_window.global_selectors[self.mode]:
                        # Selector'ı listeye ekle
                        item_text = f"{selector}\n   📝 (Önceden seçilmiş)"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, selector)
                        self.selector_list.addItem(item)
                        self.selected_selectors.append(selector)
                    
                    print(f"✅ Global {len(parent_window.global_selectors[self.mode])} eski {self.mode} seçimi yüklendi")
                else:
                    print(f"ℹ️ Global {self.mode} seçimi bulunamadı")
            else:
                print(f"❌ Parent window'da global_selectors bulunamadı!")
        except Exception as e:
            print(f"❌ Eski seçimleri yükleme hatası: {e}")
    
    def load_page(self):
        """Sayfayı yükler ve JavaScript'i enjekte eder"""
        self.web_view.load(QUrl(self.url))
        self.web_view.loadFinished.connect(self.start_overlay_mode)
    
    def start_overlay_mode(self, success):
        """Element seçme modu başlatır - tag_test_minimal mantığı"""
        if not success:
            return
        
        print(f"[DEBUG] Element seçme modu başlatılıyor, JS injection yapılıyor.")
        js_code = '''
        (function() {
            try {
                if (window._tagtespit_overlay) return;
                window._tagtespit_overlay = true;
                var overlay = document.createElement('div');
                overlay.style.position = 'fixed';
                overlay.style.left = '0';
                overlay.style.top = '0';
                overlay.style.width = '100vw';
                overlay.style.height = '100vh';
                overlay.style.zIndex = '999999';
                overlay.style.background = 'rgba(0,0,0,0.01)';
                overlay.style.cursor = 'crosshair';
                overlay.style.pointerEvents = 'none';
                document.body.appendChild(overlay);

                function onClick(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    var x = e.clientX, y = e.clientY;
                    var el = document.elementFromPoint(x, y);
                    if (!el || el === overlay) {
                        document.title = '[SEÇİM YOK]';
                    } else {
                        // CSS selector'ı oluştur
                        let selector = '';
                        if (el.id) {
                            selector = '#' + el.id;
                        } else if (el.className) {
                            let classes = el.className.split(' ').filter(c => c.trim());
                            if (classes.length > 0) {
                                selector = '.' + classes.join('.');
                            }
                        }
                        if (!selector) {
                            selector = el.tagName.toLowerCase();
                        }
                        // Parent elementleri kontrol et
                        let parent = el.parentElement;
                        let depth = 0;
                        while (parent && parent !== document.body && depth < 3) {
                            if (parent.id) {
                                selector = '#' + parent.id + ' ' + selector;
                                break;
                            } else if (parent.className) {
                                let classes = parent.className.split(' ').filter(c => c.trim());
                                if (classes.length > 0) {
                                    selector = '.' + classes.join('.') + ' ' + selector;
                                    break;
                                }
                            }
                            parent = parent.parentElement;
                            depth++;
                        }
                        var info = selector + '|' + el.textContent.trim().substring(0, 100);
                        document.title = info;
                    }
                    overlay.remove();
                    window.removeEventListener('click', onClick, true);
                    window._tagtespit_overlay = false;
                }
                setTimeout(function() {
                    window.addEventListener('click', onClick, true);
                }, 10);
            } catch (err) {
                document.title = '[OVERLAY BASARISIZ]';
            }
        })();
        '''
        self.web_view.page().runJavaScript(js_code)
    
    def show_element_info(self, info):
        """Element bilgisini gösterir"""
        print(f"[DEBUG] Element kutusuna yazılıyor: {info}")
        if info and '|' in info:
            parts = info.split('|', 1)
            if len(parts) == 2:
                selector = parts[0]
                text = parts[1]
                self.add_selector(selector, text)
        elif info == '[SEÇİM YOK]':
            print('Seçim yapılmadı.')
        elif info == '[OVERLAY BASARISIZ]':
            print('Overlay injection başarısız oldu.')
    
    def add_selector(self, selector, text):
        """Seçilen selector'ı listeye ekler"""
        item_text = f"{selector}\n   📝 {text[:50]}..."
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, selector)
        self.selector_list.addItem(item)
        self.selected_selectors.append(selector)
    
    def delete_selected_selector(self):
        """Seçili selector'ı siler"""
        current_row = self.selector_list.currentRow()
        if current_row >= 0:
            self.selector_list.takeItem(current_row)
            self.selected_selectors.pop(current_row)
    
    def clear_all_selectors(self):
        """Tüm selector'ları temizler"""
        self.selector_list.clear()
        self.selected_selectors.clear()
    
    def update_delete_button_state(self):
        """Sil butonunun durumunu günceller"""
        self.delete_button.setEnabled(self.selector_list.currentRow() >= 0)
    
    def save_and_close(self):
        """Seçilen selector'ları kaydeder ve dialog'u kapatır"""
        from urllib.parse import urlparse
        parsed_url = urlparse(self.url)
        domain = parsed_url.netloc.lower().replace('www.', '')
        
        # Parent window'dan domain_selectors'a eriş
        if hasattr(self.parent(), 'domain_selectors'):
            if domain not in self.parent().domain_selectors:
                self.parent().domain_selectors[domain] = {'category': [], 'tag': []}
            self.parent().domain_selectors[domain][self.mode] = self.selected_selectors.copy()
            print(f"Domain '{domain}' için {self.mode} selector'ları kaydedildi: {self.selected_selectors}")
        
        # Global seçimleri sakla
        parent_window = self.parent()
        print(f"[DEBUG] Parent window: {parent_window}")
        while parent_window:
            print(f"[DEBUG] Parent window type: {type(parent_window)}")
            if hasattr(parent_window, 'global_selectors'):
                print(f"[DEBUG] global_selectors bulundu!")
                break
            parent_window = parent_window.parent()
            if not parent_window:
                print(f"[DEBUG] Ana pencere bulunamadı!")
                break
        if parent_window and hasattr(parent_window, 'global_selectors'):
            if self.selected_selectors:
                # Global selector'lara kaydet (URL'ye özel değil)
                parent_window.global_selectors[self.mode] = self.selected_selectors.copy()
                print(f"✅ Global {self.mode} seçimleri kaydedildi: {self.selected_selectors}")
            else:
                # Hiçbir şey seçilmediyse, global selector'ları temizle
                parent_window.global_selectors[self.mode] = []
                print(f"⚠️ Global {self.mode} seçimleri temizlendi.")
        else:
            print(f"❌ Parent window'da global_selectors bulunamadı!")
        
        # URL listesini yenile
        parent_window = self.parent()
        while parent_window and not hasattr(parent_window, 'global_selectors'):
            parent_window = parent_window.parent()
        if parent_window and hasattr(parent_window, 'populate_url_list'):
            parent_window.populate_url_list()
            print("✅ URL listesi yenilendi")
        
        self.accept()
    
    def closeEvent(self, event):
        """Dialog kapatılırken temizlik yapar"""
        # Web view'ı temizle
        if hasattr(self, 'web_view'):
            self.web_view.deleteLater()
        
        event.accept()

class SelectorBridge(QObject):
    """JavaScript ile Python arasında köprü"""
    
    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
    
    @Slot(str, str)
    def selectorSelected(self, selector, text):
        """JavaScript'ten gelen selector seçimini işler"""
        self.dialog.add_selector(selector, text)

class AutoDetectionThread(QThread):
    """Otomatik kategori/etiket tespiti yapan thread"""
    progress = Signal(str)
    
    def __init__(self, url_to_snapshots, parent_window):
        super().__init__()
        self.url_to_snapshots = url_to_snapshots
        self.parent_window = parent_window
    
    def run(self):
        """Otomatik tespit işlemini yapar"""
        try:
            # Önce internet bağlantısını kontrol et
            self.progress.emit("🌐 İnternet bağlantısı kontrol ediliyor...")
            import requests
            try:
                test_response = requests.get("https://web.archive.org", timeout=10)
                if test_response.status_code != 200:
                    self.progress.emit("❌ Archive.org'a erişilemiyor! İnternet bağlantınızı kontrol edin.")
                    return
            except Exception as e:
                self.progress.emit(f"❌ İnternet bağlantısı hatası: {str(e)}")
                return
            
            self.progress.emit("✅ İnternet bağlantısı OK, tespit başlatılıyor...")
            
            total_urls = len(self.url_to_snapshots)
            processed = 0
            successful = 0
            
            # Akıllı retry mekanizması
            base_delay = 2
            max_delay = 60
            consecutive_errors = 0
            max_consecutive_errors = 5
            
            for url, snapshots in self.url_to_snapshots.items():
                try:
                    self.progress.emit(f"🔍 Tespit ediliyor: {url[:50]}... ({processed+1}/{total_urls})")
                    
                    # En yeni snapshot'ı kullan
                    if snapshots:
                        latest_snapshot = max(snapshots, key=lambda s: s['timestamp'])
                        archive_url = latest_snapshot['archive_url']
                        
                        # Akıllı retry ile HTML çek
                        soup = self.fetch_with_retry(archive_url)
                        
                        if soup:
                            # Kategori ve etiket tespiti
                            categories, tags = self.detect_categories_and_tags(soup, url)
                            
                            # Cache'e kaydet
                            if url not in self.parent_window.detected_categories_cache:
                                self.parent_window.detected_categories_cache[url] = {}
                            
                            self.parent_window.detected_categories_cache[url]['categories'] = categories
                            self.parent_window.detected_categories_cache[url]['tags'] = tags
                            
                            successful += 1
                            consecutive_errors = 0  # Başarılı istek
                            
                            if categories or tags:
                                self.progress.emit(f"✅ {url[:30]}... - {len(categories)} kategori, {len(tags)} etiket")
                            else:
                                self.progress.emit(f"⚠️ {url[:30]}... - Kategori/etiket bulunamadı")
                        else:
                            consecutive_errors += 1
                            self.progress.emit(f"❌ {url[:30]}... - HTML çekilemedi")
                        
                        # Akıllı bekleme
                        if consecutive_errors >= max_consecutive_errors:
                            delay = min(base_delay * (2 ** consecutive_errors), max_delay)
                            self.progress.emit(f"⚠️ Çok fazla hata! {delay} saniye bekleniyor...")
                            import time
                            time.sleep(delay)
                        else:
                            import time
                            time.sleep(base_delay)
                        
                    processed += 1
                    
                except Exception as e:
                    consecutive_errors += 1
                    print(f"❌ URL tespit hatası ({url}): {e}")
                    processed += 1
                    continue
            
            self.progress.emit(f"🎯 Tespit tamamlandı! {successful}/{total_urls} URL başarılı")
            
        except Exception as e:
            print(f"❌ Otomatik tespit hatası: {e}")
            self.progress.emit(f"Hata: {str(e)}")
    
    def fetch_with_retry(self, archive_url, max_retries=3):
        """Akıllı retry ile HTML çeker"""
        import requests
        from bs4 import BeautifulSoup
        import time
        
        for attempt in range(max_retries):
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
                    'Connection': 'keep-alive'
                }
                
                response = requests.get(archive_url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    # Encoding'i düzelt
                    if response.encoding == 'ISO-8859-1':
                        response.encoding = 'utf-8'
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    return soup
                    
                elif response.status_code == 429:
                    # Rate limit
                    delay = (attempt + 1) * 5
                    self.progress.emit(f"⚠️ Rate limit! {delay} saniye bekleniyor...")
                    time.sleep(delay)
                    continue
                    
                elif response.status_code in [502, 503, 504]:
                    # Server hatası
                    delay = (attempt + 1) * 10
                    self.progress.emit(f"⚠️ Server hatası {response.status_code}! {delay} saniye bekleniyor...")
                    time.sleep(delay)
                    continue
                    
                else:
                    # Diğer HTTP hataları
                    self.progress.emit(f"⚠️ HTTP {response.status_code}")
                    time.sleep(2)
                    continue
                    
            except requests.exceptions.ConnectionError:
                delay = (attempt + 1) * 3
                self.progress.emit(f"⚠️ Bağlantı hatası! {delay} saniye bekleniyor...")
                time.sleep(delay)
                continue
                
            except requests.exceptions.Timeout:
                delay = (attempt + 1) * 3
                self.progress.emit(f"⚠️ Timeout! {delay} saniye bekleniyor...")
                time.sleep(delay)
                continue
                
            except Exception as e:
                self.progress.emit(f"❌ Beklenmeyen hata: {str(e)}")
                time.sleep(2)
                continue
        
        return None  # Tüm denemeler başarısız
    
    def detect_categories_and_tags(self, soup, url):
        """HTML'den kategori ve etiket tespiti yapar"""
        categories = set()
        tags = set()
        
        try:
            # Kategori tespiti
            cat_selectors = [
                '[rel="category tag"]', '[rel="category"]', '[rel="tag"]',
                'a.category', 'a.cat', 'a.kategori', 'a[data-category]',
                'span.category', 'span.cat', 'span.kategori', 'span[data-category]',
                'div.category', 'div.cat', 'div.kategori', 'div[data-category]',
                'a[href*="/kategori/"]', 'a[href*="/category/"]', 'a[href*="category"]',
                '.cat-links a', '.entry-categories a', '.post-categories a', '.category a', '.categories a', '.category-links a'
            ]
            
            for selector in cat_selectors:
                for el in soup.select(selector):
                    txt = el.get_text(strip=True)
                    if txt and len(txt) > 1 and len(txt) < 50:
                        categories.add(txt.title())
            
            # Meta tag'lerden kategori
            for meta_name in ['category', 'categories', 'kategori']:
                meta = soup.find('meta', {'name': meta_name})
                if meta and meta.get('content'):
                    for kw in meta['content'].split(','):
                        kw = kw.strip()
                        if len(kw) > 2 and len(kw) < 30:
                            categories.add(kw.title())
            
            # Etiket tespiti
            title = soup.find('title')
            if title:
                title_text = title.get_text(strip=True)
                for word in title_text.split():
                    if len(word) > 3:
                        tags.add(word.title())
            
            # Meta description'dan etiketler
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                desc_text = meta_desc['content']
                for word in desc_text.split():
                    if len(word) > 3:
                        tags.add(word.title())
            
            # İçerikten en çok geçen kelimeler
            content = soup.get_text()
            import re
            from collections import Counter
            
            words = re.findall(r'\b\w{4,}\b', content.lower())
            word_counts = Counter(words)
            
            # En çok geçen 5 kelimeyi etiket olarak ekle
            for word, count in word_counts.most_common(5):
                if count > 2:  # En az 3 kez geçmeli
                    tags.add(word.title())
            
        except Exception as e:
            print(f"❌ Kategori/etiket tespit hatası: {e}")
        
        return list(categories)[:5], list(tags)[:5]  # En fazla 5'er tane

class DomainAnalysisThread(QThread):
    """Domain analizi yapan thread"""
    progress = Signal(str)
    analysis_complete = Signal(list, int)
    error = Signal(str)
    
    def __init__(self, domain, analysis_id):
        super().__init__()
        self.domain = domain
        self.analysis_id = analysis_id
    
    def run(self):
        try:
            self.progress.emit("Archive.org'dan domain bilgileri alınıyor...")
            
            # Domain'in hangi tarihlerde arşivlendiğini bul
            available_dates = self.get_available_dates()
            if not available_dates:
                self.error.emit("Bu domain için hiç arşiv bulunamadı!")
                return
            
            self.progress.emit(f"Domain {len(available_dates)} farklı tarihte arşivlenmiş")
            self.analysis_complete.emit(available_dates, self.analysis_id)
            
        except Exception as e:
            self.error.emit(f"Analiz hatası: {str(e)}")
    
    def get_available_dates(self):
        """Domain'in hangi tarihlerde arşivlendiğini bulur (tüm domain için)"""
        try:
            cdx_url = f"https://web.archive.org/cdx/search/cdx"
            params = {
                'url': self.domain + '/*',
                'output': 'json',
                'fl': 'timestamp',
                'collapse': 'timestamp:4'
            }
            response = requests.get(cdx_url, params=params, timeout=60)
            if response.status_code != 200:
                return []
            data = response.json()
            if len(data) <= 1:
                return []
            dates = []
            for row in data[1:]:
                if row:
                    timestamp = row[0]
                    if len(timestamp) >= 8:
                        year = timestamp[:4]
                        month = timestamp[4:6]
                        dates.append(f"{year}-{month}")
            return sorted(list(set(dates)))
        except Exception as e:
            print(f"Tarih alma hatası: {e}")
            return []

def test_url_selection_window():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    # Test verisi: 2 url, her birinin bir snapshot'ı var
    urls_with_snapshots = {
        'http://test1.com': [
            {'url': 'http://test1.com', 'archive_url': 'http://archive.org/1', 'timestamp': '20220101000000'}
        ],
        'http://test2.com': [
            {'url': 'http://test2.com', 'archive_url': 'http://archive.org/2', 'timestamp': '20220102000000'}
        ]
    }
    # Sahte is_blog_post fonksiyonu
    def is_blog_post(url):
        return True

    # Pencereyi aç
    dialog = UrlSelectionWindow('Test Kategori', urls_with_snapshots, is_blog_post)
    dialog.show()
    # İlk iki url'yi seç
    dialog.url_list_widget.setCurrentRow(0)
    dialog.url_list_widget.setCurrentRow(1)
    # Seçilenleri ekle butonunu tetikle
    dialog.add_selected_items()
    # Seçilenler ana pencereye aktarılmış mı?
    selected = dialog.get_selected_urls()
    assert len(selected) == 2, f"Beklenen 2 seçim, gelen: {len(selected)}"
    assert selected[0]['url'] == 'http://test1.com' or selected[1]['url'] == 'http://test1.com'
    print('TEST BAŞARILI: Seçilenler doğru şekilde aktarılıyor.')

# --- Koyu Tema Stylesheet ---
DARK_STYLESHEET = """
QWidget, QDialog, QListWidget, QGroupBox, QScrollArea, QComboBox, QLineEdit, QPushButton, QMenu, QToolTip, QProgressBar, QCheckBox {
    background-color: #23272e;
    color: #e0e0e0;
    border: none;
}
QLabel {
    color: #4ecdc4;
}
QPushButton {
    background-color: #34495e;
    color: #e0e0e0;
    border-radius: 6px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #45b7af;
}
QPushButton:pressed {
    background-color: #3da89f;
}
QListWidget, QScrollArea, QGroupBox, QDialog {
    background-color: #23272e;
    color: #e0e0e0;
    border: 2px solid #34495e;
    border-radius: 8px;
}
QLineEdit, QComboBox, QSpinBox, QDateEdit {
    background-color: #2c3e50;
    color: #e0e0e0;
    border: 1px solid #34495e;
    border-radius: 4px;
}
QMenu {
    background-color: #23272e;
    color: #e0e0e0;
    border: 1px solid #34495e;
}
QToolTip {
    background-color: #34495e;
    color: #e0e0e0;
    border: 1px solid #4ecdc4;
}
QProgressBar {
    background-color: #2c3e50;
    color: #e0e0e0;
    border: 2px solid #4ecdc4;
    border-radius: 6px;
    text-align: center;
    height: 25px;
}
QProgressBar::chunk {
    background-color: #4ecdc4;
    border-radius: 4px;
}
QCheckBox {
    color: #e0e0e0;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #34495e;
    border-radius: 3px;
    background-color: #2c3e50;
}
QCheckBox::indicator:checked {
    background-color: #4ecdc4;
    border-color: #4ecdc4;
}
"""

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()