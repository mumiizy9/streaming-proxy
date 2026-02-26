#!/usr/bin/env python3
"""
Multi-Source Streaming Proxy Server
Sources: animegojo.com, series-days.com, 24-hdmovie.com, wow-drama.com, k35tanmai.com, anifume.com
Features: HLS proxy, privacy protection, auto-next, stall recovery, language filter (พากย์ไทย/ซับไทย)
"""

import os, re, json, time, random, hashlib, threading, urllib.parse, base64
from datetime import datetime
from flask import Flask, request, Response, jsonify, send_file, redirect
import cloudscraper
from bs4 import BeautifulSoup

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# ============================================================
# PRIVACY PROTECTION SYSTEM - Multi-layer identity masking
# ============================================================
UA_POOL = [
    # Chrome Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    # Chrome Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    # Chrome Linux
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    # Firefox Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
    # Firefox Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0',
    # Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
    # Safari Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    # Mobile Chrome
    'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0.6778.73 Mobile/15E148 Safari/604.1',
    # Mobile Safari
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
]

ACCEPT_LANGUAGE_POOL = [
    'en-US,en;q=0.9',
    'en-GB,en;q=0.9',
    'en-US,en;q=0.9,th;q=0.8',
    'th-TH,th;q=0.9,en;q=0.8',
    'en-US,en;q=0.9,ja;q=0.8',
    'en,th;q=0.9',
]

# Per-site scraper sessions with rotating identity
_scrapers = {}
_scraper_lock = threading.Lock()

def get_scraper(site_key='default'):
    """Get or create a cloudscraper session for a site with privacy headers."""
    with _scraper_lock:
        if site_key not in _scrapers or random.random() < 0.05:  # 5% chance rotate
            s = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': random.choice(['windows', 'darwin', 'linux']), 'mobile': False},
                delay=random.uniform(0.5, 2.0)
            )
            s.headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': random.choice(ACCEPT_LANGUAGE_POOL),
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            })
            # Strip identifying headers
            for h in ['X-Forwarded-For', 'X-Real-IP', 'Via', 'Forwarded']:
                s.headers.pop(h, None)
            _scrapers[site_key] = s
        return _scrapers[site_key]

def random_ua():
    return random.choice(UA_POOL)

def privacy_delay():
    """Random delay to avoid pattern detection."""
    time.sleep(random.uniform(0.3, 1.5))

def safe_request(url, site_key='default', method='GET', data=None, headers=None, timeout=20, stream=False):
    """Make a request with full privacy protection."""
    s = get_scraper(site_key)
    h = {
        'User-Agent': random_ua(),
        'Accept-Language': random.choice(ACCEPT_LANGUAGE_POOL),
    }
    if headers:
        h.update(headers)
    try:
        if method == 'POST':
            return s.post(url, data=data, headers=h, timeout=timeout, stream=stream)
        else:
            return s.get(url, headers=h, timeout=timeout, stream=stream)
    except Exception as e:
        print(f"[Privacy Request Error] {url}: {e}")
        return None

# ============================================================
# URL ENCODING HELPERS
# ============================================================
def encode_url(url):
    """Base64 encode a URL for safe transport."""
    return base64.urlsafe_b64encode(url.encode()).decode()

def decode_url(encoded):
    """Decode a base64 encoded URL."""
    try:
        return base64.urlsafe_b64decode(encoded.encode()).decode()
    except:
        return ''

# ============================================================
# ANIMEGOJO.COM SCRAPER (Custom Site)
# ============================================================
ANIMEGOJO_BASE = 'https://animegojo.com'

ANIMEGOJO_CATEGORIES = {
    'all': '/',
    'Action': '/category/action/',
    'Adventure': '/category/adventure/',
    'Comedy': '/category/comedy/',
    'Drama': '/category/drama/',
    'Fantasy': '/category/fantasy/',
    'Horror': '/category/horror/',
    'Mystery': '/category/mystery/',
    'Romance': '/category/romance/',
    'Sci-Fi': '/category/sci-fi/',
    'Sports': '/category/sports/',
    'Supernatural': '/category/supernatural/',
    'Historical': '/category/historical/',
    'Ecchi': '/category/ecchi/',
    'Demons': '/category/demons/',
    'Game': '/category/game/',
    'Kids': '/category/kids/',
}

def animegojo_catalog(page=1, category='all'):
    """Get anime catalog from animegojo."""
    cat_path = ANIMEGOJO_CATEGORIES.get(category, '/')
    if page > 1:
        url = f"{ANIMEGOJO_BASE}{cat_path}{page}/"
    else:
        url = f"{ANIMEGOJO_BASE}{cat_path}"
    r = safe_request(url, 'animegojo')
    if not r or r.status_code != 200:
        return {'items': [], 'page': page, 'has_next': False}

    soup = BeautifulSoup(r.text, 'lxml')
    items = []

    # Items are <a href="/list/{id}/{slug}"> tags
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        m = re.match(r'^/list/(\d+)/(.+?)/?$', href)
        if not m:
            continue
        item_id = m.group(1)
        item_slug = m.group(2)
        text = a.get_text(strip=True)
        if not text or len(text) < 3:
            continue

        # Parse title and episode info
        title = text
        ep_info = ''
        ep_match = re.search(r'(EP\s*[\d\-]+(?:\s*\([^)]+\))?)', text)
        if ep_match:
            ep_info = ep_match.group(1)
            title = text[:ep_match.start()].strip()

        # Language tag
        lang = ''
        if 'พากย์ไทย' in text:
            lang = 'พากย์ไทย'
        elif 'ซับไทย' in text:
            lang = 'ซับไทย'

        image = f"{ANIMEGOJO_BASE}/img/{item_id}-{item_slug}.webp"
        combined_slug = f"{item_id}---{item_slug}"

        items.append({
            'title': title,
            'slug': combined_slug,
            'url': f"{ANIMEGOJO_BASE}{href}",
            'image': image,
            'quality': lang,
            'status': ep_info,
        })

    # Deduplicate by slug
    seen = set()
    unique_items = []
    for it in items:
        if it['slug'] not in seen:
            seen.add(it['slug'])
            unique_items.append(it)
    items = unique_items

    has_next = bool(re.search(rf'/{page + 1}/', r.text))

    return {'items': items, 'page': page, 'has_next': has_next}


def animegojo_detail(slug):
    """Get anime detail with episode list. Slug format: {id}---{text_slug}"""
    parts = slug.split('---', 1)
    if len(parts) != 2:
        return None
    item_id, text_slug = parts

    url = f"{ANIMEGOJO_BASE}/list/{item_id}/{text_slug}"
    r = safe_request(url, 'animegojo')
    if not r or r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, 'lxml')

    # Title from div.title h1
    title = ''
    title_el = soup.select_one('div.title h1')
    if title_el:
        title = title_el.get_text(strip=True)
        title = re.sub(r'\s*ตอนที่\s*[\d\-]+\s*$', '', title).strip()

    poster = f"{ANIMEGOJO_BASE}/img/{item_id}-{text_slug}.webp"

    # Synopsis from detail2
    synopsis = ''
    detail2 = soup.select_one('div.detail2')
    if detail2:
        for div in detail2.find_all('div'):
            text_content = div.get_text(strip=True)
            if text_content.startswith('เรื่องย่อ:'):
                synopsis = text_content.replace('เรื่องย่อ:', '').strip()[:500]
                break

    # Episodes from div.ep2 > a > span.ep3
    episodes = []
    ep_container = soup.select_one('div.ep2')
    if ep_container:
        for a_tag in ep_container.find_all('a', href=True):
            href = a_tag.get('href', '')
            ep_id_match = re.search(r'/ep/(\d+)', href)
            if ep_id_match:
                ep_id = ep_id_match.group(1)
                span = a_tag.select_one('span.ep3')
                ep_text = span.get_text(strip=True) if span else a_tag.get_text(strip=True)
                num_match = re.search(r'(\d+)', ep_text)
                ep_num = int(num_match.group(1)) if num_match else len(episodes) + 1
                episodes.append({
                    'number': ep_num,
                    'slug': ep_id,
                    'title': ep_text,
                })

    episodes.sort(key=lambda x: x['number'])

    return {
        'title': title,
        'slug': slug,
        'poster': poster,
        'synopsis': synopsis,
        'episodes': episodes,
        'episode_count': len(episodes),
    }


def animegojo_episode(ep_id):
    """Get video for an animegojo episode. ep_id is the numeric ID from /ep/{id}/"""
    url = f"{ANIMEGOJO_BASE}/ep/{ep_id}/"
    r = safe_request(url, 'animegojo')
    if not r or r.status_code != 200:
        return None

    # Extract video key (link2) from reload() JS
    link2_match = re.search(r'link2=([A-Za-z0-9+/=]+)', r.text)
    link2 = link2_match.group(1) if link2_match else ''

    # Find next/prev episode links
    soup = BeautifulSoup(r.text, 'lxml')
    all_ep_links = []
    ep_container = soup.select_one('div.ep2')
    if ep_container:
        for a_tag in ep_container.find_all('a', href=True):
            ep_match = re.search(r'/ep/(\d+)', a_tag.get('href', ''))
            if ep_match:
                all_ep_links.append(ep_match.group(1))

    current_idx = -1
    for i, eid in enumerate(all_ep_links):
        if eid == ep_id:
            current_idx = i
            break

    next_ep = all_ep_links[current_idx + 1] if current_idx >= 0 and current_idx + 1 < len(all_ep_links) else None

    videos = []
    if link2:
        m3u8_url = f'https://youtube.anccplayer.cyou/playg.php?uid={link2}'
        videos.append({
            'type': 'hls',
            'video_id': link2,
            'm3u8_url': m3u8_url,
            'server': 1,
        })

    return {
        'videos': videos,
        'next_episode': next_ep,
        'servers': videos,
    }


