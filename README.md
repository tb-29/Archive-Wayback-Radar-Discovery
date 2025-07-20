# Archive Radar: Archive.org Content Discovery & Export Suite

## Overview

**Archive Radar** is a professional desktop GUI application designed for recovering lost website content from [Archive.org (Wayback Machine)](https://archive.org/web/). It allows you to explore and retrieve archived pages, export them in WordPress-compatible formats, and includes a powerful WordPress plugin for image restoration and cleanup.

> Supports x86 and ARM-based systems.

---

## Features

### 🖥️ Desktop GUI Application (Python + PySide6)

- **Domain Analysis:** Automatically discovers all snapshots and date ranges of an archived domain.
- **Category & Tag Mapping:** Use an advanced HTML element selector to define category and tag containers.
- **Bulk Content Fetching:** Retrieves multiple articles, cleans unnecessary elements, and preserves images.
- **WordPress XML Export:** Export content to WXR (WordPress XML) format, with auto-splitting for large sites.
- **Dark Mode & Modern UI:** Intuitive, sleek, and theme-aware interface.
- **Progress & Logging:** Full progress bars and detailed logs for each task.

### 🔌 WordPress Plugin

- **Image Processor:** Automatically downloads and imports images from Archive.org into the WordPress Media Library.
- **Batch Processing:** Handles large-scale image restoration with batch settings.
- **Find & Replace:** Bulk edit content to fix links, references, etc.
- **Slug Cleaner:** Automatically sanitizes and fixes post slugs.
- **Logging System:** Logs and summarizes all actions for review.

---

## 🛠️ Installation

### 💻 Desktop Application

#### 1. Requirements

- Python 3.8 or higher  
- All dependencies listed in `requirements.txt`

#### 2. Setup (Recommended: Use Virtual Environment)

```bash
# On Windows:
python3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python3 archive_discovery.py

# On macOS/Linux:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 archive_discovery.py


