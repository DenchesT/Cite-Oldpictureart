import asyncio
import os
import re
from pathlib import Path
from telethon import TelegramClient, connection

# ==================== НАСТРОЙКИ ====================
API_ID = 123456        # Твой api_id (число)
API_HASH = "твой_hash"  # Твой api_hash (строка)

CHANNEL_URL = "https://t.me/oldpictureart"
OUTPUT_DIR = "output"
IMAGES_DIR = "output/images"
TEMPLATE_FILE = "template.html"

PROXY = (
    '138.226.236.46',
    8443,
    'ee5a76b164eadb451a845bfae212bf8649706574726f766963682e7275'
)

OUTPUT_DIR = "output"
IMAGES_DIR = "output/images"
TEMPLATE_FILE = "template.html"

PROXY = (
    '138.226.236.46',
    8443,
    'ee5a76b164eadb451a845bfae212bf8649706574726f766963682e7275'
)
# ===================================================

def load_template():
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        return f.read()

def clean_title(text):
    title = text.split("\n")[0]
    title = re.sub(r'\*\*|__|##|`', '', title)
    title = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', title)
    title = re.sub(r'#\w+', '', title)
    return title.strip()

def slugify(text):
    title = clean_title(text)
    slug = "".join(c if c.isalnum() or c.isspace() else "" for c in title)
    slug = slug.strip().replace(" ", "-").lower()
    return slug[:60].rstrip("-") or "post"

def extract_tags(text):
    """Извлекает хэштеги из текста"""
    return list(set(re.findall(r'#(\w+)', text)))

def telegram_to_html(text):
    """Конвертирует разметку Telegram в HTML"""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<em>\1</em>', text)
    text = re.sub(r'[⸻]{3,}|[-_]{3,}', r'<hr>', text)
    # Превращаем хэштеги в ссылки
    text = re.sub(r'#(\w+)', r'<a href="tag-\1.html" class="tag">#\1</a>', text)
    text = text.replace("\n\n", "</p><p>")
    return text

async def download_media(client, message, post_slug):
    """Скачивает медиа из поста, возвращает HTML-тег"""
    if not message.media:
        return ""
    
    try:
        # Создаём имя файла
        ext = ".jpg"
        filename = f"{post_slug}{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)
        
        # Скачиваем
        await client.download_media(message, filepath)
        
        # Возвращаем HTML
        return f'<img src="images/{filename}" alt="{clean_title(message.text)}" class="post-image">'
    except Exception as e:
        print(f"    ⚠️ Не удалось скачать медиа: {e}")
        return ""

def build_post(post, template, media_html):
    """Создаёт HTML-страницу для одного поста"""
    title = clean_title(post["text"])
    content = telegram_to_html(post["text"])
    tags = extract_tags(post["text"])
    
    # Собираем теги
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
    """Создаёт index.html с сеткой карточек"""
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
    
    # Группировка по годам для боковой панели
    years = sorted(set(date.split("-")[0] for _, _, date, _ in posts_meta), reverse=True)
    months = sorted(set(date[:7] for _, _, date, _ in posts_meta), reverse=True)
    
    years_nav = "\n".join([f'<li><a href="year-{y}.html">{y}</a></li>' for y in years])
    months_nav = "\n".join([f'<li><a href="month-{m}.html">{m}</a></li>' for m in months[:12]])
    
    index_html = f"""<!DOCTYPE html>
<html lang="ru" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Old Picture Art — Галерея</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <style>
        :root {{ --pico-font-size: 100%; }}
        body {{ max-width: 1000px; margin: 0 auto; padding: 1rem; }}
        .layout {{ display: grid; grid-template-columns: 1fr 200px; gap: 2rem; }}
        .sidebar {{ 
            background: #f8f9fa; 
            padding: 1rem; 
            border-radius: 8px; 
            height: fit-content;
            position: sticky;
            top: 1rem;
        }}
        .sidebar h4 {{ margin-top: 0; }}
        .sidebar ul {{ list-style: none; padding: 0; font-size: 0.9rem; }}
        .sidebar li {{ margin-bottom: 0.3rem; }}
        .card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }}
        .card {{ 
            padding: 1rem; 
            border: 1px solid #e0e0e0; 
            border-radius: 8px; 
            transition: box-shadow 0.2s;
        }}
        .card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
        .card h3 {{ margin: 0 0 0.5rem 0; font-size: 1.1rem; }}
        .card h3 a {{ text-decoration: none; color: #2c3e50; }}
        .card time {{ color: #888; font-size: 0.85rem; }}
        .card-tags {{ margin-top: 0.5rem; }}
        .card-tags a {{ 
            font-size: 0.8rem; 
            color: #666; 
            text-decoration: none; 
            margin-right: 0.3rem;
        }}
        .card-tags a:hover {{ color: #000; }}
        .search-box {{ 
            width: 100%; 
            padding: 0.5rem; 
            margin-bottom: 1rem; 
            border: 1px solid #ddd; 
            border-radius: 4px; 
        }}
        @media (max-width: 768px) {{
            .layout {{ grid-template-columns: 1fr; }}
            .sidebar {{ position: static; }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>🖼 Old Picture Art</h1>
        <input type="text" class="search-box" placeholder="🔍 Поиск по постам..." id="search">
        <p style="color: #888;">Постов: {len(posts_meta)}</p>
    </header>
    <div class="layout">
        <main>
            <div class="card-grid" id="cards">
                {cards}
            </div>
        </main>
        <aside class="sidebar">
            <h4>📅 По годам</h4>
            <ul>{years_nav}</ul>
            <h4>📆 По месяцам</h4>
            <ul>{months_nav}</ul>
        </aside>
    </div>
    <script>
        document.getElementById('search').addEventListener('input', function(e) {{
            const query = e.target.value.toLowerCase();
            document.querySelectorAll('.card').forEach(card => {{
                const text = card.textContent.toLowerCase();
                card.style.display = text.includes(query) ? '' : 'none';
            }});
        }});
    </script>
</body>
</html>"""
    
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