def animegojo_search(query):
    """Search anime on animegojo."""
    url = f"{ANIMEGOJO_BASE}/search?name={urllib.parse.quote(query)}"
    r = safe_request(url, 'animegojo')
    if not r or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, 'lxml')
    results = []

    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        m = re.match(r'^/list/(\d+)/(.+?)/?$', href)
        if not m:
            continue
        item_id = m.group(1)
        item_slug = m.group(2)
        text = a.get_text(strip=True)
        if not text or len(text) < 3:
            continue

        title = text
        ep_match = re.search(r'(EP\s*[\d\-]+)', text)
        if ep_match:
            title = text[:ep_match.start()].strip()

        combined_slug = f"{item_id}---{item_slug}"
        image = f"{ANIMEGOJO_BASE}/img/{item_id}-{item_slug}.webp"

        if combined_slug not in [r_item['slug'] for r_item in results]:
            results.append({
                'title': title,
                'slug': combined_slug,
                'url': f"{ANIMEGOJO_BASE}{href}",
                'image': image,
            })

    return results


# ============================================================
# SERIES-DAYS.COM SCRAPER (Halim Theme)
# ============================================================
SERIESDAYS_BASE = 'https://www.series-days.com'
SERIESDAYS_API = f'{SERIESDAYS_BASE}/api/get.php'

SERIESDAYS_CATEGORIES = {
    'all': '/',
    'ใหม่2025': '/%e0%b8%8b%e0%b8%b5%e0%b8%a3%e0%b8%b5%e0%b9%88%e0%b8%a2%e0%b9%8c%e0%b9%83%e0%b8%ab%e0%b8%a1%e0%b9%88-2025/',
    'พากย์ไทย': '/%e0%b8%8b%e0%b8%b5%e0%b8%a3%e0%b8%b5%e0%b9%88%e0%b8%a2%e0%b9%8c%e0%b8%9e%e0%b8%b2%e0%b8%81%e0%b8%a2%e0%b9%8c%e0%b9%84%e0%b8%97%e0%b8%a2/',
    'Netflix': '/netflix/',
    'TOP IMDB': '/top-imdb/',
}

def seriesdays_catalog(page=1, category='all'):
    """Get series catalog from series-days."""
    cat_path = SERIESDAYS_CATEGORIES.get(category, '/')
    if page > 1:
        url = f"{SERIESDAYS_BASE}{cat_path}page/{page}/"
    else:
        url = f"{SERIESDAYS_BASE}{cat_path}"
    r = safe_request(url, 'seriesdays')
    if not r or r.status_code != 200:
        return {'items': [], 'page': page, 'has_next': False}

    soup = BeautifulSoup(r.text, 'lxml')
    items = []

    for box in soup.select('div.box'):
        link = box.select_one('a[href]')
        if not link:
            continue
        href = link.get('href', '')
        if 'series-days.com' not in href:
            continue

        slug = href.rstrip('/').split('/')[-1]
        if not slug:
            continue

        img = box.select_one('img')
        image = ''
        if img:
            image = img.get('data-lazy-src', '') or img.get('src', '') or img.get('data-src', '')

        title_el = box.select_one('.p2')
        title = title_el.get_text(strip=True) if title_el else (img.get('alt', '') if img else slug)

        lang_el = box.select_one('.p1')
        lang = lang_el.get_text(strip=True) if lang_el else ''

        ep_el = box.select_one('.EP')
        ep_status = ep_el.get_text(strip=True) if ep_el else ''

        items.append({
            'title': title,
            'slug': slug,
            'url': href,
            'image': image,
            'quality': lang,
            'status': ep_status,
        })

    seen = set()
    unique_items = []
    for it in items:
        if it['slug'] not in seen:
            seen.add(it['slug'])
            unique_items.append(it)
    items = unique_items

    has_next = bool(re.search(rf'page/{page + 1}/', r.text))

    return {'items': items, 'page': page, 'has_next': has_next}


def seriesdays_detail(slug):
    """Get series detail with episode list."""
    url = f"{SERIESDAYS_BASE}/{slug}/"
    r = safe_request(url, 'seriesdays')
    if not r or r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, 'lxml')

    title = ''
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        title = og_title.get('content', '').strip()
    if not title:
        title_tag = soup.select_one('title')
        if title_tag:
            title = title_tag.get_text(strip=True).split(' - ')[0].split(' | ')[0].strip()

    poster = ''
    og_img = soup.select_one('meta[property="og:image"]')
    if og_img:
        poster = og_img.get('content', '').strip()
    if not poster:
        poster_el = soup.select_one('img.wp-post-image, .movie-l-img img, .poster img')
        if poster_el:
            poster = poster_el.get('data-lazy-src', '') or poster_el.get('src', '') or poster_el.get('data-src', '')

    synopsis = ''
    syn_el = soup.select_one('.entry-content p, .film-content p, .halim-entry-box p')
    if syn_el:
        synopsis = syn_el.get_text(strip=True)[:500]

    post_id = None
    cfg_match = re.search(r'"post_id"\s*:\s*(\d+)', r.text)
    if cfg_match:
        post_id = cfg_match.group(1)
    if not post_id:
        btn = soup.select_one('[data-post-id]')
        if btn:
            post_id = btn.get('data-post-id')

    max_ep = 0
    ep_nums_from_links = re.findall(re.escape(slug) + r'-ep-?(\d+)', r.text)
    if ep_nums_from_links:
        max_ep = max(int(n) for n in ep_nums_from_links)
    if max_ep == 0:
        ep_text_nums = re.findall(r'(?:EP|ตอนที่|ตอน)\s*[.\s]*(\d+)', r.text, re.I)
        if ep_text_nums:
            max_ep = max(int(n) for n in ep_text_nums)
    if max_ep == 0:
        max_ep = 1

    episodes = []
    if post_id:
        for n in range(1, max_ep + 1):
            episodes.append({
                'number': n,
                'slug': f'{post_id}-ep-{n}',
                'post_id': post_id,
                'title': f'ตอนที่ {n}',
            })

    return {
        'title': title,
        'slug': slug,
        'poster': poster,
        'synopsis': synopsis,
        'post_id': post_id,
        'episodes': episodes,
        'episode_count': len(episodes),
    }


def seriesdays_episode_video(slug):
    """Get video for a series-days episode. Slug format: {post_id}-ep-{N}"""
    ep_match = re.match(r'(\d+)-ep-(\d+)', slug)
    if ep_match:
        post_id = ep_match.group(1)
        episode = ep_match.group(2)
    else:
        url = f"{SERIESDAYS_BASE}/{slug}/"
        r = safe_request(url, 'seriesdays')
        if not r or r.status_code != 200:
            return None
        cfg_match = re.search(r'"post_id"\s*:\s*(\d+)', r.text)
        post_id = cfg_match.group(1) if cfg_match else None
        episode = '1'
        if not post_id:
            return None

    servers = []
    for server_num in range(1, 4):
        result = _halim_get_video(SERIESDAYS_API, post_id, episode, server_num, SERIESDAYS_BASE, slug)
        if result:
            servers.append(result)

    ep_num = int(episode)
    next_ep = f'{post_id}-ep-{ep_num + 1}'

    return {
        'post_id': post_id,
        'episode': episode,
        'servers': servers,
        'next_episode': next_ep,
    }


def seriesdays_get_video(post_id, episode=1, server=1):
    """Get video URL from series-days Halim API."""
    return _halim_get_video(SERIESDAYS_API, post_id, episode, server, SERIESDAYS_BASE)


# ============================================================
# 24-HDMOVIE.COM SCRAPER (Halim Theme + External API)
# ============================================================
HDMOVIE_BASE = 'https://www.24-hdmovie.com'
HDMOVIE_API = 'https://api.24-hdmovie.com/get.php'

