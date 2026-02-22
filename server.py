#!/usr/bin/env python3
"""
Multi-Source Streaming Proxy Server
Sources: animeruka.com, series-days.com, 24-hdmovie.com
Features: HLS proxy, privacy protection, auto-next, stall recovery
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
# ANIMERUKA.COM SCRAPER (DooPlay Theme)
# ============================================================
ANIMERUKA_BASE = 'https://animeruka.com'
ANIMERUKA_API = f'{ANIMERUKA_BASE}/wp-json/dooplayer/v2'

ANIMERUKA_CATEGORIES = {
    'all': '/anime/',
    'ซับไทย': '/catalog/ซับไทย/',
    'พากย์ไทย': '/catalog/พากย์ไทย/',
    'action': '/genre/action/',
    'adventure': '/genre/adventure/',
    'comedy': '/genre/comedy/',
    'drama': '/genre/drama/',
    'fantasy': '/genre/fantasy/',
    'horror': '/genre/horror/',
    'isekai': '/genre/isekai/',
    'mecha': '/genre/mecha/',
    'mystery': '/genre/mystery/',
    'romance': '/genre/romance/',
    'school': '/genre/school/',
    'sci-fi': '/genre/sci-fi/',
    'shounen': '/genre/shounen/',
    'slice-of-life': '/genre/slice-of-life/',
    'sports': '/genre/sports/',
    'supernatural': '/genre/supernatural/',
}

def animeruka_catalog(page=1, category='all'):
    """Get anime catalog from animeruka."""
    cat_path = ANIMERUKA_CATEGORIES.get(category, '/anime/')
    url = f"{ANIMERUKA_BASE}{cat_path}page/{page}/"
    r = safe_request(url, 'animeruka')
    if not r or r.status_code != 200:
        return {'items': [], 'page': page, 'has_next': False}

    soup = BeautifulSoup(r.text, 'lxml')
    items = []
    for article in soup.select('article.item'):
        # DooPlay: <article class="item"> <div class="poster"> <img> <a><h3><div class="movie-title">
        link = article.select_one('.poster a, a[href]')
        img = article.select_one('img')
        # Title in movie-title div inside h3 inside a
        title_el = article.select_one('.movie-title, h3, .data h3')
        quality = article.select_one('.quality, .features-type')
        ep_status = article.select_one('.features-status')

        if link:
            href = link.get('href', '')
            slug = href.rstrip('/').split('/')[-1] if href else ''
            title = title_el.get_text(strip=True) if title_el else slug
            image = ''
            if img:
                image = img.get('src', '') or img.get('data-src', '') or img.get('data-lazy-src', '')
            item = {
                'title': title,
                'slug': slug,
                'url': href,
                'image': image,
                'quality': quality.get_text(strip=True) if quality else '',
                'status': ep_status.get_text(strip=True) if ep_status else '',
            }
            items.append(item)

    # Check for next page
    has_next = bool(soup.select_one('.pagination .next, .nav-next, a.arrow_pag[href]'))
    # Also check for numbered pagination
    if not has_next:
        has_next = bool(re.search(rf'page/{page + 1}/', r.text))

    return {'items': items, 'page': page, 'has_next': has_next}


def animeruka_detail(slug):
    """Get anime detail with episode list."""
    url = f"{ANIMERUKA_BASE}/anime/{slug}/"
    r = safe_request(url, 'animeruka')
    if not r or r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, 'lxml')

    # Get title and info
    title = ''
    title_el = soup.select_one('.sheader .data h1')
    if title_el:
        title = title_el.get_text(strip=True)

    # Get poster image
    poster = ''
    poster_el = soup.select_one('.sheader .poster img')
    if poster_el:
        poster = poster_el.get('src', '') or poster_el.get('data-src', '')

    # Get synopsis
    synopsis = ''
    syn_el = soup.select_one('#info .wp-content p, .description p')
    if syn_el:
        synopsis = syn_el.get_text(strip=True)[:500]

    # Get episodes from seasons section
    episodes = []
    # DooPlay uses single-quoted attributes in inline HTML
    ep_pattern = re.compile(r"<a\s+href=['\"]([^'\"]*?/ep/[^'\"]*?)['\"]", re.I)
    for match in ep_pattern.finditer(r.text):
        ep_url = match.group(1)
        ep_num_match = re.search(r'ep-?(\d+)', ep_url)
        ep_num = ep_num_match.group(1) if ep_num_match else str(len(episodes) + 1)
        episodes.append({
            'number': int(ep_num),
            'url': ep_url,
            'slug': ep_url.rstrip('/').split('/')[-1],
        })

    # Also try season episode list
    if not episodes:
        for li in soup.select('#seasons .se-a li, .episodios li'):
            a = li.select_one('a')
            if a:
                href = a.get('href', '')
                ep_num_match = re.search(r'ep-?(\d+)', href)
                ep_num = ep_num_match.group(1) if ep_num_match else str(len(episodes) + 1)
                episodes.append({
                    'number': int(ep_num),
                    'url': href,
                    'slug': href.rstrip('/').split('/')[-1],
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


def animeruka_episode(slug):
    """Get video servers for an episode."""
    url = f"{ANIMERUKA_BASE}/ep/{slug}/"
    r = safe_request(url, 'animeruka')
    if not r or r.status_code != 200:
        return None

    # Extract post ID and player options (single-quoted in DooPlay)
    post_id_match = re.search(r"data-post=['\"](\d+)['\"]", r.text)
    post_id = post_id_match.group(1) if post_id_match else None

    if not post_id:
        # Try from body class
        body_match = re.search(r'postid-(\d+)', r.text)
        post_id = body_match.group(1) if body_match else None

    servers = []
    option_pattern = re.compile(
        r"data-type=['\"]([^'\"]*)['\"][^>]*data-post=['\"](\d+)['\"][^>]*data-nume=['\"](\d+)['\"]"
    )
    for m in option_pattern.finditer(r.text):
        servers.append({
            'type': m.group(1),
            'post_id': m.group(2),
            'server': int(m.group(3)),
        })

    # If no servers found in regex, try reverse attribute order
    if not servers:
        option_pattern2 = re.compile(
            r"data-post=['\"](\d+)['\"][^>]*data-(?:type|num|nume)=['\"]([^'\"]*)['\"]"
        )
        for m in option_pattern2.finditer(r.text):
            servers.append({
                'post_id': m.group(1),
                'server': len(servers) + 1,
                'type': 'tv',
            })

    # Get next episode link
    next_ep = None
    next_match = re.search(r'<a\s+href=["\']([^"\']*?/ep/[^"\']*?)["\'][^>]*>\s*(?:<span>)?ตอนต่อไป', r.text)
    if next_match:
        next_url = next_match.group(1)
        next_slug = next_url.rstrip('/').split('/')[-1]
        next_ep = next_slug

    # Get anime page link (for going back to episode list)
    anime_link = None
    anime_match = re.search(r'href=["\']([^"\']*?/anime/[^"\']*?)["\']', r.text)
    if anime_match:
        anime_link = anime_match.group(1)

    return {
        'post_id': post_id,
        'servers': servers,
        'next_episode': next_ep,
        'anime_url': anime_link,
    }


def animeruka_video(post_id, server=1):
    """Get video embed URL from DooPlay API."""
    url = f"{ANIMERUKA_API}/{post_id}/tv/{server}"
    r = safe_request(url, 'animeruka', headers={
        'Accept': 'application/json',
        'Referer': f'{ANIMERUKA_BASE}/',
    })
    if not r:
        return None
    try:
        data = r.json()
        embed_url = data.get('embed_url', '')
        return {
            'embed_url': embed_url,
            'type': data.get('type', 'iframe'),
            'server': server,
        }
    except:
        return None


def animeruka_search(query):
    """Search anime on animeruka via search page scraping."""
    url = f"{ANIMERUKA_BASE}/?s={urllib.parse.quote(query)}"
    r = safe_request(url, 'animeruka')
    if not r or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, 'lxml')
    results = []

    for item in soup.select('.result-item'):
        link = item.select_one('a[href*="/anime/"]')
        if not link:
            continue
        href = link.get('href', '')
        slug = href.rstrip('/').split('/')[-1]
        if not slug:
            continue

        title_el = item.select_one('.title a')
        title = title_el.get_text(strip=True) if title_el else slug

        img = item.select_one('img')
        image = ''
        if img:
            image = img.get('src', '') or img.get('data-src', '')

        if slug not in [r['slug'] for r in results]:
            results.append({
                'title': title,
                'slug': slug,
                'url': href,
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

    # Custom Halim theme: <div class="box"><a href><div class="box-img"><img data-lazy-src>
    # <div class="p-box"><div class="p1">ซับไทย</div><div class="p2">Title</div></div></a></div>
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

    # Deduplicate
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

    # Use og:title for correct title (h1 is site title on Halim theme)
    title = ''
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        title = og_title.get('content', '').strip()
    if not title:
        title_tag = soup.select_one('title')
        if title_tag:
            title = title_tag.get_text(strip=True).split(' - ')[0].split(' | ')[0].strip()

    # Use og:image for poster
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

    # Get post ID from halim_cfg
    post_id = None
    cfg_match = re.search(r'"post_id"\s*:\s*(\d+)', r.text)
    if cfg_match:
        post_id = cfg_match.group(1)
    if not post_id:
        btn = soup.select_one('[data-post-id]')
        if btn:
            post_id = btn.get('data-post-id')

    # Discover episode count from the page
    max_ep = 0

    # Method 1: Look for ep-N links in the HTML
    ep_nums_from_links = re.findall(re.escape(slug) + r'-ep-?(\d+)', r.text)
    if ep_nums_from_links:
        max_ep = max(int(n) for n in ep_nums_from_links)

    # Method 2: Look for episode number text patterns
    if max_ep == 0:
        ep_text_nums = re.findall(r'(?:EP|ตอนที่|ตอน)\s*[.\s]*(\d+)', r.text, re.I)
        if ep_text_nums:
            max_ep = max(int(n) for n in ep_text_nums)

    # Method 3: Default 1 episode
    if max_ep == 0:
        max_ep = 1

    # Generate episodes using post_id-ep-N pattern
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
    """Get video for a series-days episode.
    Slug format: {post_id}-ep-{episode_number}
    """
    # Parse post_id and episode from slug
    ep_match = re.match(r'(\d+)-ep-(\d+)', slug)
    if ep_match:
        post_id = ep_match.group(1)
        episode = ep_match.group(2)
    else:
        # Fallback: try loading the page
        url = f"{SERIESDAYS_BASE}/{slug}/"
        r = safe_request(url, 'seriesdays')
        if not r or r.status_code != 200:
            return None
        cfg_match = re.search(r'"post_id"\s*:\s*(\d+)', r.text)
        post_id = cfg_match.group(1) if cfg_match else None
        episode = '1'
        if not post_id:
            return None

    # Get video from all servers
    servers = []
    for server_num in range(1, 4):
        result = _halim_get_video(SERIESDAYS_API, post_id, episode, server_num, SERIESDAYS_BASE, slug)
        if result:
            servers.append(result)

    # Calculate next episode slug
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

    # Same box structure as series-days
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

    # Use og:title for correct title
    title = ''
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        title = og_title.get('content', '').strip()
    if not title:
        title_tag = soup.select_one('title')
        if title_tag:
            title = title_tag.get_text(strip=True).split(' - ')[0].split(' | ')[0].strip()

    # Use og:image for poster
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

    # Get post ID from halim_cfg
    post_id = None
    cfg_match = re.search(r'"post_id"\s*:\s*(\d+)', r.text)
    if cfg_match:
        post_id = cfg_match.group(1)
    if not post_id:
        btn = soup.select_one('[data-post-id]')
        if btn:
            post_id = btn.get('data-post-id')

    # Discover episode count
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

    # Generate episodes using post_id-ep-N pattern
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

    # Extract iframe src
    iframe_match = re.search(r'src="([^"]+)"', text)
    if not iframe_match:
        return None

    embed_url = iframe_match.group(1)

    # Extract video ID from embed URL
    id_match = re.search(r'[?&]id=([^&]+)', embed_url)
    if not id_match:
        return {'embed_url': embed_url, 'type': 'iframe', 'server': server}

    video_id = id_match.group(1)

    # Determine m3u8 path based on player URL
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
    """Get master m3u8 playlist and rewrite URLs for proxying."""
    prefix = 'newplaylist_g' if backup else 'newplaylist'
    url = f'{PLAYER_BASE}/{prefix}/{video_id}/{video_id}.m3u8'
    r = safe_request(url, 'hls', headers={
        'Referer': f'{PLAYER_BASE}/',
    })
    if not r or r.status_code != 200:
        return None

    # Rewrite quality variant URLs to proxy through us
    lines = r.text.strip().split('\n')
    rewritten = []
    for line in lines:
        if line.startswith('#'):
            rewritten.append(line)
        elif line.strip():
            # e.g. /m3u8/{id}/{id}438.m3u8
            variant_match = re.search(r'/m3u8(?:_g)?/([^/]+)/([^/]+\.m3u8)', line.strip())
            if variant_match:
                variant_path = line.strip()
                encoded = encode_url(f'{PLAYER_BASE}{variant_path}')
                rewritten.append(f'/hls/variant/{encoded}')
            else:
                rewritten.append(line.strip())

    return '\n'.join(rewritten) + '\n'


def get_hls_variant(variant_url):
    """Get variant m3u8 and rewrite segment URLs for proxying."""
    r = safe_request(variant_url, 'hls', headers={
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
            seg_url = line.strip()
            if not seg_url.startswith('http'):
                # Relative URL - make absolute
                base = variant_url.rsplit('/', 1)[0]
                seg_url = f'{base}/{seg_url}'
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
                'id': 'animeruka',
                'name': 'AnimeRuka',
                'description': 'อนิเมะ ซับไทย/พากย์ไทย',
                'icon': '🎌',
                'categories': list(ANIMERUKA_CATEGORIES.keys()),
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
        ]
    })


@app.route('/api/catalog/<source>')
def api_catalog(source):
    page = int(request.args.get('page', 1))
    category = request.args.get('category', 'all')

    if source == 'animeruka':
        return jsonify(animeruka_catalog(page, category))
    elif source == 'seriesdays':
        return jsonify(seriesdays_catalog(page, category))
    elif source == 'hdmovie':
        return jsonify(hdmovie_catalog(page, category))
    return jsonify({'error': 'Unknown source'}), 404


@app.route('/api/detail/<source>/<slug>')
def api_detail(source, slug):
    if source == 'animeruka':
        result = animeruka_detail(slug)
    elif source == 'seriesdays':
        result = seriesdays_detail(slug)
    elif source == 'hdmovie':
        result = hdmovie_detail(slug)
    else:
        return jsonify({'error': 'Unknown source'}), 404

    if result is None:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(result)


@app.route('/api/episode/<source>/<slug>')
def api_episode(source, slug):
    """Get video servers for a specific episode."""
    if source == 'animeruka':
        result = animeruka_episode(slug)
        if result and result.get('servers'):
            # For each server, get the embed URL
            videos = []
            for srv in result['servers'][:3]:  # Max 3 servers
                video = animeruka_video(srv['post_id'], srv['server'])
                if video:
                    videos.append(video)
            result['videos'] = videos
        return jsonify(result) if result else (jsonify({'error': 'Not found'}), 404)

    elif source in ('seriesdays', 'hdmovie'):
        # Both Halim sites use {post_id}-ep-{N} slug format
        ep_match = re.match(r'(\d+)-ep-(\d+)', slug)
        if ep_match:
            post_id = ep_match.group(1)
            episode = ep_match.group(2)
        else:
            # Fallback for old-style slugs
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

    if source == 'animeruka':
        result = animeruka_video(post_id, server)
    elif source == 'seriesdays':
        result = seriesdays_get_video(post_id, episode, server)
    elif source == 'hdmovie':
        result = hdmovie_get_video(post_id, episode, server)
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

    if source == 'animeruka':
        return jsonify(animeruka_search(query))
    elif source == 'seriesdays':
        # Use WP REST API for search (standard search returns empty)
        return jsonify(_search_wp_api(SERIESDAYS_BASE, query, 'seriesdays'))
    elif source == 'hdmovie':
        return jsonify(_search_halim(HDMOVIE_BASE, query, 'hdmovie'))
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
            # Clean HTML from title
            title = re.sub(r'<[^>]+>', '', title).strip()
            # Get featured image
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

    # Try div.box selectors first (custom Halim layout)
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

    # Fallback to standard Halim selectors
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

    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        if r['slug'] not in seen:
            seen.add(r['slug'])
            unique.append(r)
    return unique


# ============================================================
# HLS PROXY ROUTES
# ============================================================

@app.route('/hls/master/<video_id>')
def hls_master(video_id):
    """Proxy master m3u8 playlist."""
    backup = request.args.get('backup', '0') == '1'
    content = get_hls_master(video_id, backup)
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

    r = safe_request(url, 'hls', headers={
        'Referer': f'{PLAYER_BASE}/',
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

    # Determine referer based on URL
    referer = ''
    if 'animeruka' in url:
        referer = ANIMERUKA_BASE
    elif 'series-days' in url:
        referer = SERIESDAYS_BASE
    elif '24-hdmovie' in url:
        referer = HDMOVIE_BASE

    r = safe_request(url, 'images', headers={
        'Referer': referer + '/',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    })
    if not r or r.status_code != 200:
        # Return 1x1 transparent pixel
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
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("=" * 60)
    print("  STREAMING PROXY SERVER")
    print("=" * 60)
    print(f"  PC:     http://localhost:5555")
    print(f"  Mobile: http://{local_ip}:5555")
    print(f"  Sources: AnimeRuka | Series-Days | 24-HDMovie")
    print("=" * 60)

    send_telegram(f"🎬 Server started\nPC: http://localhost:5555\nMobile: http://{local_ip}:5555")

    app.run(host='0.0.0.0', port=5555, debug=False, threaded=True)
