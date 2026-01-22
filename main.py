import requests
from bs4 import BeautifulSoup
import datetime
import os
import json
import hashlib
import time
import random
import re

# --- 核心配置区 ---
KEYWORDS = ["韶关市妇幼保健院", "韶关妇幼", "韶关产科"]
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
HISTORY_FILE = "history.json"

def get_headers():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15'
    ]
    return {
        'User-Agent': random.choice(user_agents),
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://cn.bing.com/'
    }

def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fa5]', text))

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_history(history_set):
    limited_history = list(history_set)[-1000:]
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(limited_history, f)

def search_cn_bing(keyword):
    results = []
    url = f"https://cn.bing.com/search?q={keyword}&cc=CN&setmkt=zh-CN&first=1"
    
    try:
        print(f"正在抓取: {keyword} ...")
        resp = requests.get(url, headers=get_headers(), timeout=20)
        soup = BeautifulSoup(resp.text, 'lxml')
        
        for item in soup.find_all('li', class_='b_algo'):
            title_tag = item.find('h2')
            if not title_tag: continue
            
            link_tag = title_tag.find('a')
            if not link_tag: continue
            
            # --- 修复点：拆分写法，解决 SyntaxError ---
            link = link_tag.get('href')
            if not link: continue
            # -------------------------------------
            
            title = link_tag.text.strip()
            if not contains_chinese(title): continue
            
            snippet = ""
            caption_div = item.find('div', class_='b_caption')
            if caption_div:
                p_tag = caption_div.find('p')
                snippet = p_tag.text.strip() if p_tag else ""

            results.append({
                "title": title,
                "link": link,
                "snippet": snippet,
                "source": "BingCN"
            })
    except Exception as e:
        print(f"抓取异常: {e}")
    
    return results

def send_push(content_list):
    if not content_list: return
    title = f"📢 {datetime.date.today()} 韶关妇幼舆情 ({len(content_list)}条)"
    content = "#### 🔍 监控日报\n------------------\n\n" + "\n\n".join(content_list)
    url = "http://www.pushplus.plus/send"
    data = {"token": PUSH_TOKEN, "title": title, "content": content, "template": "markdown"}
    requests.post(url, json=data)

def main():
    history = load_history()
    new_entries = []
    
    for keyword in KEYWORDS:
        results = search_cn_bing(keyword)
        for item in results:
            unique_str = item['link']
            uid = hashlib.md5(unique_str.encode()).hexdigest()
            if uid in history: continue
            
            history.add(uid)
            is_risk = any(w in (item['title'] + item['snippet']) for w in ["投诉", "死", "差", "避雷", "事故"])
            emoji = "🔴" if is_risk else "🔵"
            entry = f"{emoji} **[{item['title']}]({item['link']})**\n> {item['snippet'][:80]}..."
            new_entries.append(entry)
        time.sleep(random.uniform(2, 5))

    if new_entries:
        print(f"✅ 发现 {len(new_entries)} 条内容，推送中...")
        send_push(new_entries)
        save_history(history)
    else:
        print("⭕ 今日无新内容")

if __name__ == "__main__":
    main()