HDMOVIE_CATEGORIES = {
    'all': '/',
    'หนังใหม่2026': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b9%83%e0%b8%ab%e0%b8%a1%e0%b9%88-2026/',
    'หนังใหม่2025': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b9%83%e0%b8%ab%e0%b8%a1%e0%b9%88-2025/',
    'ชนโรง': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b8%8a%e0%b8%99%e0%b9%82%e0%b8%a3%e0%b8%87/',
    'การ์ตูน': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b8%81%e0%b8%b2%e0%b8%a3%e0%b9%8c%e0%b8%95%e0%b8%b9%e0%b8%99/',
    'ฝรั่ง': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b8%9d%e0%b8%a3%e0%b8%b1%e0%b9%88%e0%b8%87/',
    'เกาหลี': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b9%80%e0%b8%81%e0%b8%b2%e0%b8%ab%e0%b8%a5%e0%b8%b5/',
    'จีน': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b8%88%e0%b8%b5%e0%b8%99/',
    'ไทย': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b9%80%e0%b8%ad%e0%b9%80%e0%b8%8a%e0%b8%b5%e0%b8%a2/',
    'ญี่ปุ่น': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b8%8d%e0%b8%b5%e0%b9%88%e0%b8%9b%e0%b8%b8%e0%b9%88%e0%b8%99/',
    'เอเชีย': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b9%80%e0%b8%ad%e0%b9%80%e0%b8%8a%e0%b8%b5%e0%b8%a2/',
    'อินเดีย': '/%e0%b8%ab%e0%b8%99%e0%b8%b1%e0%b8%87%e0%b8%ad%e0%b8%b4%e0%b8%99%e0%b9%80%e0%b8%94%e0%b8%b5%e0%b8%a2/',
    'Netflix': '/netflix/',
    'ซีรี่ย์': '/series/',
    'TOP IMDB': '/topimdb/',
}

def hdmovie_catalog(page=1, category='all'):
    """Get movie catalog from 24-hdmovie."""
    cat_path = HDMOVIE_CATEGORIES.get(category, '/')
    if page > 1:
        url = f"{HDMOVIE_BASE}{cat_path}page/{page}/"
    else:
        url = f"{HDMOVIE_BASE}{cat_path}"
    r = safe_request(url, 'hdmovie')
    if not r or r.status_code != 200:
        return {'items': [], 'page': page, 'has_next': False}

    soup = BeautifulSoup(r.text, 'lxml')
    items = []

    for box in soup.select('div.box'):
        link = box.select_one('a[href]')
        if not link:
            continue
        href = link.get('href', '')
        if '24-hdmovie.com' not in href:
            continue

        slug = href.rstrip('/').split('/')[-1]
        if not slug:
            continue

        img = box.select_one('img')
        image = ''
        if img:
            image = img.get('data-lazy-src', '') or img.get('src', '') or img.get('data-src', '')

        title_el = box.select_one('.p2')
        title = title_el.get_text(strip=True) if title_el else (img.get('alt', '') if img else slug)

        lang_el = box.select_one('.p1')
        lang = lang_el.get_text(strip=True) if lang_el else ''

        items.append({
            'title': title,
            'slug': slug,
            'url': href,
            'image': image,
            'quality': lang,
        })

    seen = set()
    unique_items = []
    for it in items:
        if it['slug'] not in seen:
            seen.add(it['slug'])
            unique_items.append(it)
    items = unique_items

    has_next = bool(re.search(rf'page/{page + 1}/', r.text))

    return {'items': items, 'page': page, 'has_next': has_next}


def hdmovie_detail(slug):
    """Get movie detail and post_id."""
    url = f"{HDMOVIE_BASE}/{slug}/"
    r = safe_request(url, 'hdmovie')
    if not r or r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, 'lxml')

    title = ''
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        title = og_title.get('content', '').strip()
    if not title:
        title_tag = soup.select_one('title')
        if title_tag:
            title = title_tag.get_text(strip=True).split(' - ')[0].split(' | ')[0].strip()

    poster = ''
    og_img = soup.select_one('meta[property="og:image"]')
    if og_img:
        poster = og_img.get('content', '').strip()
    if not poster:
        poster_el = soup.select_one('img.wp-post-image, .movie-l-img img, .poster img')
        if poster_el:
            poster = poster_el.get('data-lazy-src', '') or poster_el.get('src', '') or poster_el.get('data-src', '')

    synopsis = ''
    syn_el = soup.select_one('.entry-content p, .film-content p, .halim-entry-box p')
    if syn_el:
        synopsis = syn_el.get_text(strip=True)[:500]

    post_id = None
    cfg_match = re.search(r'"post_id"\s*:\s*(\d+)', r.text)
    if cfg_match:
        post_id = cfg_match.group(1)
    if not post_id:
        btn = soup.select_one('[data-post-id]')
        if btn:
            post_id = btn.get('data-post-id')

    max_ep = 0
    ep_nums_from_links = re.findall(re.escape(slug) + r'-ep-?(\d+)', r.text)
    if ep_nums_from_links:
        max_ep = max(int(n) for n in ep_nums_from_links)
    if max_ep == 0:
        ep_text_nums = re.findall(r'(?:EP|ตอนที่|ตอน)\s*[.\s]*(\d+)', r.text, re.I)
        if ep_text_nums:
            max_ep = max(int(n) for n in ep_text_nums)
    if max_ep == 0:
        max_ep = 1

    episodes = []
    if post_id:
        for n in range(1, max_ep + 1):
            episodes.append({
                'number': n,
                'slug': f'{post_id}-ep-{n}',
                'post_id': post_id,
                'title': f'ตอนที่ {n}' if max_ep > 1 else 'เล่นเลย',
            })

    return {
        'title': title,
        'slug': slug,
        'poster': poster,
        'synopsis': synopsis,
        'post_id': post_id,
        'episodes': episodes,
        'episode_count': len(episodes),
    }


def hdmovie_get_video(post_id, episode=1, server=1):
    """Get video URL from 24-hdmovie external API."""
    return _halim_get_video(HDMOVIE_API, post_id, episode, server, HDMOVIE_BASE)


# ============================================================
# WOW-DRAMA.COM SCRAPER (WordPress + Miru Player)
# ============================================================
WOWDRAMA_BASE = 'https://wow-drama.com'
WOWDRAMA_AJAX = f'{WOWDRAMA_BASE}/wp-admin/admin-ajax.php'

WOWDRAMA_CATEGORIES = {
    'all': '/category/the-series-all/',
    'ซีรี่ย์มาใหม่': '/category/new-online-todays/',
    'ซีรี่ย์จีน': '/category/doo-free-24/',
    'ซีรี่ย์เกาหลี': '/category/series-korea/',
    'ซีรี่ย์ญี่ปุ่น': '/category/japan-series/',
    'ซีรี่ย์ไทย': '/category/the-series-th/',
}

def wowdrama_catalog(page=1, category='all'):
    """Get drama catalog from wow-drama."""
    cat_path = WOWDRAMA_CATEGORIES.get(category, '/category/the-series-all/')
    if page > 1:
        url = f"{WOWDRAMA_BASE}{cat_path}page/{page}/"
    else:
        url = f"{WOWDRAMA_BASE}{cat_path}"
    r = safe_request(url, 'wowdrama')
    if not r or r.status_code != 200:
        return {'items': [], 'page': page, 'has_next': False}

    soup = BeautifulSoup(r.text, 'lxml')
    items = []

    for movie_div in soup.select('div.-movie'):
        pic_link = movie_div.select_one('div.pic a[href]')
        info_link = movie_div.select_one('h2.entry-title a[href]')
        link = info_link or pic_link
        if not link:
            continue

        href = link.get('href', '')
        if 'wow-drama.com' not in href:
            continue

        slug = href.rstrip('/').split('/')[-1]
        if not slug:
            continue

        title = ''
        if info_link:
            title = info_link.get_text(strip=True)
        if not title:
            img = movie_div.select_one('img')
            if img:
                title = img.get('alt', slug)

        image = ''
        img = movie_div.select_one('img')
        if img:
            image = img.get('src', '') or img.get('data-src', '')

        quality = ''
        qa_label = movie_div.select_one('.qa-label')
        if qa_label:
            quality = qa_label.get_text(strip=True)

        lang_el = movie_div.select_one('.imdb')
        lang = lang_el.get_text(strip=True) if lang_el else ''
        if lang:
            quality = f"{quality} {lang}".strip()

        ep_el = movie_div.select_one('.epseries')
        ep_status = ep_el.get_text(strip=True) if ep_el else ''

        items.append({
            'title': title,
            'slug': slug,
            'url': href,
            'image': image,
            'quality': quality,
            'status': ep_status,
        })

    seen = set()
    unique_items = []
    for it in items:
        if it['slug'] not in seen:
            seen.add(it['slug'])
            unique_items.append(it)
    items = unique_items

    has_next = bool(re.search(rf'page/{page + 1}/', r.text))

    return {'items': items, 'page': page, 'has_next': has_next}