def build_tag_pages(all_tags, posts_meta):
    """Создаёт страницы для каждого тега"""
    for tag in all_tags:
        tag_posts = [(f, t, d) for f, t, d, tags in posts_meta if tag in tags]
        links = ""
        for filename, title, date in tag_posts:
            links += f'<li><a href="{filename}">{title}</a> <small>{date}</small></li>\n'
        
        tag_html = f"""<!DOCTYPE html>
<html lang="ru" data-theme="light">
<head>
    <meta charset="UTF-8">
    <title>#{tag} — Old Picture Art</title>
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
            f.write(tag_html)

def build_date_pages(posts_meta):
    """Создаёт страницы по годам и месяцам"""
    # По годам
    years = {}
    for filename, title, date, tags in posts_meta:
        year = date.split("-")[0]
        years.setdefault(year, []).append((filename, title, date))
    
    for year, year_posts in years.items():
        links = ""
        for filename, title, date in year_posts:
            links += f'<li><a href="{filename}">{title}</a> <small>{date}</small></li>\n'
        
        html = f"""<!DOCTYPE html>
<html lang="ru" data-theme="light">
<head>
    <meta charset="UTF-8">
    <title>{year} — Old Picture Art</title>
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
    for filename, title, date, tags in posts_meta:
        month = date[:7]
        months.setdefault(month, []).append((filename, title, date))
    
    for month, month_posts in months.items():
        links = ""
        for filename, title, date in month_posts:
            links += f'<li><a href="{filename}">{title}</a> <small>{date}</small></li>\n'
        
        html = f"""<!DOCTYPE html>
<html lang="ru" data-theme="light">
<head>
    <meta charset="UTF-8">
    <title>{month} — Old Picture Art</title>
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
    """Забирает посты из Telegram"""
    print("📥 Загружаю посты...")
    
    posts = []
    async for message in client.iter_messages(CHANNEL_URL, limit=50):
        if message.text:
            posts.append({
                "id": message.id,
                "date": message.date.strftime("%Y-%m-%d"),
                "text": message.text,
                "message": message  # Сохраняем объект для скачивания медиа
            })
    
    print(f"📥 Загружено постов: {len(posts)}")
    return posts

async def main():
    print("🚀 Начинаю сборку сайта...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    # Подключаемся
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
    
    # Загружаем посты
    posts = await fetch_telegram_posts(client)
    
    if not posts:
        print("❌ Посты не найдены.")
        await client.disconnect()
        return
    
    template = load_template()
    posts_meta = []
    all_tags = set()
    
    # Генерируем страницы
    for post in posts:
        preview = clean_title(post["text"])[:60]
        print(f"📝 Пост #{post['id']}: {preview}...")
        
        # Скачиваем медиа
        post_slug = slugify(post["text"])
        media_html = await download_media(client, post["message"], post_slug)
        
        filename, title, date, tags = build_post(post, template, media_html)
        posts_meta.append((filename, title, date, tags))
        all_tags.update(tags)
    
    await client.disconnect()
    
    # Создаём индекс
    print("📄 Создаю главную страницу...")
    build_index(posts_meta)
    
    # Создаём страницы тегов
    print(f"🏷 Создаю страницы тегов ({len(all_tags)} шт)...")
    build_tag_pages(all_tags, posts_meta)
    
    # Создаём страницы дат
    print("📅 Создаю страницы по датам...")
    build_date_pages(posts_meta)
    
    print(f"\n✨ Готово!")
    print(f"📂 Открой {OUTPUT_DIR}/index.html в браузере")

if __name__ == "__main__":
    asyncio.run(main())