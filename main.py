import os
import json
import time
import hashlib
import requests
import traceback
from xhs import XhsClient

# --- 🎯 核心配置区 ---

# 1. 搜索关键词 (广撒网)
SEARCH_KEYWORDS = [
    "韶关 妇幼",
    "韶关 产科",
    "韶关 生产",
    "韶关 生孩子",
    "韶关 避雷",
    "妇幼保健院", # 搜全名，靠下面的地域词过滤
    "产科 避雷"   # 搜大类，靠下面的地域词过滤
]

# 2. 地域/相关性过滤器 (必须包含其中之一)
MUST_INCLUDE = [
    "韶关", "武江", "浈江", "曲江", "翁源", "乳源", "始兴", 
    "仁化", "新丰", "乐昌", "南雄", "广东"
] 

# 3. 负面敏感词
NEGATIVE_WORDS = ["避雷", "坑", "差", "事故", "垃圾", "无语", "投诉", "死", "黑", "医疗纠纷"]

# 4. 抓取深度 (翻3页，约60条，覆盖24小时)
MAX_PAGES = 3

# 环境变量
COOKIE_RAW = os.environ.get("XHS_COOKIE")
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
HISTORY_FILE = "history.json"

def send_wechat(title, content):
    """发送微信推送"""
    if not PUSH_TOKEN: return
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSH_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown"
    }
    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_history(history_set):
    try:
        data = list(history_set)[-1000:]
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except:
        pass

def check_relevance(text):
    """地域过滤"""
    if not MUST_INCLUDE: return True
    for word in MUST_INCLUDE:
        if word in text: return True
    return False

def main():
    print(">>> 启动小红书监控 (原生Cookie直连版)...")
    
    try:
        if not COOKIE_RAW:
            raise ValueError("未设置 XHS_COOKIE")

        # 【核心修改】不做任何解析，只去头尾空格，原样使用
        # 请确保你在 GitHub 填入的是 a=1; b=2 这种长字符串
        final_cookie = COOKIE_RAW.strip()

        # 初始化
        client = XhsClient(cookie=final_cookie)

        # 活性检测 (还是得测一下，不然不知道Cookie能不能用)
        print("🔍 正在测试 Cookie 是否有效...")
        try:
            client.get_note_by_keyword("你好", page=1, page_size=1)
        except Exception as e:
            send_wechat("🚨 Cookie 报错", f"Cookie 似乎无法使用，请检查是否复制完整。\n错误：{e}")
            return

        print("✅ Cookie 有效，开始执行广域搜索...")
        history = load_history()
        new_notes = []
        
        for keyword in SEARCH_KEYWORDS:
            print(f"正在搜索: {keyword}")
            
            # 翻页循环
            for page in range(1, MAX_PAGES + 1):
                try:
                    # sort='time' 按时间倒序
                    notes = client.get_note_by_keyword(keyword, sort='time', page=page, page_size=20)
                except Exception as e:
                    print(f"⚠️ 翻页中断: {e}")
                    break

                if not notes or 'items' not in notes or not notes['items']:
                    break 

                for note in notes['items']:
                    note_id = note.get('id')
                    card = note.get('note_card', {})
                    title = card.get('display_title', '无标题')
                    desc = card.get('desc', '')
                    user = card.get('user', {}).get('nickname', '未知')
                    
                    full_text = title + desc
                    
                    # 1. 地域过滤
                    if not check_relevance(full_text): 
                        continue
                    
                    # 2. 去重
                    uid = hashlib.md5(note_id.encode()).hexdigest()
                    if uid in history: continue
                    history.add(uid)
                    
                    # 3. 标记
                    is_risk = any(w in full_text for w in NEGATIVE_WORDS)
                    emoji = "🔴" if is_risk else "📝"
                    risk_tag = "**[⚠️高危]** " if is_risk else ""
                    
                    link = f"https://www.xiaohongshu.com/explore/{note_id}"
                    entry = f"{emoji} {risk_tag}**[{title}]({link})**\n> 👤 {user}\n> 📄 {desc[:40]}..."
                    new_notes.append(entry)
                
                time.sleep(1.5) # 稍微快一点点

        if new_notes:
            print(f"✅ 抓取到 {len(new_notes)} 条有效信息")
            title = f"📢 妇幼舆情 ({len(new_notes)}条)"
            content = "#### 🔍 24小时广域监测\n\n" + "\n\n".join(new_notes)
            send_wechat(title, content)
            save_history(history)
        else:
            print("⭕ 暂无新增内容")
            send_wechat("✅ 监控正常", f"脚本运行完毕。\n已搜索关键词：{SEARCH_KEYWORDS}\n暂无韶关地区相关新增内容。")

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"❌ 运行崩溃: {error_msg}")
        send_wechat("⚠️ 监控脚本崩溃", f"详情：\n{str(e)}")
        raise e

if __name__ == "__main__":
    main()