def wowdrama_detail(slug):
    """Get drama detail with episode list."""
    url = f"{WOWDRAMA_BASE}/{slug}/"
    r = safe_request(url, 'wowdrama')
    if not r or r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, 'lxml')

    title = ''
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        title = og_title.get('content', '').strip()
    if not title:
        title_tag = soup.select_one('title')
        if title_tag:
            title = title_tag.get_text(strip=True).split(' - ')[0].split(' | ')[0].strip()

    poster = ''
    og_img = soup.select_one('meta[property="og:image"]')
    if og_img:
        poster = og_img.get('content', '').strip()

    synopsis = ''
    content_div = soup.select_one('.entry-content, .post-content, article')
    if content_div:
        for p in content_div.find_all('p'):
            text_content = p.get_text(strip=True)
            if len(text_content) > 50 and 'wow-drama' not in text_content.lower():
                synopsis = text_content[:500]
                break

    post_id = None
    body = soup.find('body')
    if body:
        body_class = ' '.join(body.get('class', []))
        pid_match = re.search(r'postid-(\d+)', body_class)
        if pid_match:
            post_id = pid_match.group(1)

    episodes = []
    ep_list = soup.select_one('div.mp-ep-list')
    if ep_list:
        for btn in ep_list.select('button.mp-ep-btn'):
            data_id = btn.get('data-id', '')
            if not data_id:
                continue
            ep_text = btn.get_text(strip=True)
            num_match = re.search(r'(\d+)', ep_text)
            ep_num = int(num_match.group(1)) if num_match else len(episodes) + 1
            episodes.append({
                'number': ep_num,
                'slug': data_id,
                'title': ep_text.strip(),
            })

    episodes.sort(key=lambda x: x['number'])

    return {
        'title': title,
        'slug': slug,
        'poster': poster,
        'synopsis': synopsis,
        'post_id': post_id,
        'episodes': episodes,
        'episode_count': len(episodes),
    }


def wowdrama_episode(data_id):
    """Get video for a wow-drama episode via AJAX.
    data_id is the post_id from button.mp-ep-btn data-id attribute.
    """
    r = safe_request(WOWDRAMA_AJAX, 'wowdrama', method='POST', data={
        'action': 'miru_custom_player',
        'post_id': data_id,
    }, headers={
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f'{WOWDRAMA_BASE}/',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    })
    if not r or r.status_code != 200 or r.text.strip() == 'error':
        return None

    videos = []
    soup = BeautifulSoup(r.text, 'lxml')

    # Main iframe
    iframe = soup.select_one('iframe[src]')
    if iframe:
        embed_url = iframe.get('src', '')
        if embed_url:
            video_info = _extract_topcdn_video(embed_url)
            if video_info:
                videos.append(video_info)
            else:
                videos.append({
                    'embed_url': embed_url,
                    'type': 'iframe',
                    'server': 1,
                })

    # Alternative servers from data attributes or additional links
    for i, sl in enumerate(soup.select('[data-id]')):
        sl_url = sl.get('data-id', '')
        if sl_url and sl_url.startswith('http') and sl_url not in [v.get('embed_url', '') for v in videos]:
            video_info = _extract_topcdn_video(sl_url)
            if video_info:
                video_info['server'] = i + 2
                videos.append(video_info)
            else:
                videos.append({
                    'embed_url': sl_url,
                    'type': 'iframe',
                    'server': i + 2,
                })

    return {
        'videos': videos,
        'servers': videos,
        'next_episode': None,
    }


def _extract_topcdn_video(embed_url):
    """Extract HLS video URL from top-cdn.com or ok-hd.com embed."""
    if 'top-cdn.com/play/' not in embed_url and 'ok-hd.com/play/' not in embed_url:
        return None

    hash_match = re.search(r'/play/([a-f0-9]+)', embed_url)
    if not hash_match:
        return None
    video_hash = hash_match.group(1)

    if 'ok-hd.com' in embed_url:
        cdn_base = 'https://ok-hd.com'
    else:
        cdn_base = 'https://top-cdn.com'

    m3u8_url = f'{cdn_base}/hls/{video_hash}/master.m3u8'

    return {
        'video_id': video_hash,
        'embed_url': embed_url,
        'm3u8_url': m3u8_url,
        'type': 'hls',
        'server': 1,
        'cdn_base': cdn_base,
    }


def wowdrama_search(query):
    """Search drama on wow-drama via WP REST API."""
    url = f"{WOWDRAMA_BASE}/wp-json/wp/v2/posts?search={urllib.parse.quote(query)}&per_page=20"
    r = safe_request(url, 'wowdrama', headers={'Accept': 'application/json'})
    if not r or r.status_code != 200:
        return []
    try:
        posts = r.json()
        results = []
        for post in posts:
            slug = post.get('slug', '')
            if not slug:
                continue
            title = post.get('title', {}).get('rendered', slug)
            title = re.sub(r'<[^>]+>', '', title).strip()
            image = ''
            if post.get('_embedded', {}).get('wp:featuredmedia'):
                media = post['_embedded']['wp:featuredmedia'][0]
                image = media.get('source_url', '')
            results.append({
                'title': title,
                'slug': slug,
                'url': post.get('link', f'{WOWDRAMA_BASE}/{slug}/'),
                'image': image,
            })
        return results
    except:
        return []


# ============================================================
# K35TANMAI.COM SCRAPER (WordPress + Elementor)
# ============================================================
K35TANMAI_BASE = 'https://k35tanmai.com'

K35TANMAI_CATEGORIES = {
    'all': '/',
    'พากย์ไทย': '/%e0%b8%ad%e0%b8%99%e0%b8%b4%e0%b9%80%e0%b8%a1%e0%b8%b0%e0%b8%9e%e0%b8%b2%e0%b8%81%e0%b8%a2%e0%b9%8c%e0%b9%84%e0%b8%97%e0%b8%a2/',
    'ซับไทย': '/%e0%b8%ad%e0%b8%99%e0%b8%b4%e0%b9%80%e0%b8%a1%e0%b8%b0%e0%b8%8b%e0%b8%b1%e0%b8%9a%e0%b9%84%e0%b8%97%e0%b8%a2/',
    'มาใหม่': '/%e0%b8%ad%e0%b8%99%e0%b8%b4%e0%b9%80%e0%b8%a1%e0%b8%b0%e0%b8%a1%e0%b8%b2%e0%b9%83%e0%b8%ab%e0%b8%a1%e0%b9%88/',
    'Fantasy': '/fantasy/',
    'Action': '/action/',
    'Romance': '/romance/',
    'Isekai': '/isekai/',
    'อนิเมะจีน': '/cn-anime/',
    'Movie': '/movie/',
}


def k35tanmai_catalog(page=1, category='all'):
    """Get anime catalog from k35tanmai."""
    cat_path = K35TANMAI_CATEGORIES.get(category, '/')
    if page > 1:
        url = f"{K35TANMAI_BASE}{cat_path}page/{page}/"
    else:
        url = f"{K35TANMAI_BASE}{cat_path}"

    r = safe_request(url, 'k35tanmai')
    if not r or r.status_code != 200:
        return {'items': [], 'page': page, 'has_next': False}

    soup = BeautifulSoup(r.text, 'lxml')
    items = []

    for item_el in soup.select('div.e-loop-item'):
        link = item_el.select_one('a[href]')
        if not link:
            continue
        href = link.get('href', '')
        if 'k35tanmai.com' not in href:
            continue

        slug = href.rstrip('/').split('/')[-1]
        if not slug:
            continue

        img = item_el.select_one('img')
        image = ''
        if img:
            image = img.get('src', '') or img.get('data-src', '')

        title = ''
        for heading in item_el.select('.elementor-heading-title'):
            a_tag = heading.select_one('a[href]')
            if a_tag and 'k35tanmai.com' in a_tag.get('href', ''):
                title = a_tag.get_text(strip=True)
                break
        if not title and img:
            title = img.get('alt', slug)

        lang = ''
        full_text = item_el.get_text()
        if 'พากย์ไทย' in full_text:
            lang = 'พากย์ไทย'
        elif 'ซับไทย' in full_text:
            lang = 'ซับไทย'
        elif 'Soundtrack' in full_text:
            lang = 'Soundtrack'

        items.append({
            'title': title,
            'slug': slug,
            'url': href,
            'image': image,
            'quality': lang,
        })

    seen = set()
    unique = []
    for it in items:
        if it['slug'] not in seen:
            seen.add(it['slug'])
            unique.append(it)
    items = unique

    has_next = bool(soup.select_one('a.next.page-numbers') or re.search(rf'page/{page + 1}/', r.text))
    return {'items': items, 'page': page, 'has_next': has_next}


def k35tanmai_detail(slug):
    """Get anime detail from k35tanmai."""
    url = f"{K35TANMAI_BASE}/{slug}/"
    r = safe_request(url, 'k35tanmai')
    if not r or r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, 'lxml')

    title = ''
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        title = og_title.get('content', '').strip()
    if not title:
        h1 = soup.select_one('h1')
        if h1:
            title = h1.get_text(strip=True)

    poster = ''
    og_img = soup.select_one('meta[property="og:image"]')
    if og_img:
        poster = og_img.get('content', '').strip()

    synopsis = ''
    for p in soup.select('.elementor-widget-theme-post-content p, .entry-content p'):
        text = p.get_text(strip=True)
        if len(text) > 50 and 'k35tanmai' not in text.lower():
            synopsis = text[:500]
            break

    lang = ''
    page_text = soup.get_text()
    if 'พากย์ไทย' in page_text:
        lang = 'พากย์ไทย'
    elif 'ซับไทย' in page_text:
        lang = 'ซับไทย'

    episodes = [{
        'number': 1,
        'slug': slug,
        'title': 'เล่นเลย',
    }]

    return {
        'title': title,
        'slug': slug,
        'poster': poster,
        'synopsis': synopsis,
        'language': lang,
        'episodes': episodes,
        'episode_count': 1,
    }


