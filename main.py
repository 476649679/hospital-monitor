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
# 建议加上 "医院" "公告" 等后缀，搜索结果更精准
KEYWORDS = ["医院","韶关 医院","韶关市妇幼保健院", "韶关妇幼保健院", "韶关妇幼 投诉", "韶关妇幼 避雷"]

PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
HISTORY_FILE = "history.json"

def get_headers():
    """
    伪装成位于中国的中文用户
    """
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15'
    ]
    return {
        'User-Agent': random.choice(user_agents),
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8', # 关键：告诉服务器我是中文用户
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://cn.bing.com/'
    }

def contains_chinese(text):
    """判断文本中是否包含中文字符，用于过滤英文垃圾结果"""
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
    """
    针对 cn.bing.com 的优化搜索
    """
    results = []
    # 强制使用 cn.bing.com，并加上 &cc=CN 参数强制中国区
    url = f"https://cn.bing.com/search?q={keyword}&cc=CN&setmkt=zh-CN&first=1"
    
    try:
        print(f"正在抓取: {keyword} ...")
        resp = requests.get(url, headers=get_headers(), timeout=20)
        
        if resp.status_code != 200:
            print(f"❌ 访问失败，状态码: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, 'lxml')
        
        # 解析 Bing 搜索结果列表
        for item in soup.find_all('li', class_='b_algo'):
            title_tag = item.find('h2')
            if not title_tag: continue
            
            link_tag = title_tag.find('a')
            if not link_tag: continue
            
            link = link_tag.get('href')
            if not link: continue
            
            title = link_tag.text.strip()
            
            # --- 关键过滤器 ---
            # 1. 如果标题里没有中文，说明是英文垃圾结果，丢弃
            if not contains_chinese(title):
                continue
            
            # 获取摘要
            snippet = ""
            caption_div = item.find('div', class_='b_caption')
            if caption_div:
                p_tag = caption_div.find('p')
                snippet = p_tag.text.strip() if p_tag else ""
            
            # 如果摘要里也没有关键词，可能是广告，进一步过滤
            if keyword.split()[0] not in title and keyword.split()[0] not in snippet:
                 # 稍微放宽一点，防止漏抓，这里只做简单的相关性打印
                 pass

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
    
    content = "#### 🔍 监控日报 (CN节点增强版)\n"
    content += "------------------\n\n"
    content += "\n\n".join(content_list)
    
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSH_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown" 
    }
    requests.post(url, json=data)

def main():
    history = load_history()
    new_entries = []
    
    # 遍历关键词
    for keyword in KEYWORDS:
        results = search_cn_bing(keyword)
        
        for item in results:
            # 去重逻辑
            unique_str = item['link']
            uid = hashlib.md5(unique_str.encode()).hexdigest()
            
            if uid in history:
                continue 
            
            history.add(uid)
            
            # 简单的负面词高亮
            is_risk = any(w in (item['title'] + item['snippet']) for w in ["投诉", "死", "差", "避雷", "事故"])
            emoji = "🔴" if is_risk else "🔵"
            
            entry = f"{emoji} **[{item['title']}]({item['link']})**\n" \
                    f"> {item['snippet'][:80]}..."
            new_entries.append(entry)
        
        # 随机等待，避免被封
        time.sleep(random.uniform(2, 5))

    if new_entries:
        print(f"✅ 发现 {len(new_entries)} 条有效中文内容，推送中...")
        send_push(new_entries)
        save_history(history)
    else:
        print("⭕ 今日无新内容（已过滤掉非中文/无关键内容结果）")

if __name__ == "__main__":
    main()
