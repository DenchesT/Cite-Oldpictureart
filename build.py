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
        shutil.copy2(os.path.join(OUTPUT_DIR, "index.html"), "index.html")
        print("   ✅ index.html скопирован в корень")
        
        result = subprocess.run(["git", "add", "."], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ⚠️ git add: {result.stderr}")
        else:
            print("   ✅ Файлы добавлены в Git")
        
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not result.stdout.strip():
            print("   ℹ️ Нет изменений для отправки")
            return
        
        commit_msg = f"Авто-обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        result = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ⚠️ git commit: {result.stderr}")
        else:
            print(f"   ✅ Закоммичено: {commit_msg}")
        
        result = subprocess.run(["git", "push"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ⚠️ git push: {result.stderr}")
        else:
            print("   ✅ Отправлено на GitHub!")
            
    except Exception as e:
        print(f"   ❌ Ошибка при отправке на GitHub: {e}")

def load_template():
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        return f.read()

def clean_title(text):
    """Берёт ПЕРВУЮ строку как название (имя художника)"""
    title = text.split("\n")[0].strip()
    # Убираем всякий мусор
    title = re.sub(r'\*\*|__|##|`', '', title)
    title = re.sub(r'\[.+?\]\(.+?\)', '', title)
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
    # Убираем всё, кроме букв, цифр и пробелов
    slug = re.sub(r'[^\w\s]', '', title)
    slug = slug.strip().replace(" ", "-").lower()
    # Ограничиваем длину
    slug = slug[:50]
    return slug if slug else "post"

def extract_tags(text):
    return list(set(re.findall(r'#(\w+)', text)))

def telegram_to_html(text):
    """Конвертирует Telegram-разметку в HTML"""
    # Убираем разделители
    text = re.sub(r'[⸻]{3,}|[-_]{3,}', '<hr>', text)
    # Превращаем ссылки
    text = re.sub(r'(https?://[^\s]+)', r'<a href="\1" target="_blank">\1</a>', text)
    # Жирный и курсив
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<em>\1</em>', text)
    # Разбиваем на параграфы
    text = text.replace("\n\n", "</p><p>")
    text = f"<p>{text}</p>"
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
    html = html.replace("{{content}}", content)
    html = html.replace("{{tags}}", tags_html)
    
    filename = f"{post['date']}-{slugify(post['text'])}.html"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    
    return filename, title, post["date"], tags

def build_index(posts_meta):
    """Создаёт простую главную страницу без боковой панели"""
    cards = ""
    for filename, title, date, tags in reversed(posts_meta):
        tags_html = ""
        if tags:
            tags_html = '<div class="card-tags">' + " ".join(
                [f'<span class="tag">#{tag}</span>' for tag in sorted(tags[:3])]
            ) + '</div>'
        
        cards += f"""
        <article class="card">
            <h3><a href="{filename}">{title}</a></h3>
            <time>{date}</time>
            {tags_html}
        </article>"""
    
    index_html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Old Picture Art — Галерея</title>
    <style>
        body {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 1rem;
            font-family: system-ui, -apple-system, sans-serif;
            background: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5rem;
        }}
        .card-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.5rem;
        }}
        .card {{
            background: white;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        .card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .card h3 {{
            margin: 0 0 0.5rem 0;
            font-size: 1.1rem;
        }}
        .card h3 a {{
            text-decoration: none;
            color: #2c3e50;
        }}
        .card h3 a:hover {{
            color: #3498db;
        }}
        .card time {{
            color: #888;
            font-size: 0.85rem;
        }}
        .card-tags {{
            margin-top: 0.5rem;
        }}
        .tag {{
            font-size: 0.75rem;
            color: #666;
            background: #f0f0f0;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            margin-right: 0.3rem;
        }}
        .search-box {{
            width: 100%;
            padding: 0.75rem;
            margin-bottom: 1.5rem;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 1rem;
        }}
        .stats {{
            color: #666;
            margin-bottom: 1rem;
            font-size: 0.9rem;
        }}
        @media (max-width: 700px) {{
            .card-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>🖼 Old Picture Art</h1>
        <input type="text" class="search-box" placeholder="🔍 Поиск по названию..." id="search">
        <div class="stats">📊 Всего картин: {len(posts_meta)}</div>
    </header>
    <main>
        <div class="card-grid" id="cards">
            {cards}
        </div>
    </main>
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

async def fetch_telegram_posts(client):
    """Загружает ВСЕ посты с картинами"""
    print("📥 Загружаю все посты с картинами...")
    
    processed_ids = load_processed_ids()
    print(f"   Уже обработано постов: {len(processed_ids)}")
    
    posts = []
    total_checked = 0
    new_found = 0
    
    # Считаем общее количество
    print("   Подсчитываю общее количество постов...")
    total_messages = 0
    async for _ in client.iter_messages(CHANNEL_URL):
        total_messages += 1
    print(f"   Всего постов в канале: {total_messages}")
    
    # Загружаем посты
    progress = 0
    async for message in client.iter_messages(CHANNEL_URL):
        progress += 1
        total_checked += 1
        
        # Прогресс
        percent = int(progress / total_messages * 100)
        print(f"\r   Прогресс: {percent}% ({progress}/{total_messages})", end="", flush=True)
        
        if message.id in processed_ids:
            continue
        
        if message.text and is_artist_post(message.text):
            posts.append({
                "id": message.id,
                "date": message.date.strftime("%Y-%m-%d"),
                "text": message.text,
                "message": message
            })
            new_found += 1
    
    print(f"\n   ✅ Завершено! Проверено: {total_checked}, найдено новых картин: {new_found}")
    
    # Сохраняем ID
    all_ids = processed_ids.union({msg["id"] for msg in posts})
    save_processed_ids(all_ids)
    
    return posts

async def main():
    print("🚀 Начинаю сборку сайта...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    print("📡 Подключаюсь к Telegram...")
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
        print("❌ Новых постов не найдено.")
        await client.disconnect()
        push_to_github()
        return
    
    template = load_template()
    posts_meta = []
    all_tags = set()
    
    for i, post in enumerate(posts, 1):
        title = clean_title(post["text"])[:60]
        print(f"📝 [{i}/{len(posts)}] {title}...")
        
        post_slug = slugify(post["text"])
        media_html = await download_media(client, post["message"], post_slug)
        
        filename, title, date, tags = build_post(post, template, media_html)
        posts_meta.append((filename, title, date, tags))
        all_tags.update(tags)
    
    await client.disconnect()
    
    # Собираем все посты для главной страницы
    all_posts_meta = []
    for filename in os.listdir(OUTPUT_DIR):
        if filename.endswith(".html") and filename not in ["index.html"]:
            parts = filename.split("-", 1)
            if len(parts) == 2:
                date = parts[0]
                name = parts[1].replace(".html", "").replace("-", " ")
                all_posts_meta.append((filename, name, date, []))
    
    for item in posts_meta:
        if item[0] not in [x[0] for x in all_posts_meta]:
            all_posts_meta.append(item)
    
    all_posts_meta.sort(key=lambda x: x[2])
    
    print("📄 Создаю главную страницу...")
    build_index(all_posts_meta)
    
    print(f"\n✨ Готово! Добавлено {len(posts)} новых постов.")
    print(f"📂 Всего постов на сайте: {len(all_posts_meta)}")
    
    push_to_github()

if __name__ == "__main__":
    asyncio.run(main())