def k35tanmai_episode(slug):
    """Get video for a k35tanmai page. Extracts m3u8 from LiteSpeed JS bundle or inline scripts."""
    url = f"{K35TANMAI_BASE}/{slug}/"
    r = safe_request(url, 'k35tanmai')
    if not r or r.status_code != 200:
        return None

    videos = []
    soup = BeautifulSoup(r.text, 'lxml')
    page_text = r.text

    # 1) Check inline scripts for m3u8/mp4 URLs and iframes
    for script in soup.select('script'):
        script_text = script.string or ''
        # m3u8/mp4 URLs
        for m in re.finditer(r'(?:file|source|src|url)\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', script_text, re.I):
            src = m.group(1).replace('\\/', '/')
            if src not in [v.get('m3u8_url', '') or v.get('embed_url', '') for v in videos]:
                vtype = 'hls' if '.m3u8' in src else 'direct'
                videos.append({'embed_url': src, 'm3u8_url': src if vtype == 'hls' else '', 'type': vtype, 'server': len(videos) + 1})
        # iframes
        for m in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', script_text):
            src = m.group(1).replace('\\/', '/')
            if src and not any(x in src.lower() for x in ['google', 'facebook', 'twitter', 'ads', 'ibit.ly', 'doubleclick']):
                if src not in [v.get('embed_url', '') for v in videos]:
                    videos.append({'embed_url': src, 'type': 'iframe', 'server': len(videos) + 1})

    # 2) Check for iframes in HTML directly
    for iframe in soup.select('iframe[src]'):
        src = iframe.get('src', '')
        if src and not any(x in src.lower() for x in ['google', 'facebook', 'twitter', 'ads', 'ibit.ly', 'doubleclick']):
            if src not in [v.get('embed_url', '') for v in videos]:
                videos.append({'embed_url': src, 'type': 'iframe', 'server': len(videos) + 1})

    # 3) If no m3u8 found yet, check LiteSpeed combined JS bundle
    if not any(v.get('type') == 'hls' for v in videos):
        ls_match = re.search(r'wp-content/litespeed/js/[a-f0-9]+\.js[^"\']*', page_text)
        if ls_match:
            js_url = f"{K35TANMAI_BASE}/{ls_match.group(0)}"
            jr = safe_request(js_url, 'k35tanmai')
            if jr and jr.status_code == 200:
                js_text = jr.text
                # Extract m3u8 URLs from the JS bundle (normal quotes)
                for m in re.finditer(r'(?:file|source|src)\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', js_text, re.I):
                    src = m.group(1).replace('\\/', '/')
                    if src not in [v.get('m3u8_url', '') or v.get('embed_url', '') for v in videos]:
                        videos.insert(0, {'embed_url': src, 'm3u8_url': src, 'type': 'hls', 'server': 1})
                # Escaped JSON pattern: file: \"https:\/\/...\/index.m3u8\"
                # The URL contains \/ so we match everything between \" markers
                for m in re.finditer(r'file:\s*\\"(.*?\.m3u8.*?)\\"', js_text):
                    src = m.group(1).replace('\\/', '/').replace('\\', '')
                    if src.startswith('http') and src not in [v.get('m3u8_url', '') or v.get('embed_url', '') for v in videos]:
                        videos.insert(0, {'embed_url': src, 'm3u8_url': src, 'type': 'hls', 'server': 1})

    # Renumber servers and add video_id for HLS entries
    for i, v in enumerate(videos):
        v['server'] = i + 1
        if v.get('type') == 'hls' and v.get('m3u8_url'):
            v['video_id'] = encode_url(v['m3u8_url'])

    # Fallback: use the page itself as iframe
    if not videos:
        videos.append({'embed_url': url, 'type': 'iframe', 'server': 1})

    return {'videos': videos, 'servers': videos, 'next_episode': None}


def k35tanmai_search(query):
    """Search anime on k35tanmai."""
    url = f"{K35TANMAI_BASE}/?s={urllib.parse.quote(query)}"
    r = safe_request(url, 'k35tanmai')
    if not r or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, 'lxml')
    results = []

    for item_el in soup.select('div.e-loop-item'):
        link = item_el.select_one('a[href]')
        if not link:
            continue
        href = link.get('href', '')
        if 'k35tanmai.com' not in href:
            continue
        slug = href.rstrip('/').split('/')[-1]
        if not slug:
            continue

        img = item_el.select_one('img')
        image = ''
        if img:
            image = img.get('src', '') or img.get('data-src', '')

        title = ''
        for heading in item_el.select('.elementor-heading-title'):
            a_tag = heading.select_one('a[href]')
            if a_tag and 'k35tanmai.com' in a_tag.get('href', ''):
                title = a_tag.get_text(strip=True)
                break
        if not title and img:
            title = img.get('alt', slug)

        if slug not in [r_item['slug'] for r_item in results]:
            results.append({'title': title, 'slug': slug, 'url': href, 'image': image})

    return results


# ============================================================
# ANIFUME.COM SCRAPER
# ============================================================
ANIFUME_BASE = 'https://anifume.com'

ANIFUME_CATEGORIES = {
    'all': '/',
    'ซับไทย': '/',
    'พากย์ไทย': '/',
}


def anifume_catalog(page=1, category='all'):
    """Get anime catalog from anifume."""
    if page > 1:
        url = f"{ANIFUME_BASE}/page/{page}"
    else:
        url = f"{ANIFUME_BASE}/"

    r = safe_request(url, 'anifume')
    if not r or r.status_code != 200:
        return {'items': [], 'page': page, 'has_next': False}

    soup = BeautifulSoup(r.text, 'lxml')
    items = []

    for col in soup.select('div.col-p'):
        link = col.select_one('div.col-title a[href]') or col.select_one('div.col-img a[href]')
        if not link:
            continue
        href = link.get('href', '')
        if not href.startswith('http'):
            href = f"{ANIFUME_BASE}{href}"

        slug_match = re.search(r'/(\d+)(?:/|$)', href.rstrip('/'))
        if not slug_match:
            continue
        slug = slug_match.group(1)

        img = col.select_one('div.col-img img') or col.select_one('img')
        image = ''
        if img:
            image = img.get('src', '') or img.get('data-src', '')
            if image and not image.startswith('http'):
                image = f"{ANIFUME_BASE}{image}"

        title_el = col.select_one('div.col-title a')
        title = title_el.get_text(strip=True) if title_el else ''

        lang = ''
        if 'พากย์ไทย' in title and 'ซับไทย' in title:
            lang = 'ซับไทย/พากย์ไทย'
        elif 'พากย์ไทย' in title:
            lang = 'พากย์ไทย'
        elif 'ซับไทย' in title:
            lang = 'ซับไทย'

        if category == 'พากย์ไทย' and 'พากย์ไทย' not in title:
            continue
        if category == 'ซับไทย' and 'ซับไทย' not in title:
            continue

        items.append({
            'title': title,
            'slug': slug,
            'url': href,
            'image': image,
            'quality': lang,
        })

    seen = set()
    unique = []
    for it in items:
        if it['slug'] not in seen:
            seen.add(it['slug'])
            unique.append(it)
    items = unique

    has_next = bool(soup.select_one('div.pagenavi a.next') or
                     re.search(rf'page/{page + 1}', r.text))
    return {'items': items, 'page': page, 'has_next': has_next}


def anifume_detail(slug):
    """Get anime detail from anifume. Slug is the numeric post ID."""
    url = f"{ANIFUME_BASE}/{slug}"
    r = safe_request(url, 'anifume')
    if not r or r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, 'lxml')

    title = ''
    h1 = soup.select_one('h1.post-title, h1')
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title:
            title = og_title.get('content', '').strip()

    poster = ''
    poster_el = soup.select_one('div.post-content-img img') or soup.select_one('.content-row img')
    if poster_el:
        poster = poster_el.get('src', '')
        if poster and not poster.startswith('http'):
            poster = f"{ANIFUME_BASE}{poster}"

    synopsis = ''
    desc_el = soup.select_one('div.content-des')
    if desc_el:
        synopsis = desc_el.get_text(strip=True)[:500]

    episodes = []
    current_lang = ''

    # Parse episode links separated by language markers
    eplink_wrap = soup.select_one('div.eplink-wrap')
    if eplink_wrap:
        for el in eplink_wrap.find_all(['span', 'div', 'a']):
            if el.name == 'span' and 'eptext' in el.get('class', []):
                text = el.get_text(strip=True)
                # Check which keyword appears first (handles "ซับไทย (พากย์ไทย อยู่ข้างล่าง)")
                sub_pos = text.find('ซับไทย')
                dub_pos = text.find('พากย์ไทย')
                if sub_pos >= 0 and (dub_pos < 0 or sub_pos < dub_pos):
                    current_lang = 'ซับไทย'
                elif dub_pos >= 0:
                    current_lang = 'พากย์ไทย'
                continue

            if el.name == 'a' and el.get('href'):
                ep_href = el.get('href', '')
                if not ep_href or slug not in ep_href:
                    continue
                if not ep_href.startswith('http'):
                    ep_href = f"{ANIFUME_BASE}{ep_href}"

                ep_slug_part = ep_href.rstrip('/').split('/')[-1]
                full_ep_slug = f"{slug}/{ep_slug_part}"

                num_match = re.search(r'(\d+)$', ep_slug_part)
                ep_num = int(num_match.group(1)) if num_match else len(episodes) + 1

                lang_label = f" [{current_lang}]" if current_lang else ''
                episodes.append({
                    'number': ep_num,
                    'slug': full_ep_slug,
                    'title': f"ตอนที่ {ep_num}{lang_label}",
                    'language': current_lang,
                })

    # Fallback: look for episode links directly
    if not episodes:
        for a_tag in soup.select(f'a[href*="/{slug}/"]'):
            ep_href = a_tag.get('href', '')
            ep_text = a_tag.get_text(strip=True)
            if not ep_href:
                continue
            if not ep_href.startswith('http'):
                ep_href = f"{ANIFUME_BASE}{ep_href}"
            ep_slug_part = ep_href.rstrip('/').split('/')[-1]
            full_ep_slug = f"{slug}/{ep_slug_part}"
            num_match = re.search(r'(\d+)', ep_slug_part)
            ep_num = int(num_match.group(1)) if num_match else len(episodes) + 1
            lang = 'พากย์ไทย' if ('-th-' in ep_slug_part or 'พากย์ไทย' in ep_text) else 'ซับไทย'
            episodes.append({
                'number': ep_num,
                'slug': full_ep_slug,
                'title': f"ตอนที่ {ep_num} [{lang}]",
                'language': lang,
            })

    return {
        'title': title,
        'slug': slug,
        'poster': poster,
        'synopsis': synopsis,
        'episodes': episodes,
        'episode_count': len(episodes),
    }


