import os
os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-gpu'
os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'

import sys
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QListWidget, QListWidgetItem, QGroupBox
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt

def debug_log(msg):
    print(f"[DEBUG] {msg}")

class SelectorDialog(QDialog):
    """HTML element seçici dialog - tag_test_minimal mantığı"""
    
    def __init__(self, url, mode="category", parent=None):
        super().__init__(parent)
        self.url = url
        self.mode = mode  # "category" veya "tag"
        self.selected_selectors = []
        self.setup_ui()
        self.load_page()
        self.load_existing_selectors()  # Daha önce kaydedilen selector'ları yükle
    
    def setup_ui(self):
        self.setWindowTitle(f"HTML Element Seçici - {self.mode.title()}")
        self.setMinimumSize(1000, 700)
        
        layout = QVBoxLayout(self)
        
        # Başlık
        title_label = QLabel(f"🎯 {self.mode.title()} Seçim Modu")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4ecdc4; margin: 10px;")
        layout.addWidget(title_label)
        
        # Açıklama
        if self.mode == "category":
            desc_text = "🎯 Kategori Seçimi: Element Seç butonuna bas → Sayfada + işareti belirir → Kategori elementlerine tıkla → Birden fazla seçebilirsin → Kaydet"
        else:  # tag
            desc_text = "🏷️ Etiket Seçimi: Element Seç butonuna bas → Sayfada + işareti belirir → Etiket elementlerine tıkla → Birden fazla seçebilirsin → Kaydet"
        
        desc_label = QLabel(desc_text)
        desc_label.setStyleSheet("color: #e0e0e0; margin: 5px; font-size: 12px; background-color: #34495e; padding: 10px; border-radius: 6px; font-weight: bold;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Element Seç butonu
        self.select_button = QPushButton("Element Seç")
        self.select_button.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                margin: 10px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:pressed {
                background-color: #c0392b;
            }
        """)
        self.select_button.clicked.connect(self.start_element_selection)
        layout.addWidget(self.select_button)
        
        # Web view
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)
        
        # Seçilen selector'lar listesi
        self.selector_group = QGroupBox("Seçilen Elementler (0 adet)")
        self.selector_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #34495e;
                border-radius: 8px;
                margin: 10px;
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
        selector_layout = QVBoxLayout(self.selector_group)
        
        self.selector_list = QListWidget()
        self.selector_list.setMaximumHeight(200)
        self.selector_list.setStyleSheet("""
            QListWidget {
                background-color: #34495e;
                border: 1px solid #4ecdc4;
                border-radius: 4px;
                padding: 5px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                margin: 2px;
                border-radius: 4px;
                background-color: #2c3e50;
            }
            QListWidget::item:selected {
                background-color: #4ecdc4;
                color: #2c3e50;
            }
        """)
        selector_layout.addWidget(self.selector_list)
        
        # Butonlar
        button_layout = QHBoxLayout()
        
        self.delete_button = QPushButton("Seçiliyi Sil")
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: 2px solid #ec7063;
                padding: 8px 15px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ec7063;
                border-color: #e74c3c;
            }
            QPushButton:pressed {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                border-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.delete_button.clicked.connect(self.delete_selected_selector)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)
        
        self.clear_button = QPushButton("Tümünü Temizle")
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: 2px solid #f7dc6f;
                padding: 8px 15px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #f7dc6f;
                border-color: #f39c12;
                color: #2c3e50;
            }
            QPushButton:pressed {
                background-color: #d68910;
            }
        """)
        self.clear_button.clicked.connect(self.clear_all_selectors)
        button_layout.addWidget(self.clear_button)
        
        button_layout.addStretch()
        
        self.save_button = QPushButton("Kaydet ve Kapat")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: 2px solid #2ecc71;
                padding: 8px 15px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
                border-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
        """)
        self.save_button.clicked.connect(self.save_and_close)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: 2px solid #bdc3c7;
                padding: 8px 15px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #bdc3c7;
                border-color: #95a5a6;
                color: #2c3e50;
            }
            QPushButton:pressed {
                background-color: #7f8c8d;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        selector_layout.addLayout(button_layout)
        layout.addWidget(self.selector_group)
        
        # Bağlantılar
        self.selector_list.itemSelectionChanged.connect(self.update_delete_button_state)
        
        # Title değişikliklerini dinle
        self.web_view.titleChanged.connect(self.show_element_info)
        
        # Seçim modu durumu
        self.selection_mode_active = False
    
    def load_page(self):
        """Sayfayı yükler"""
        debug_log(f"URL yükleniyor: {self.url}")
        self.web_view.setUrl(QUrl(self.url))
    
    def load_existing_selectors(self):
        """Daha önce kaydedilen selector'ları yükler"""
        try:
            # Archive.org URL'sinden asıl domain'i çıkar
            from urllib.parse import urlparse
            parsed_url = urlparse(self.url)
            
            # Archive.org URL'si ise asıl domain'i bul
            if 'web.archive.org' in parsed_url.netloc:
                # URL'den asıl domain'i çıkar: web.archive.org/web/20201201171241/http://yardimoloji.com/...
                path_parts = parsed_url.path.split('/')
                for i, part in enumerate(path_parts):
                    if part == 'web' and i + 1 < len(path_parts):
                        # Timestamp'ten sonraki kısım asıl URL
                        if i + 2 < len(path_parts):
                            original_url = '/'.join(path_parts[i+2:])
                            if original_url.startswith('http'):
                                original_parsed = urlparse(original_url)
                                domain = original_parsed.netloc.lower().replace('www.', '')
                                break
                else:
                    # Fallback: URL'den domain çıkar
                    domain = parsed_url.netloc.lower().replace('www.', '')
            else:
                # Normal URL ise direkt domain'i al
                domain = parsed_url.netloc.lower().replace('www.', '')
            
            # Parent window'u bul (URL seçim penceresi -> MainWindow)
            parent_window = self.parent()
            while parent_window and not hasattr(parent_window, 'global_selectors'):
                parent_window = parent_window.parent()
                if parent_window is None:
                    break
            
            # 1. ÖNCE GLOBAL SELECTOR'LARI YÜKLE (tüm sayfalarda kullanılır)
            if parent_window and hasattr(parent_window, 'global_selectors'):
                if self.mode in parent_window.global_selectors and parent_window.global_selectors[self.mode]:
                    debug_log(f"🌍 Global {self.mode} selector'ları yükleniyor...")
                    for selector in parent_window.global_selectors[self.mode]:
                        # Selector'ı listeye ekle
                        item_text = f"{selector}\n   🌍 (Global selector - tüm sayfalarda kullanılır)"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, selector)
                        self.selector_list.addItem(item)
                        self.selected_selectors.append(selector)
                    
                    debug_log(f"✅ {len(parent_window.global_selectors[self.mode])} global {self.mode} selector'ı yüklendi")
                else:
                    debug_log(f"ℹ️ Global {self.mode} selector'ı bulunamadı")
            
            # 2. DOMAIN BAZLI SELECTOR'LARI YÜKLE
            if parent_window and hasattr(parent_window, 'domain_selectors'):
                if domain in parent_window.domain_selectors:
                    existing_selectors = parent_window.domain_selectors[domain].get(self.mode, [])
                    if existing_selectors:
                        debug_log(f"📋 Domain '{domain}' için {len(existing_selectors)} adet mevcut {self.mode} selector'ı yükleniyor...")
                        for selector in existing_selectors:
                            # Selector'ı listeye ekle (text olmadan)
                            item_text = f"{selector}\n   📝 (Domain selector - {domain} için)"
                            item = QListWidgetItem(item_text)
                            item.setData(Qt.UserRole, selector)
                            self.selector_list.addItem(item)
                            self.selected_selectors.append(selector)
                        
                        debug_log(f"✅ {len(existing_selectors)} adet domain {self.mode} selector'ı yüklendi")
                    else:
                        debug_log(f"ℹ️ Domain '{domain}' için mevcut {self.mode} selector'ı bulunamadı")
                else:
                    debug_log(f"ℹ️ Domain '{domain}' için hiç selector kaydı bulunamadı")
            
            # 3. URL BAZLI SEÇİMLERİ YÜKLE
            try:
                if parent_window and hasattr(parent_window, 'url_selections'):
                    if self.url in parent_window.url_selections:
                        url_selections = parent_window.url_selections[self.url]
                        if self.mode in url_selections and url_selections[self.mode]:
                            debug_log(f"🔗 URL '{self.url}' için {len(url_selections[self.mode])} eski {self.mode} seçimi yükleniyor...")
                            for selector in url_selections[self.mode]:
                                # Selector'ı listeye ekle
                                item_text = f"{selector}\n   🔗 (Bu URL için önceden seçilmiş)"
                                item = QListWidgetItem(item_text)
                                item.setData(Qt.UserRole, selector)
                                self.selector_list.addItem(item)
                                self.selected_selectors.append(selector)
                            
                            debug_log(f"✅ URL '{self.url}' için {len(url_selections[self.mode])} eski {self.mode} seçimi yüklendi")
                        else:
                            debug_log(f"ℹ️ URL '{self.url}' için eski {self.mode} seçimi bulunamadı")
                    else:
                        debug_log(f"ℹ️ URL '{self.url}' için hiç seçim kaydı bulunamadı")
            except Exception as e:
                debug_log(f"❌ URL seçimlerini yükleme hatası: {e}")
            
            # Başlığı güncelle
            self.selector_group.setTitle(f"Seçilen Elementler ({len(self.selected_selectors)} adet)")
                
        except Exception as e:
            debug_log(f"❌ load_existing_selectors hatası: {e}")
    
    def start_element_selection(self):
        """Element seçme modunu başlatır"""
        if self.selection_mode_active:
            debug_log("Seçim modu zaten aktif!")
            return
        
        self.selection_mode_active = True
        self.select_button.setText("🎯 Seçim Modu Aktif (Tıklayın)")
        self.select_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                margin: 10px;
            }
        """)
        
        debug_log("Element seçme modu başlatılıyor, JS injection yapılıyor.")
        js_code = '''
        (function() {
            try {
                if (window._tagtespit_overlay) return;
                window._tagtespit_overlay = true;
                
                // Büyük + işareti oluştur
                var crosshair = document.createElement('div');
                crosshair.style.position = 'fixed';
                crosshair.style.left = '50%';
                crosshair.style.top = '50%';
                crosshair.style.transform = 'translate(-50%, -50%)';
                crosshair.style.width = '40px';
                crosshair.style.height = '40px';
                crosshair.style.zIndex = '999999';
                crosshair.style.pointerEvents = 'none';
                crosshair.style.background = 'rgba(255, 0, 0, 0.8)';
                crosshair.style.borderRadius = '50%';
                crosshair.style.border = '3px solid white';
                crosshair.innerHTML = '<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; font-size: 20px; font-weight: bold;">+</div>';
                document.body.appendChild(crosshair);
                
                // Overlay oluştur
                var overlay = document.createElement('div');
                overlay.style.position = 'fixed';
                overlay.style.left = '0';
                overlay.style.top = '0';
                overlay.style.width = '100vw';
                overlay.style.height = '100vh';
                overlay.style.zIndex = '999998';
                overlay.style.background = 'rgba(0,0,0,0.01)';
                overlay.style.cursor = 'crosshair';
                overlay.style.pointerEvents = 'none';
                document.body.appendChild(overlay);

                // Mouse hareketi ile + işaretini takip et
                document.addEventListener('mousemove', function(e) {
                    crosshair.style.left = e.clientX + 'px';
                    crosshair.style.top = e.clientY + 'px';
                    crosshair.style.transform = 'translate(-50%, -50%)';
                });

                // Hover efekti
                document.addEventListener('mouseover', function(e) {
                    if(window.lastHovered && window.lastHovered !== window.lastSelected){
                        window.lastHovered.style.outline = '';
                        window.lastHovered.style.backgroundColor = '';
                    }
                    if(e.target !== window.lastSelected && e.target !== overlay && e.target !== crosshair){
                        e.target.style.outline = '2px dashed #4ecdc4';
                        e.target.style.backgroundColor = 'rgba(78,205,196,0.08)';
                        window.lastHovered = e.target;
                    }
                }, true);
                
                document.addEventListener('mouseout', function(e) {
                    if(window.lastHovered && window.lastHovered !== window.lastSelected){
                        window.lastHovered.style.outline = '';
                        window.lastHovered.style.backgroundColor = '';
                    }
                }, true);

                // Tıklama ile seçim (birden fazla seçim için overlay'i kaldırma)
                function onClick(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    var x = e.clientX, y = e.clientY;
                    var el = document.elementFromPoint(x, y);
                    
                    if (!el || el === overlay || el === crosshair) {
                        console.log('Seçim yapılmadı');
                        return;
                    }
                    
                    // Seçimi işaretle (kalıcı)
                    el.style.outline = '3px solid #e67e22';
                    el.style.backgroundColor = 'rgba(230, 126, 34, 0.2)';
                    window.lastSelected = el;
                    
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
                    
                    // Seçim modunu devam ettir (overlay'i kaldırma)
                    console.log('Element seçildi:', selector);
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
    
    def stop_element_selection(self):
        """Element seçme modunu durdurur"""
        self.selection_mode_active = False
        self.select_button.setText("🎯 Element Seç (Büyük + İşareti)")
        self.select_button.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                margin: 10px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:pressed {
                background-color: #c0392b;
            }
        """)
        
        # JavaScript'te overlay'i kaldır
        js_code = '''
        if (window._tagtespit_overlay) {
            var overlays = document.querySelectorAll('div[style*="z-index: 999999"], div[style*="z-index: 999998"]');
            overlays.forEach(function(el) {
                if (el.parentNode) el.parentNode.removeChild(el);
            });
            window._tagtespit_overlay = false;
        }
        '''
        self.web_view.page().runJavaScript(js_code)
    
    def show_element_info(self, info):
        """Element bilgisini gösterir"""
        debug_log(f"Element kutusuna yazılıyor: {info}")
        
        # Sadece seçim modu aktifken element ekle
        if not self.selection_mode_active:
            return
            
        if info and '|' in info:
            parts = info.split('|', 1)
            if len(parts) == 2:
                selector = parts[0]
                text = parts[1]
                
                # Aynı selector zaten var mı kontrol et
                if selector not in self.selected_selectors:
                    self.add_selector(selector, text)
                    debug_log(f"Yeni element eklendi: {selector}")
                else:
                    debug_log(f"Bu element zaten seçilmiş: {selector}")
        elif info == '[SEÇİM YOK]':
            debug_log('Seçim yapılmadı.')
        elif info == '[OVERLAY BASARISIZ]':
            debug_log('Overlay injection başarısız oldu.')
    
    def add_selector(self, selector, text):
        """Seçilen selector'ı listeye ekler"""
        item_text = f"{selector}\n   📝 {text[:50]}..."
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, selector)
        self.selector_list.addItem(item)
        self.selected_selectors.append(selector)
        
        # Başlığı güncelle
        self.selector_group.setTitle(f"Seçilen Elementler ({len(self.selected_selectors)} adet)")
    
    def delete_selected_selector(self):
        """Seçili selector'ı siler"""
        current_row = self.selector_list.currentRow()
        if current_row >= 0:
            self.selector_list.takeItem(current_row)
            self.selected_selectors.pop(current_row)
            # Başlığı güncelle
            self.selector_group.setTitle(f"Seçilen Elementler ({len(self.selected_selectors)} adet)")
    
    def clear_all_selectors(self):
        """Tüm selector'ları temizler"""
        self.selector_list.clear()
        self.selected_selectors.clear()
        # Başlığı güncelle
        self.selector_group.setTitle(f"Seçilen Elementler ({len(self.selected_selectors)} adet)")
    
    def update_delete_button_state(self):
        """Sil butonunun durumunu günceller"""
        self.delete_button.setEnabled(self.selector_list.currentRow() >= 0)
    
    def save_and_close(self):
        """Seçilen selector'ları kaydeder ve dialog'u kapatır"""
        try:
            # Archive.org URL'sinden asıl domain'i çıkar
            from urllib.parse import urlparse
            parsed_url = urlparse(self.url)
            
            # Archive.org URL'si ise asıl domain'i bul
            if 'web.archive.org' in parsed_url.netloc:
                # URL'den asıl domain'i çıkar: web.archive.org/web/20201201171241/http://yardimoloji.com/...
                path_parts = parsed_url.path.split('/')
                for i, part in enumerate(path_parts):
                    if part == 'web' and i + 1 < len(path_parts):
                        # Timestamp'ten sonraki kısım asıl URL
                        if i + 2 < len(path_parts):
                            original_url = '/'.join(path_parts[i+2:])
                            if original_url.startswith('http'):
                                original_parsed = urlparse(original_url)
                                domain = original_parsed.netloc.lower().replace('www.', '')
                                break
                else:
                    # Fallback: URL'den domain çıkar
                    domain = parsed_url.netloc.lower().replace('www.', '')
            else:
                # Normal URL ise direkt domain'i al
                domain = parsed_url.netloc.lower().replace('www.', '')
            
            print(f"🔍 Tespit edilen domain: {domain}")
            print(f"🔍 Archive.org URL: {self.url}")
            
            # Parent window'u bul (URL seçim penceresi -> MainWindow)
            parent_window = self.parent()
            while parent_window and not hasattr(parent_window, 'global_selectors'):
                parent_window = parent_window.parent()
                if parent_window is None:
                    break
            
            # 1. GLOBAL SELECTOR'LARI KAYDET (tüm sayfalarda kullanılır)
            if parent_window and hasattr(parent_window, 'global_selectors'):
                if self.mode not in parent_window.global_selectors:
                    parent_window.global_selectors[self.mode] = []
                
                # Seçilen selector'ları global olarak kaydet (domain fark etmez)
                for selector in self.selected_selectors:
                    if selector not in parent_window.global_selectors[self.mode]:
                        parent_window.global_selectors[self.mode].append(selector)
                
                print(f"🌍 Global {self.mode} selector'ları kaydedildi: {parent_window.global_selectors[self.mode]}")
            
            # 2. DOMAIN BAZLI SELECTOR'LARI KAYDET
            if parent_window and hasattr(parent_window, 'domain_selectors'):
                if domain not in parent_window.domain_selectors:
                    parent_window.domain_selectors[domain] = {'category': [], 'tag': []}
                parent_window.domain_selectors[domain][self.mode] = self.selected_selectors.copy()
                print(f"📋 Domain '{domain}' için {self.mode} selector'ları kaydedildi: {self.selected_selectors}")
            
            # 3. URL BAZLI SEÇİMLERİ KAYDET
            if parent_window and hasattr(parent_window, 'url_selections'):
                if self.selected_selectors:
                    if self.url not in parent_window.url_selections:
                        parent_window.url_selections[self.url] = {'category': [], 'tag': []}
                    parent_window.url_selections[self.url][self.mode] = self.selected_selectors.copy()
                    print(f"🔗 URL '{self.url}' için {self.mode} seçimleri kaydedildi: {self.selected_selectors}")
                else:
                    # Hiçbir şey seçilmediyse, varsa kaydı sil
                    if self.url in parent_window.url_selections:
                        parent_window.url_selections[self.url][self.mode] = []
                        # Eğer hem kategori hem tag boşsa, url kaydını tamamen sil
                        if not parent_window.url_selections[self.url]['category'] and not parent_window.url_selections[self.url]['tag']:
                            del parent_window.url_selections[self.url]
                    print(f"⚠️ URL '{self.url}' için hiç seçim yapılmadı, kayıt silindi veya eklenmedi.")
            
            # Kaydetme durumunu göster
            if self.selected_selectors:
                print(f"🎯 {len(self.selected_selectors)} adet {self.mode} selector'ı başarıyla kaydedildi!")
                print(f"📋 Kaydedilen selector'lar: {', '.join(self.selected_selectors)}")
                print(f"🌐 Domain: {domain}")
                print(f"🔗 URL: {self.url}")
            else:
                print(f"⚠️ Hiç {self.mode} selector'ı seçilmedi!")
            
            # Seçim modunu durdur
            if self.selection_mode_active:
                self.stop_element_selection()
            
            self.accept()
            
        except Exception as e:
            print(f"❌ save_and_close hatası: {e}")
            # Hata olsa bile kapat
            self.accept()
    
    def closeEvent(self, event):
        """Dialog kapatılırken temizlik yapar"""
        # Seçim modunu durdur
        if self.selection_mode_active:
            self.stop_element_selection()
        
        # Web view'ı temizle
        if hasattr(self, 'web_view'):
            self.web_view.deleteLater()
        
        event.accept()

def test_selector_dialog():
    """Test fonksiyonu"""
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Test URL'si
    test_url = "http://yardimoloji.com"
    
    # Dialog'u aç
    dialog = SelectorDialog(test_url, "category")
    dialog.show()
    
    return app.exec()

if __name__ == "__main__":
    test_selector_dialog() 