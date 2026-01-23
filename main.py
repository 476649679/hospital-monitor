import os
import json
import time
import hashlib
import requests
import traceback
from xhs import XhsClient

# --- 核心配置 ---
MUST_INCLUDE = ["的"] 
SEARCH_KEYWORDS = ["产科","韶关市妇幼保健院", "韶关妇幼", "韶关 产科", "韶关 避雷"]
NEGATIVE_WORDS = ["避雷", "坑", "差", "事故", "垃圾", "无语", "投诉", "死", "黑"]

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

def get_valid_cookie_string(raw_input):
    """清洗 Cookie 格式"""
    if not raw_input: return None
    try:
        cookie_dict = json.loads(raw_input)
        if isinstance(cookie_dict, dict):
            return "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
    except:
        pass
    clean_str = raw_input.strip()
    if clean_str.startswith('"') and clean_str.endswith('"'):
        clean_str = clean_str[1:-1]
    return clean_str

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

def validate_cookie_alive(client):
    """
    【看门狗机制】
    尝试搜索一个绝对热门的词（如"小红书"），如果返回空，说明Cookie已死
    """
    try:
        print("🔍 正在进行 Cookie 活性检测...")
        # 搜索"你好"，理论上必定有结果
        test_notes = client.get_note_by_keyword("你好", page=1, page_size=1)
        
        # 如果返回的数据结构不对，或者 items 为空，说明 Cookie 只是在"空转"
        if not test_notes or 'items' not in test_notes or len(test_notes['items']) == 0:
            return False, "API返回数据为空（隐性失效）"
            
        return True, "Cookie 活性正常"
    except Exception as e:
        # 如果直接抛出异常，更是失效了
        return False, str(e)

def main():
    print(">>> 启动小红书监控 (防假死版)...")
    
    try:
        if not COOKIE_RAW:
            raise ValueError("未设置 XHS_COOKIE")

        final_cookie = get_valid_cookie_string(COOKIE_RAW)
        client = XhsClient(cookie=final_cookie)
        
        # --- 1. 先进行看门狗检查 ---
        is_alive, reason = validate_cookie_alive(client)
        if not is_alive:
            print(f"❌ 检测到 Cookie 失效: {reason}")
            send_wechat(
                "🚨 严重报警：Cookie已失效", 
                f"监控脚本检测到 Cookie 已无法获取数据。\n\n原因：{reason}\n\n👉 **请立即去 GitHub 更新 Cookie**，否则监控将停止。"
            )
            return # 直接结束，不再做无用功

        # --- 2. 只有检测通过才开始正常任务 ---
        print("✅ Cookie 检测通过，开始执行监控任务...")
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
            send_wechat("✅ 监控正常", f"脚本运行正常，Cookie 活性检测通过。\n暂无关于“韶关”的新内容。\n检测时间: {time.strftime('%H:%M')}")

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"❌ 错误: {error_msg}")
        send_wechat("⚠️ 监控脚本出错", f"详情：\n{str(e)}")
        raise e

if __name__ == "__main__":
    main()