def anifume_episode(ep_slug):
    """Get video for an anifume episode. ep_slug format: {animeID}/{ep-slug-part}"""
    url = f"{ANIFUME_BASE}/{ep_slug}"
    r = safe_request(url, 'anifume')
    if not r or r.status_code != 200:
        return None

    videos = []

    # Extract player iframe URL from inline JS
    iframe_match = re.search(r'innerHTML\s*=\s*[\'"](.*?iframe.*?src=[\'\"]([^\'\"]+)[\'\"].*?)[\'"]', r.text)
    if iframe_match:
        player_url = iframe_match.group(2)
        if not player_url.startswith('http'):
            player_url = f"{ANIFUME_BASE}{player_url}"
        extracted = _extract_anifume_videos(player_url)
        if extracted:
            videos.extend(extracted)
        else:
            videos.append({'embed_url': player_url, 'type': 'iframe', 'server': 1})

    # Look for direct iframes
    soup = BeautifulSoup(r.text, 'lxml')
    for iframe in soup.select('iframe[src]'):
        src = iframe.get('src', '')
        existing_urls = [v.get('embed_url', '') for v in videos] + [v.get('direct_url', '') for v in videos]
        if src and src not in existing_urls:
            videos.append({'embed_url': src, 'type': 'iframe', 'server': len(videos) + 1})

    # Fallback
    if not videos:
        videos.append({'embed_url': url, 'type': 'iframe', 'server': 1})

    # Renumber servers
    for i, v in enumerate(videos):
        v['server'] = i + 1

    return {'videos': videos, 'servers': videos, 'next_episode': None}


def _extract_anifume_videos(player_url):
    """Extract ALL video sources from anifume player page (JWPlayer). Returns list of video dicts."""
    r = safe_request(player_url, 'anifume', headers={'Referer': f'{ANIFUME_BASE}/'})
    if not r or r.status_code != 200:
        return []

    text = r.text
    results = []

    # 1) JWPlayer sources - find all MP4/m3u8 URLs with quality labels
    sources = []
    for m in re.finditer(r'["\']file["\']\s*:\s*["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']', text, re.I):
        url = m.group(1)
        label_match = re.search(r'["\']label["\']\s*:\s*["\']([^"\']+)["\']', text[m.end():m.end()+200])
        label = label_match.group(1) if label_match else ''
        sources.append({'url': url, 'label': label})

    if sources:
        def quality_order(s):
            label = s.get('label', '')
            for q, val in [('1080', 4), ('720', 3), ('480', 2), ('360', 1)]:
                if q in label:
                    return val
            return 0
        sources.sort(key=quality_order, reverse=True)
        for i, src in enumerate(sources):
            if '.m3u8' in src['url']:
                results.append({'m3u8_url': src['url'], 'embed_url': player_url, 'type': 'hls',
                                'server': i + 1, 'video_id': encode_url(src['url']), 'label': src.get('label', '')})
            else:
                results.append({'direct_url': src['url'], 'embed_url': player_url, 'type': 'direct',
                                'server': i + 1, 'label': src.get('label', '')})
        return results

    # 2) Generic patterns
    m3u8_match = re.search(r'(?:source|src|file|url)\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', text, re.I)
    if m3u8_match:
        return [{'m3u8_url': m3u8_match.group(1), 'embed_url': player_url, 'type': 'hls', 'server': 1,
                 'video_id': encode_url(m3u8_match.group(1))}]

    mp4_match = re.search(r'(?:source|src|file|url)\s*[:=]\s*["\']([^"\']+\.mp4[^"\']*)["\']', text, re.I)
    if mp4_match:
        return [{'direct_url': mp4_match.group(1), 'embed_url': player_url, 'type': 'direct', 'server': 1}]

    # 3) Nested iframe
    iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', text)
    if iframe_match:
        src = iframe_match.group(1)
        if src != player_url:
            return [{'embed_url': src, 'type': 'iframe', 'server': 1}]

    return []


def anifume_search(query):
    """Search anime on anifume."""
    url = f"{ANIFUME_BASE}/search/{urllib.parse.quote(query)}"
    r = safe_request(url, 'anifume')
    if not r or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, 'lxml')
    results = []

    for col in soup.select('div.col-p'):
        link = col.select_one('div.col-title a[href]') or col.select_one('div.col-img a[href]')
        if not link:
            continue
        href = link.get('href', '')
        if not href.startswith('http'):
            href = f"{ANIFUME_BASE}{href}"

        slug_match = re.search(r'/(\d+)(?:/|$)', href.rstrip('/'))
        if not slug_match:
            continue
        slug = slug_match.group(1)

        img = col.select_one('div.col-img img') or col.select_one('img')
        image = ''
        if img:
            image = img.get('src', '') or img.get('data-src', '')
            if image and not image.startswith('http'):
                image = f"{ANIFUME_BASE}{image}"

        title_el = col.select_one('div.col-title a')
        title = title_el.get_text(strip=True) if title_el else ''

        if slug not in [r_item['slug'] for r_item in results]:
            results.append({'title': title, 'slug': slug, 'url': href, 'image': image})

    return results


# ============================================================
# SHARED HALIM THEME VIDEO EXTRACTION
# ============================================================
PLAYER_BASE = 'https://main.24playerhd.com'

def _halim_get_video(api_url, post_id, episode, server, referer_base, slug=''):
    """Get video from Halim theme API (works for both series-days and 24-hdmovie)."""
    data = {
        'action': 'halim_ajax_player',
        'episode': str(episode),
        'server': str(server),
        'postid': str(post_id),
        'lang': 'thai',
        'nonce': '',
    }
    r = safe_request(api_url, 'halim', method='POST', data=data, headers={
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f'{referer_base}/{slug}/' if slug else f'{referer_base}/',
        'Origin': referer_base,
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    })
    if not r:
        return None

    text = r.text.strip()
    if 'ไม่พบ' in text or text == 'Error' or not text:
        return None

    iframe_match = re.search(r'src="([^"]+)"', text)
    if not iframe_match:
        return None

    embed_url = iframe_match.group(1)

    id_match = re.search(r'[?&]id=([^&]+)', embed_url)
    if not id_match:
        return {'embed_url': embed_url, 'type': 'iframe', 'server': server}

    video_id = id_match.group(1)

    if 'index_g' in embed_url:
        m3u8_path = f'/newplaylist_g/{video_id}/{video_id}.m3u8'
    else:
        m3u8_path = f'/newplaylist/{video_id}/{video_id}.m3u8'

    return {
        'video_id': video_id,
        'embed_url': embed_url,
        'm3u8_url': f'{PLAYER_BASE}{m3u8_path}',
        'type': 'hls',
        'server': server,
    }


def get_hls_master(video_id, backup=False):
    """Get master m3u8 playlist from 24playerhd and rewrite URLs for proxying."""
    prefix = 'newplaylist_g' if backup else 'newplaylist'
    url = f'{PLAYER_BASE}/{prefix}/{video_id}/{video_id}.m3u8'
    r = safe_request(url, 'hls', headers={
        'Referer': f'{PLAYER_BASE}/',
    })
    if not r or r.status_code != 200:
        return None

    lines = r.text.strip().split('\n')
    rewritten = []
    for line in lines:
        if line.startswith('#'):
            rewritten.append(line)
        elif line.strip():
            variant_match = re.search(r'/m3u8(?:_g)?/([^/]+)/([^/]+\.m3u8)', line.strip())
            if variant_match:
                variant_path = line.strip()
                encoded = encode_url(f'{PLAYER_BASE}{variant_path}')
                rewritten.append(f'/hls/variant/{encoded}')
            else:
                rewritten.append(line.strip())

    return '\n'.join(rewritten) + '\n'


