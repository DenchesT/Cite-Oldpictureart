import asyncio
import os
import re
import json
import shutil
import subprocess
from telethon import TelegramClient, connection
from datetime import datetime

# ==================== НАСТРОЙКИ ====================
API_ID = 123456        # Твой api_id (число)
API_HASH = "твой_hash"  # Твой api_hash (строка)

CHANNEL_URL = "https://t.me/oldpictureart"
OUTPUT_DIR = "output"
IMAGES_DIR = "output/images"
TEMPLATE_FILE = "template.html"
PROCESSED_FILE = "processed_ids.json"

PROXY = (
    '138.226.236.46',
    8443,
    'ee5a76b164eadb451a845bfae212bf8649706574726f766963682e7275'
)
# ===================================================

def push_to_github():
    """Автоматически отправляет обновления на GitHub"""
    print("\n📤 Отправляю обновления на GitHub...")
    
    try:
        # 1. Копируем index.html из output в корень (для GitHub Pages)
        shutil.copy2(os.path.join(OUTPUT_DIR, "index.html"), "index.html")
        print("   ✅ index.html скопирован в корень")
        
        # 2. Добавляем все изменённые файлы
        result = subprocess.run(["git", "add", "."], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ⚠️ git add: {result.stderr}")
        else:
            print("   ✅ Файлы добавлены в Git")
        
        # 3. Проверяем, есть ли изменения
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not result.stdout.strip():
            print("   ℹ️ Нет изменений для отправки")
            return
        
        # 4. Коммитим изменения
        commit_msg = f"Авто-обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        result = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ⚠️ git commit: {result.stderr}")
        else:
            print(f"   ✅ Закоммичено: {commit_msg}")
        
        # 5. Пушим на GitHub
        result = subprocess.run(["git", "push"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ⚠️ git push: {result.stderr}")
        else:
            print("   ✅ Отправлено на GitHub!")
            print("   🌐 Сайт обновится через 1-2 минуты: https://denchest.github.io/Cite-01dpictureart/")
            
    except Exception as e:
        print(f"   ❌ Ошибка при отправке на GitHub: {e}")

def load_template():
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        return f.read()

def clean_title(text):
    title = text.split("\n")[0]
    title = re.sub(r'\*\*|__|##|`', '', title)
    title = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', title)
    title = re.sub(r'#\w+', '', title)
    return title.strip()

def is_artist_post(text):
    """Проверяет, является ли пост постом с картиной"""
    if not text:
        return False
    
    lines = text.strip().split("\n")
    
    has_separator = any("⸻" in line or "⸺" in line for line in lines)
    has_link = "https://" in text
    has_artist = len(lines) >= 3 and len(lines[0]) > 3 and not lines[0].startswith("#")
    has_tags = "#" in text
    
    if has_separator and has_link and has_artist and has_tags:
        return True
    
    return False

def slugify(text):
    title = clean_title(text)
    slug = "".join(c if c.isalnum() or c.isspace() else "" for c in title)
    slug = slug.strip().replace(" ", "-").lower()
    return slug[:60].rstrip("-") or "post"

def extract_tags(text):
    return list(set(re.findall(r'#(\w+)', text)))

def telegram_to_html(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<em>\1</em>', text)
    text = re.sub(r'[⸻]{3,}|[-_]{3,}', r'<hr>', text)
    text = re.sub(r'#(\w+)', r'<a href="tag-\1.html" class="tag">#\1</a>', text)
    text = text.replace("\n\n", "</p><p>")
    return text

def load_processed_ids():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_processed_ids(ids):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)

async def download_media(client, message, post_slug):
    if not message.media:
        return ""
    
    try:
        ext = ".jpg"
        filename = f"{post_slug}{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)
        
        if not os.path.exists(filepath):
            await client.download_media(message, filepath)
        
        return f'<img src="images/{filename}" alt="{clean_title(message.text)}" class="post-image">'
    except Exception as e:
        print(f"    ⚠️ Не удалось скачать медиа: {e}")
        return ""

def build_post(post, template, media_html):
    title = clean_title(post["text"])
    content = telegram_to_html(post["text"])
    tags = extract_tags(post["text"])
    
    tags_html = ""
    if tags:
        tags_html = '<div class="tags">🏷 ' + " ".join(
            [f'<a href="tag-{tag}.html" class="tag">#{tag}</a>' for tag in sorted(tags)]
        ) + '</div>'
    
    html = template
    html = html.replace("{{title}}", title)
    html = html.replace("{{date}}", post["date"])
    html = html.replace("{{media}}", media_html)
    html = html.replace("{{content}}", f"<p>{content}</p>")
    html = html.replace("{{tags}}", tags_html)
    
    filename = f"{post['date']}-{slugify(post['text'])}.html"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    
    return filename, title, post["date"], tags

def build_index(posts_meta):
    cards = ""
    for filename, title, date, tags in reversed(posts_meta):
        tags_html = ""
        if tags:
            tags_html = '<div class="card-tags">' + " ".join(
                [f'<a href="tag-{tag}.html">#{tag}</a>' for tag in sorted(tags[:3])]
            ) + '</div>'
        
        cards += f"""
        <article class="card">
            <h3><a href="{filename}">{title}</a></h3>
            <time>{date}</time>
            {tags_html}
        </article>"""
    
    years = sorted(set(date.split("-")[0] for _, _, date, _ in posts_meta), reverse=True)
    months = sorted(set(date[:7] for _, _, date, _ in posts_meta), reverse=True)
    
    years_nav = "\n".join([f'<li><a href="year-{y}.html">{y}</a></li>' for y in years])
    months_nav = "\n".join([f'<li><a href="month-{m}.html">{m}</a></li>' for m in months[:12]])
    
    index_html = f"""<!DOCTYPE html>
<html lang="ru" data-theme="light">
<head>
    <meta charset="UTF-8">
    <title>Old Picture Art — Галерея</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <style>
        :root {{ --pico-font-size: 100%; }}
        body {{ max-width: 1000px; margin: 0 auto; padding: 1rem; }}
        .layout {{ display: grid; grid-template-columns: 1fr 200px; gap: 2rem; }}
        .sidebar {{ background: #f8f9fa; padding: 1rem; border-radius: 8px; height: fit-content; position: sticky; top: 1rem; }}
        .sidebar h4 {{ margin-top: 0; }}
        .sidebar ul {{ list-style: none; padding: 0; }}
        .card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }}
        .card {{ padding: 1rem; border: 1px solid #e0e0e0; border-radius: 8px; }}
        .card h3 {{ margin: 0 0 0.5rem 0; font-size: 1.1rem; }}
        .card h3 a {{ text-decoration: none; color: #2c3e50; }}
        .card time {{ color: #888; font-size: 0.85rem; }}
        .card-tags {{ margin-top: 0.5rem; }}
        .search-box {{ width: 100%; padding: 0.5rem; margin-bottom: 1rem; border: 1px solid #ddd; border-radius: 4px; }}
        @media (max-width: 768px) {{ .layout {{ grid-template-columns: 1fr; }} .sidebar {{ position: static; }} }}
    </style>
</head>
<body>
    <header>
        <h1>🖼 Old Picture Art</h1>
        <input type="text" class="search-box" placeholder="🔍 Поиск..." id="search">
        <p>Постов: {len(posts_meta)}</p>
    </header>
    <div class="layout">
        <main><div class="card-grid" id="cards">{cards}</div></main>
        <aside class="sidebar">
            <h4>📅 По годам</h4><ul>{years_nav}</ul>
            <h4>📆 По месяцам</h4><ul>{months_nav}</ul>
        </aside>
    </div>
    <script>
        document.getElementById('search').addEventListener('input', function(e) {{
            const q = e.target.value.toLowerCase();
            document.querySelectorAll('.card').forEach(card => {{
                card.style.display = card.textContent.toLowerCase().includes(q) ? '' : 'none';
            }});
        }});
    </script>
</body>
</html>"""
    
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

def build_tag_pages(all_tags, posts_meta):
    for tag in all_tags:
        tag_posts = [(f, t, d) for f, t, d, tags in posts_meta if tag in tags]
        links = "".join(f'<li><a href="{f}">{t}</a> <small>{d}</small></li>' for f, t, d in tag_posts)
        
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>#{tag}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
</head>
<body style="max-width:800px;margin:0 auto;padding:2rem;">
    <a href="index.html">← Назад</a>
    <h1>🏷 #{tag}</h1>
    <p>Постов: {len(tag_posts)}</p>
    <ul>{links}</ul>
</body>
</html>"""
        
        with open(os.path.join(OUTPUT_DIR, f"tag-{tag}.html"), "w", encoding="utf-8") as f:
            f.write(html)

def build_date_pages(posts_meta):
    # По годам
    years = {}
    for filename, title, date, _ in posts_meta:
        year = date.split("-")[0]
        years.setdefault(year, []).append((filename, title, date))
    
    for year, year_posts in years.items():
        links = "".join(f'<li><a href="{f}">{t}</a> <small>{d}</small></li>' for f, t, d in year_posts)
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{year}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
</head>
<body style="max-width:800px;margin:0 auto;padding:2rem;">
    <a href="index.html">← Назад</a>
    <h1>📅 {year}</h1>
    <p>Постов: {len(year_posts)}</p>
    <ul>{links}</ul>
</body>
</html>"""
        with open(os.path.join(OUTPUT_DIR, f"year-{year}.html"), "w", encoding="utf-8") as f:
            f.write(html)
    
    # По месяцам
    months = {}
    for filename, title, date, _ in posts_meta:
        month = date[:7]
        months.setdefault(month, []).append((filename, title, date))
    
    for month, month_posts in months.items():
        links = "".join(f'<li><a href="{f}">{t}</a> <small>{d}</small></li>' for f, t, d in month_posts)
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{month}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
</head>
<body style="max-width:800px;margin:0 auto;padding:2rem;">
    <a href="index.html">← Назад</a>
    <h1>📆 {month}</h1>
    <p>Постов: {len(month_posts)}</p>
    <ul>{links}</ul>
</body>
</html>"""
        with open(os.path.join(OUTPUT_DIR, f"month-{month}.html"), "w", encoding="utf-8") as f:
            f.write(html)

async def fetch_telegram_posts(client):
    """Загружает ВСЕ посты с картинами с ПРОГРЕСС-БАРОМ и БЕЗ ДУБЛИРОВАНИЯ"""
    print("📥 Загружаю все посты с картинами...")
    
    processed_ids = load_processed_ids()
    print(f"   Уже обработано постов: {len(processed_ids)}")
    
    posts = []
    total_checked = 0
    new_found = 0
    
    # Сначала посчитаем общее количество постов в канале
    print("   Подсчитываю общее количество постов...")
    total_messages = 0
    async for _ in client.iter_messages(CHANNEL_URL):
        total_messages += 1
    print(f"   Всего постов в канале: {total_messages}")
    
    # Загружаем посты с прогресс-баром
    progress = 0
    async for message in client.iter_messages(CHANNEL_URL):
        progress += 1
        total_checked += 1
        
        # Прогресс-бар
        percent = int(progress / total_messages * 100)
        bar_length = 30
        filled = int(bar_length * progress / total_messages)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r   Прогресс: [{bar}] {percent}% ({progress}/{total_messages})", end="", flush=True)
        
        # Проверяем, не обработан ли уже
        if message.id in processed_ids:
            continue
        
        # Проверяем, картина ли это
        if message.text and is_artist_post(message.text):
            posts.append({
                "id": message.id,
                "date": message.date.strftime("%Y-%m-%d"),
                "text": message.text,
                "message": message
            })
            new_found += 1
    
    print(f"\n   ✅ Завершено! Проверено: {total_checked}, найдено новых картин: {new_found}")
    
    # Сохраняем ID всех обработанных постов
    all_ids = processed_ids.union({msg["id"] for msg in posts})
    save_processed_ids(all_ids)
    
    return posts

async def main():
    print("🚀 Начинаю сборку сайта...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    print("📡 Подключаюсь к Telegram через MTProto...")
    client = TelegramClient(
        "my_session",
        api_id=API_ID,
        api_hash=API_HASH,
        connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
        proxy=PROXY
    )
    await client.start()
    print("✅ Подключён!")
    
    posts = await fetch_telegram_posts(client)
    
    if not posts:
        print("❌ Новых постов с картинами не найдено.")
        await client.disconnect()
        # Всё равно обновляем индекс и отправляем на GitHub
        # Загружаем существующие посты для полного индекса
        all_posts_meta = []
        for filename in os.listdir(OUTPUT_DIR):
            if filename.endswith(".html") and filename not in ["index.html"]:
                parts = filename.split("-", 1)
                if len(parts) == 2:
                    date = parts[0]
                    title = parts[1].replace(".html", "").replace("-", " ").title()
                    all_posts_meta.append((filename, title, date, []))
        
        all_posts_meta.sort(key=lambda x: x[2])
        
        if all_posts_meta:
            print("📄 Обновляю главную страницу...")
            build_index(all_posts_meta)
        
        await client.disconnect()
        push_to_github()
        return
    
    template = load_template()
    posts_meta = []
    all_tags = set()
    
    for i, post in enumerate(posts, 1):
        preview = clean_title(post["text"])[:50]
        print(f"📝 [{i}/{len(posts)}] Пост #{post['id']}: {preview}...")
        
        post_slug = slugify(post["text"])
        media_html = await download_media(client, post["message"], post_slug)
        
        filename, title, date, tags = build_post(post, template, media_html)
        posts_meta.append((filename, title, date, tags))
        all_tags.update(tags)
    
    await client.disconnect()
    
    # Загружаем существующие посты для полного индекса
    all_posts_meta = []
    for filename in os.listdir(OUTPUT_DIR):
        if filename.endswith(".html") and filename not in ["index.html"]:
            parts = filename.split("-", 1)
            if len(parts) == 2:
                date = parts[0]
                title = parts[1].replace(".html", "").replace("-", " ").title()
                all_posts_meta.append((filename, title, date, []))
    
    # Добавляем новые посты
    for item in posts_meta:
        if item[0] not in [x[0] for x in all_posts_meta]:
            all_posts_meta.append(item)
    
    all_posts_meta.sort(key=lambda x: x[2])
    
    print("📄 Создаю главную страницу...")
    build_index(all_posts_meta)
    
    print(f"🏷 Создаю страницы тегов ({len(all_tags)} шт)...")
    build_tag_pages(all_tags, all_posts_meta)
    
    print("📅 Создаю страницы по датам...")
    build_date_pages(all_posts_meta)
    
    print(f"\n✨ Готово! Добавлено {len(posts)} новых постов.")
    print(f"📂 Всего постов на сайте: {len(all_posts_meta)}")
    
    # Автоматическая отправка на GitHub
    push_to_github()

if __name__ == "__main__":
    asyncio.run(main())