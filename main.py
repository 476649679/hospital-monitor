import os
import json
import time
import hashlib
import requests
from xhs import XhsClient
from http.cookies import SimpleCookie

# --- 核心配置 ---
# 只要包含"韶关"就抓取，不再强制要求"妇幼"（防止漏抓）
MUST_INCLUDE = ["韶关"] 
# 搜索关键词列表
SEARCH_KEYWORDS = ["韶关市妇幼保健院", "韶关妇幼", "韶关 产科", "韶关 避雷"]
# 负面敏感词
NEGATIVE_WORDS = ["避雷", "坑", "差", "事故", "垃圾", "无语", "投诉", "死", "黑"]

# 环境变量
COOKIE_STR = os.environ.get("XHS_COOKIE")
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
HISTORY_FILE = "history.json"

def cookie_to_dict(cookie_str):
    """
    【关键修复】将 Cookie 字符串转换为字典
    解决 'str' object has no attribute 'value' 报错
    """
    if not cookie_str:
        return {}
    try:
        cookie = SimpleCookie()
        cookie.load(cookie_str)
        cookies = {}
        for key, morsel in cookie.items():
            cookies[key] = morsel.value
        return cookies
    except Exception as e:
        print(f"❌ Cookie 解析失败: {e}")
        return {}

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
        requests.post(url, json=data)
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
    data = list(history_set)[-1000:]
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)

def check_relevance(text):
    """关键词过滤"""
    for word in MUST_INCLUDE:
        if word in text:
            return True
    return False

def main():
    print(">>> 启动小红书监控 (Cookie兼容版)...")
    
    if not COOKIE_STR:
        print("❌ 错误：未设置 XHS_COOKIE")
        send_wechat("❌ 监控中断", "请去 GitHub Settings 填写 XHS_COOKIE")
        return

    # 【关键修复】这里不再直接传字符串，而是传转换后的字典
    cookie_dict = cookie_to_dict(COOKIE_STR)
    client = XhsClient(cookie=cookie_dict)
    
    history = load_history()
    new_notes = []
    
    for keyword in SEARCH_KEYWORDS:
        print(f"正在搜索: {keyword}")
        try:
            # 搜索笔记
            notes = client.get_note_by_keyword(keyword, sort='time', page=1, page_size=20)
        except Exception as e:
            # 捕捉所有错误并打印详情
            print(f"⚠️ 抓取报错 (关键词: {keyword}): {str(e)}")
            continue

        if not notes or 'items' not in notes:
            continue

        for note in notes['items']:
            note_id = note.get('id')
            if not note_id: continue
            
            card = note.get('note_card', {})
            title = card.get('display_title', '无标题')
            desc = card.get('desc', '') 
            user = card.get('user', {}).get('nickname', '未知')
            
            full_text = title + desc
            
            # 1. 过滤无关内容
            if not check_relevance(full_text):
                continue
                
            # 2. 去重
            uid = hashlib.md5(note_id.encode()).hexdigest()
            if uid in history:
                continue
            history.add(uid)
            
            # 3. 负面标记
            is_risk = False
            for risk_word in NEGATIVE_WORDS:
                if risk_word in full_text:
                    is_risk = True
                    break
            
            link = f"https://www.xiaohongshu.com/explore/{note_id}"
            emoji = "🔴" if is_risk else "📝"
            risk_tag = "**[⚠️高危]** " if is_risk else ""
            
            entry = f"{emoji} {risk_tag}**{title}**\n" \
                    f"> 👤 {user}\n" \
                    f"> 📄 {desc[:60]}...\n" \
                    f"> 🔗 [点击查看]({link})"
            
            new_notes.append(entry)
            
        time.sleep(2)

    if new_notes:
        print(f"✅ 发现 {len(new_notes)} 条新笔记，推送中...")
        title = f"📢 小红书舆情 ({len(new_notes)}条)"
        content = "#### 🔍 监控日报\n\n" + "\n\n".join(new_notes)
        send_wechat(title, content)
        save_history(history)
    else:
        print("⭕ 今日无新增相关笔记")
        # 发送心跳回执
        send_wechat("✅ 监控正常", f"脚本运行完毕，暂无关于“韶关”的新增笔记。\n时间: {time.strftime('%H:%M')}")

if __name__ == "__main__":
    main()