def get_generic_hls_master(m3u8_url, referer=''):
    """Get master m3u8 from any URL and rewrite for proxying."""
    r = safe_request(m3u8_url, 'hls', headers={
        'Referer': referer or m3u8_url.split('/hls/')[0] + '/',
    })
    if not r or r.status_code != 200:
        return None

    base_url = m3u8_url.rsplit('/', 1)[0]
    lines = r.text.strip().split('\n')
    rewritten = []
    for line in lines:
        if line.startswith('#'):
            rewritten.append(line)
        elif line.strip():
            variant_url = line.strip()
            if not variant_url.startswith('http'):
                variant_url = f'{base_url}/{variant_url}'
            encoded = encode_url(variant_url)
            rewritten.append(f'/hls/variant/{encoded}')

    return '\n'.join(rewritten) + '\n'


def get_hls_variant(variant_url):
    """Get variant m3u8 and rewrite segment URLs for proxying."""
    # Determine referer from URL
    referer = f'{PLAYER_BASE}/'
    if 'top-cdn.com' in variant_url:
        referer = 'https://top-cdn.com/'
    elif 'ok-hd.com' in variant_url:
        referer = 'https://ok-hd.com/'
    elif 'anccplayer' in variant_url:
        referer = 'https://anccplayer.cyou/'
    else:
        # Generic: derive referer from URL domain
        try:
            parsed = urllib.parse.urlparse(variant_url)
            referer = f'{parsed.scheme}://{parsed.hostname}/'
        except:
            pass

    r = safe_request(variant_url, 'hls', headers={
        'Referer': referer,
    })
    if not r or r.status_code != 200:
        return None

    base_url = variant_url.rsplit('/', 1)[0]
    lines = r.text.strip().split('\n')
    rewritten = []
    for line in lines:
        if line.startswith('#'):
            # Rewrite key URI in #EXT-X-KEY tags
            key_match = re.search(r'URI="([^"]+)"', line)
            if key_match:
                key_url = key_match.group(1)
                if not key_url.startswith('http'):
                    key_url = f'{base_url}/{key_url}'
                encoded_key = encode_url(key_url)
                line = line.replace(key_match.group(0), f'URI="/hls/segment/{encoded_key}"')
            rewritten.append(line)
        elif line.strip():
            seg_url = line.strip()
            if not seg_url.startswith('http'):
                seg_url = f'{base_url}/{seg_url}'
            encoded = encode_url(seg_url)
            rewritten.append(f'/hls/segment/{encoded}')

    return '\n'.join(rewritten) + '\n'


# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/')
def index():
    return send_file('player.html')


@app.route('/api/sources')
def api_sources():
    return jsonify({
        'sources': [
            {
                'id': 'animegojo',
                'name': 'AnimeGojo',
                'description': 'อนิเมะ ซับไทย/พากย์ไทย',
                'icon': '🎌',
                'categories': list(ANIMEGOJO_CATEGORIES.keys()),
                'type': 'anime',
            },
            {
                'id': 'seriesdays',
                'name': 'Series-Days',
                'description': 'ซีรี่ย์ เกาหลี จีน ฝรั่ง ญี่ปุ่น ไทย',
                'icon': '📺',
                'categories': list(SERIESDAYS_CATEGORIES.keys()),
                'type': 'series',
            },
            {
                'id': 'hdmovie',
                'name': '24-HDMovie',
                'description': 'หนัง HD ทุกแนว',
                'icon': '🎬',
                'categories': list(HDMOVIE_CATEGORIES.keys()),
                'type': 'movie',
            },
            {
                'id': 'wowdrama',
                'name': 'WowDrama',
                'description': 'ซีรี่ย์จีน เกาหลี ญี่ปุ่น ไทย ซับไทย/พากย์ไทย',
                'icon': '🌟',
                'categories': list(WOWDRAMA_CATEGORIES.keys()),
                'type': 'drama',
            },
            {
                'id': 'k35tanmai',
                'name': 'K35Tanmai',
                'description': 'อนิเมะ/การ์ตูน พากย์ไทย ซับไทย HD',
                'icon': '🎭',
                'categories': list(K35TANMAI_CATEGORIES.keys()),
                'type': 'anime',
            },
            {
                'id': 'anifume',
                'name': 'Anifume',
                'description': 'อนิเมะ ซับไทย/พากย์ไทย อัปเดตทุกวัน',
                'icon': '🔥',
                'categories': list(ANIFUME_CATEGORIES.keys()),
                'type': 'anime',
            },
        ]
    })


@app.route('/api/catalog/<source>')
def api_catalog(source):
    page = int(request.args.get('page', 1))
    category = request.args.get('category', 'all')

    if source == 'animegojo':
        return jsonify(animegojo_catalog(page, category))
    elif source == 'seriesdays':
        return jsonify(seriesdays_catalog(page, category))
    elif source == 'hdmovie':
        return jsonify(hdmovie_catalog(page, category))
    elif source == 'wowdrama':
        return jsonify(wowdrama_catalog(page, category))
    elif source == 'k35tanmai':
        return jsonify(k35tanmai_catalog(page, category))
    elif source == 'anifume':
        return jsonify(anifume_catalog(page, category))
    return jsonify({'error': 'Unknown source'}), 404


@app.route('/api/detail/<source>/<path:slug>')
def api_detail(source, slug):
    if source == 'animegojo':
        result = animegojo_detail(slug)
    elif source == 'seriesdays':
        result = seriesdays_detail(slug)
    elif source == 'hdmovie':
        result = hdmovie_detail(slug)
    elif source == 'wowdrama':
        result = wowdrama_detail(slug)
    elif source == 'k35tanmai':
        result = k35tanmai_detail(slug)
    elif source == 'anifume':
        result = anifume_detail(slug)
    else:
        return jsonify({'error': 'Unknown source'}), 404

    if result is None:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(result)


@app.route('/api/episode/<source>/<path:slug>')
def api_episode(source, slug):
    """Get video servers for a specific episode."""
    if source == 'animegojo':
        result = animegojo_episode(slug)
        return jsonify(result) if result else (jsonify({'error': 'Not found'}), 404)

    elif source == 'k35tanmai':
        result = k35tanmai_episode(slug)
        return jsonify(result) if result else (jsonify({'error': 'Not found'}), 404)

    elif source == 'anifume':
        result = anifume_episode(slug)
        return jsonify(result) if result else (jsonify({'error': 'Not found'}), 404)

    elif source == 'wowdrama':
        result = wowdrama_episode(slug)
        return jsonify(result) if result else (jsonify({'error': 'Not found'}), 404)

    elif source in ('seriesdays', 'hdmovie'):
        ep_match = re.match(r'(\d+)-ep-(\d+)', slug)
        if ep_match:
            post_id = ep_match.group(1)
            episode = ep_match.group(2)
        else:
            post_id = slug
            episode = '1'

        api_url = SERIESDAYS_API if source == 'seriesdays' else HDMOVIE_API
        base_url = SERIESDAYS_BASE if source == 'seriesdays' else HDMOVIE_BASE

        servers = []
        for srv_num in range(1, 4):
            video = _halim_get_video(api_url, post_id, episode, srv_num, base_url, slug)
            if video:
                servers.append(video)

        ep_num = int(episode)
        result = {
            'post_id': post_id,
            'episode': episode,
            'servers': servers,
            'next_episode': f'{post_id}-ep-{ep_num + 1}',
        }

        if result.get('servers'):
            result['videos'] = result['servers']
        return jsonify(result) if result.get('servers') else (jsonify({'error': 'Video not found'}), 404)

    return jsonify({'error': 'Unknown source'}), 404


@app.route('/api/video/<source>/<post_id>/<int:server>')
def api_video(source, post_id, server):
    """Get video URL for a specific server."""
    episode = int(request.args.get('episode', 1))

    if source == 'animegojo':
        return jsonify({'error': 'Use episode endpoint'}), 400
    elif source == 'seriesdays':
        result = seriesdays_get_video(post_id, episode, server)
    elif source == 'hdmovie':
        result = hdmovie_get_video(post_id, episode, server)
    elif source == 'wowdrama':
        result = wowdrama_episode(post_id)
        if result and result.get('videos'):
            result = result['videos'][0] if result['videos'] else None
        else:
            result = None
    else:
        return jsonify({'error': 'Unknown source'}), 404

    if result is None:
        return jsonify({'error': 'Video not found'}), 404
    return jsonify(result)


@app.route('/api/search/<source>')
def api_search(source):
    query = request.args.get('q', '')
    if not query:
        return jsonify([])

    if source == 'animegojo':
        return jsonify(animegojo_search(query))
    elif source == 'seriesdays':
        return jsonify(_search_wp_api(SERIESDAYS_BASE, query, 'seriesdays'))
    elif source == 'hdmovie':
        return jsonify(_search_halim(HDMOVIE_BASE, query, 'hdmovie'))
    elif source == 'wowdrama':
        return jsonify(wowdrama_search(query))
    elif source == 'k35tanmai':
        return jsonify(k35tanmai_search(query))
    elif source == 'anifume':
        return jsonify(anifume_search(query))
    return jsonify([])


