import requests
from bs4 import BeautifulSoup
import datetime
import os
import json
import hashlib
import time
import random

# --- 高级配置区 ---
KEYWORDS = ["韶关市妇幼保健院", "韶关妇幼"]
# 定义要专门“定点爆破”的社交平台域名
TARGET_SITES = [
   # "", # 空字符串代表全网新闻搜索
    "site:weibo.cn", # 微博 (使用手机版域名收录更快)
    "site:zhihu.com", # 知乎
    "site:xiaohongshu.com", # 小红书
    "site:toutiao.com" # 今日头条
]
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
HISTORY_FILE = "history.json"

# 负面敏感词库
NEGATIVE_WORDS = ["投诉", "避雷", "态度差", "医疗事故", "死", "垃圾", "坑", "无语", "曝光", "吵架"]

def get_headers():
    """随机User-Agent，模拟真实浏览器，防止被反爬"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    return {'User-Agent': random.choice(user_agents)}

def load_history():
    """读取历史记录，防止重复"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_history(history_set):
    """保存历史记录，保留最近1000条"""
    # 转为list并只保留最后1000个hash，防止文件无限膨胀
    limited_history = list(history_set)[-1000:]
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(limited_history, f)

def check_sentiment(text):
    """检查是否包含负面词汇"""
    for word in NEGATIVE_WORDS:
        if word in text:
            return True
    return False

def search_bing(keyword, site=""):
    """
    使用 Bing 搜索。
    site参数用于指定搜索特定网站，如 'site:weibo.cn'
    """
    results = []
    query = f"{keyword} {site}".strip()
    url = f"https://www.bing.com/search?q={query}&sort=date" 
    
    try:
        resp = requests.get(url, headers=get_headers(), timeout=15)
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # 针对 Bing 的标准搜索结果结构 (b_algo)
        for item in soup.find_all('li', class_='b_algo'):
            title_tag = item.find('h2')
            if not title_tag: continue
            
            link_tag = title_tag.find('a')
            if not link_tag: continue # 修复点：先检查有没有link_tag

            link_link = link_tag.get('href') # 修复点：拆分成两行写，避免语法错误
            if not link_link: continue
            
            title = link_tag.text
            # 尝试获取摘要
            snippet = item.find('p').text if item.find('p') else ""
            if not snippet:
                # 备用摘要获取方式
                caption = item.find('div', class_='b_caption')
                snippet = caption.text if caption else "无摘要"

            results.append({
                "title": title,
                "link": link_link,
                "snippet": snippet,
                "source": site if site else "全网新闻"
            })
    except Exception as e:
        print(f"搜索 [{query}] 时出错: {e}")
    
    return results

def send_push(content_list, has_risk):
    """发送微信推送"""
    if not content_list: return

    # 标题动态变化
    emoji = "⚠️" if has_risk else "📢"
    title = f"{emoji} {datetime.date.today()} 舆情日报 ({len(content_list)}条)"
    
    content = "#### 监控概览\n"
    content += f"监控词：{', '.join(KEYWORDS)}\n"
    content += f"覆盖源：微博、知乎、头条、全网\n\n"
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
    has_risk = False
    
    print(">>> 开始全网扫描...")
    
    # 双重循环：关键词 x 目标站点
    for keyword in KEYWORDS:
        for site in TARGET_SITES:
            print(f"正在搜索: {keyword} @ {site if site else '全网'}")
            results = search_bing(keyword, site)
            
            for item in results:
                # 生成唯一指纹 (MD5) 用于去重
                unique_str = item['link']
                uid = hashlib.md5(unique_str.encode()).hexdigest()
                
                if uid in history:
                    continue # 跳过已推送过的
                
                # 命中新内容
                history.add(uid)
                is_negative = check_sentiment(item['title'] + item['snippet'])
                if is_negative: has_risk = True
                
                # 格式化输出
                risk_tag = "**[⚠️高危]** " if is_negative else ""
                entry = f"{risk_tag}**{item['title']}**\n" \
                        f"> 来源：{item['source']}\n" \
                        f"> 摘要：{item['snippet'][:100]}...\n" \
                        f"> [点击查看原文]({item['link']})"
                new_entries.append(entry)
            
            # 礼貌性延时，防止请求过快被封
            time.sleep(2)

    if new_entries:
        print(f"发现 {len(new_entries)} 条新内容，正在推送...")
        send_push(new_entries, has_risk)
        save_history(history)
        print("历史记录已更新。")
    else:
        print("今日无新内容。")

if __name__ == "__main__":
    main()
