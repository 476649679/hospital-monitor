import os
import json
import time
import hashlib
import requests
import traceback
from xhs import XhsClient

# --- 核心配置 ---
MUST_INCLUDE = ["韶关"] 
SEARCH_KEYWORDS = ["韶关市妇幼保健院", "韶关妇幼", "韶关 产科", "韶关 避雷"]
NEGATIVE_WORDS = ["避雷", "坑", "差", "事故", "垃圾", "无语", "投诉", "死", "黑"]

# 环境变量
COOKIE_DATA = os.environ.get("XHS_COOKIE")
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
HISTORY_FILE = "history.json"

def send_wechat(title, content):
    """发送微信推送"""
    if not PUSH_TOKEN: 
        print("❌ 未设置 PUSH_TOKEN")
        return
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSH_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown"
    }
    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"❌ 推送失败: {e}")

def smart_cookie_loader(cookie_input):
    """
    【智能解析】
    不管输入是 字符串 还是 字典，通通转成字典
    解决 'dict' object has no attribute 'split' 报错
    """
    if not cookie_input:
        return {}
    
    # 1. 如果本来就是字典，直接返回（修复你刚才的报错）
    if isinstance(cookie_input, dict):
        return cookie_input
    
    # 2. 如果是字符串，尝试解析
    if isinstance(cookie_input, str):
        # 情况A: 如果是 JSON 字符串 (例如 {"a": "b"})
        if cookie_input.strip().startswith('{'):
            try:
                return json.loads(cookie_input)
            except:
                pass # 解析失败就尝试按分号切割

        # 情况B: 普通 Cookie 字符串 (a=b; c=d)
        cookies = {}
        for item in cookie_input.split(';'):
            if '=' in item:
                try:
                    k, v = item.split('=', 1)
                    cookies[k.strip()] = v.strip()
                except:
                    continue
        return cookies
        
    return {}

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
    for word in MUST_INCLUDE:
        if word in text: return True
    return False

def main():
    print(">>> 启动小红书监控 (智能兼容版)...")
    
    try:
        if not COOKIE_DATA:
            raise ValueError("未设置 XHS_COOKIE")

        # 使用智能加载器，不挑食
        cookie_dict = smart_cookie_loader(COOKIE_DATA)
        
        # 再次检查解析结果
        if not cookie_dict:
             raise ValueError("Cookie 解析为空，请检查 Secrets 格式")

        client = XhsClient(cookie=cookie_dict)
        history = load_history()
        new_notes = []
        
        for keyword in SEARCH_KEYWORDS:
            print(f"正在搜索: {keyword}")
            try:
                notes = client.get_note_by_keyword(keyword, sort='time', page=1, page_size=20)
            except Exception as e:
                print(f"⚠️ 搜索跳过: {e}")
                continue

            if not notes or 'items' not in notes:
                continue

            for note in notes['items']:
                note_id = note.get('id')
                if not note_id: continue
                
                card = note.get('note_card', {})
                title = card.get('display_title', '无标题')
                desc = card.get('desc', '') 
                
                full_text = title + desc
                
                if not check_relevance(full_text): continue
                
                uid = hashlib.md5(note_id.encode()).hexdigest()
                if uid in history: continue
                history.add(uid)
                
                is_risk = any(w in full_text for w in NEGATIVE_WORDS)
                emoji = "🔴" if is_risk else "📝"
                
                link = f"https://www.xiaohongshu.com/explore/{note_id}"
                entry = f"{emoji} **[{title}]({link})**\n> {desc[:50]}..."
                new_notes.append(entry)
            
            time.sleep(2)

        if new_notes:
            print(f"✅ 发现 {len(new_notes)} 条新笔记")
            title = f"📢 舆情日报 ({len(new_notes)}条)"
            content = "#### 🔍 监控结果\n\n" + "\n\n".join(new_notes)
            send_wechat(title, content)
            save_history(history)
        else:
            print("⭕ 无新增笔记")
            send_wechat("✅ 监控运行正常", f"脚本运行完毕，暂无关于“韶关”的新内容。\n时间: {time.strftime('%H:%M')}")

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"❌ 错误: {error_msg}")
        send_wechat("⚠️ 监控脚本出错", f"详情：\n{str(e)}")
        raise e

if __name__ == "__main__":
    main()