def _search_wp_api(base_url, query, site_key):
    """Search via WordPress REST API."""
    url = f"{base_url}/wp-json/wp/v2/posts?search={urllib.parse.quote(query)}&per_page=20"
    r = safe_request(url, site_key, headers={'Accept': 'application/json'})
    if not r or r.status_code != 200:
        return []
    try:
        posts = r.json()
        results = []
        for post in posts:
            slug = post.get('slug', '')
            if not slug:
                continue
            title = post.get('title', {}).get('rendered', slug)
            title = re.sub(r'<[^>]+>', '', title).strip()
            image = ''
            if post.get('_embedded', {}).get('wp:featuredmedia'):
                media = post['_embedded']['wp:featuredmedia'][0]
                image = media.get('source_url', '')
            results.append({
                'title': title,
                'slug': slug,
                'url': post.get('link', f'{base_url}/{slug}/'),
                'image': image,
            })
        return results
    except:
        return []


def _search_halim(base_url, query, site_key):
    """Search Halim theme sites."""
    url = f"{base_url}/?s={urllib.parse.quote(query)}"
    r = safe_request(url, site_key)
    if not r or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, 'lxml')
    results = []

    for box in soup.select('div.box'):
        link = box.select_one('a[href]')
        if not link:
            continue
        href = link.get('href', '')
        slug = href.rstrip('/').split('/')[-1]
        if not slug:
            continue

        img = box.select_one('img')
        image = ''
        if img:
            image = img.get('data-lazy-src', '') or img.get('src', '') or img.get('data-src', '')

        title_el = box.select_one('.p2')
        title = title_el.get_text(strip=True) if title_el else (img.get('alt', '') if img else slug)

        results.append({
            'title': title,
            'slug': slug,
            'url': href,
            'image': image,
        })

    if not results:
        for article in soup.select('.halim-item, article.item, .halim_box, .search-item'):
            link = article.select_one('a[href]')
            img = article.select_one('img')
            title_el = article.select_one('.halim-post-title-box a, .entry-title a, .title a, h3 a, h2 a')

            if link:
                href = link.get('href', '')
                slug = href.rstrip('/').split('/')[-1]
                title = title_el.get_text(strip=True) if title_el else slug
                image = ''
                if img:
                    image = img.get('src', '') or img.get('data-src', '') or img.get('data-original', '')
                results.append({
                    'title': title,
                    'slug': slug,
                    'url': href,
                    'image': image,
                })

    seen = set()
    unique = []
    for r_item in results:
        if r_item['slug'] not in seen:
            seen.add(r_item['slug'])
            unique.append(r_item)
    return unique


# ============================================================
# HLS PROXY ROUTES
# ============================================================

@app.route('/hls/master/<video_id>')
def hls_master(video_id):
    """Proxy master m3u8 playlist (24playerhd)."""
    backup = request.args.get('backup', '0') == '1'
    content = get_hls_master(video_id, backup)
    if content is None:
        return 'Not found', 404
    return Response(content, content_type='application/vnd.apple.mpegurl',
                    headers={'Access-Control-Allow-Origin': '*'})


@app.route('/hls/topcdn/<hash_id>')
def hls_topcdn(hash_id):
    """Proxy master m3u8 from top-cdn.com or ok-hd.com."""
    cdn = request.args.get('cdn', 'top-cdn.com')
    m3u8_url = f'https://{cdn}/hls/{hash_id}/master.m3u8'
    content = get_generic_hls_master(m3u8_url, f'https://{cdn}/')
    if content is None:
        return 'Not found', 404
    return Response(content, content_type='application/vnd.apple.mpegurl',
                    headers={'Access-Control-Allow-Origin': '*'})


@app.route('/hls/ancc/<link2>')
def hls_ancc(link2):
    """Proxy master m3u8 from anccplayer (AnimeGojo)."""
    m3u8_url = f'https://youtube.anccplayer.cyou/playg.php?uid={link2}'
    content = get_generic_hls_master(m3u8_url, 'https://anccplayer.cyou/')
    if content is None:
        return 'Not found', 404
    return Response(content, content_type='application/vnd.apple.mpegurl',
                    headers={'Access-Control-Allow-Origin': '*'})


@app.route('/hls/generic/<encoded_url>')
def hls_generic(encoded_url):
    """Proxy master m3u8 from any URL (base64 url-safe encoded)."""
    url = decode_url(encoded_url)
    if not url:
        return 'Invalid URL', 400
    # Auto-detect referer from URL domain
    try:
        parsed = urllib.parse.urlparse(url)
        referer = f'{parsed.scheme}://{parsed.hostname}/'
    except:
        referer = ''
    content = get_generic_hls_master(url, referer)
    if content is None:
        return 'Not found', 404
    return Response(content, content_type='application/vnd.apple.mpegurl',
                    headers={'Access-Control-Allow-Origin': '*'})


@app.route('/hls/variant/<encoded_url>')
def hls_variant(encoded_url):
    """Proxy variant m3u8 playlist."""
    url = decode_url(encoded_url)
    if not url:
        return 'Invalid URL', 400
    content = get_hls_variant(url)
    if content is None:
        return 'Not found', 404
    return Response(content, content_type='application/vnd.apple.mpegurl',
                    headers={'Access-Control-Allow-Origin': '*'})


@app.route('/hls/segment/<encoded_url>')
def hls_segment(encoded_url):
    """Proxy video segment."""
    url = decode_url(encoded_url)
    if not url:
        return 'Invalid URL', 400

    # Determine referer from URL
    referer = f'{PLAYER_BASE}/'
    if 'top-cdn.com' in url:
        referer = 'https://top-cdn.com/'
    elif 'ok-hd.com' in url:
        referer = 'https://ok-hd.com/'
    elif 'anccplayer' in url:
        referer = 'https://anccplayer.cyou/'
    else:
        try:
            parsed = urllib.parse.urlparse(url)
            referer = f'{parsed.scheme}://{parsed.hostname}/'
        except:
            pass

    r = safe_request(url, 'hls', headers={
        'Referer': referer,
    }, stream=True)
    if not r or r.status_code != 200:
        return 'Segment not found', 404

    def generate():
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                yield chunk

    ct = r.headers.get('Content-Type', 'video/mp2t')
    return Response(generate(), content_type=ct,
                    headers={
                        'Access-Control-Allow-Origin': '*',
                        'Cache-Control': 'public, max-age=3600',
                    })


# ============================================================
# IMAGE PROXY
# ============================================================

@app.route('/proxy/image')
def proxy_image():
    """Proxy images to hide user IP from source sites."""
    url = request.args.get('url', '')
    if not url:
        return 'No URL', 400

    referer = ''
    if 'animegojo' in url:
        referer = ANIMEGOJO_BASE
    elif 'series-days' in url:
        referer = SERIESDAYS_BASE
    elif '24-hdmovie' in url:
        referer = HDMOVIE_BASE
    elif 'wow-drama' in url:
        referer = WOWDRAMA_BASE
    elif 'k35tanmai' in url:
        referer = K35TANMAI_BASE
    elif 'anifume' in url:
        referer = ANIFUME_BASE

    r = safe_request(url, 'images', headers={
        'Referer': referer + '/' if referer else '',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    })
    if not r or r.status_code != 200:
        return Response(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
            content_type='image/png'
        )

    ct = r.headers.get('Content-Type', 'image/jpeg')
    return Response(r.content, content_type=ct,
                    headers={
                        'Cache-Control': 'public, max-age=86400',
                        'Access-Control-Allow-Origin': '*',
                    })


# ============================================================
# CORS SUPPORT
# ============================================================

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Requested-With'
    return response


# ============================================================
# TELEGRAM NOTIFICATION
# ============================================================
TELEGRAM_BOT_TOKEN = '8343329630:AAEbZlijpYGFntPI0t-0JJ55i-fHLIc1Qkg'
TELEGRAM_CHAT_ID = '8533317860'

def send_telegram(message):
    """Send a Telegram notification."""
    try:
        import requests
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}, timeout=10)
    except:
        pass

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    import socket
    port = int(os.environ.get('PORT', 5555))
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("=" * 60)
    print("  STREAMING PROXY SERVER")
    print("=" * 60)
    print(f"  PC:     http://localhost:{port}")
    print(f"  Mobile: http://{local_ip}:{port}")
    print(f"  Sources: AnimeGojo | Series-Days | 24-HDMovie | WowDrama | K35Tanmai | Anifume")
    print("=" * 60)

    send_telegram(f"🎬 Server started\nPC: http://localhost:{port}\nMobile: http://{local_ip}:{port}")

    try:
        from waitress import serve
        print("  [OK] Using waitress WSGI server (stable mode)")
        print("  Press Ctrl+C to stop")
        print("=" * 60)
        serve(app, host='0.0.0.0', port=port,
              threads=8,
              connection_limit=500,
              channel_timeout=120,
              recv_bytes=65536)
    except ImportError:
        print("  [WARN] waitress not found, falling back to Flask dev server")
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
