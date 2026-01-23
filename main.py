import os
import json
import time
import hashlib
import requests
import traceback
from xhs import XhsClient

# --- 核心配置 ---
# 只要包含"韶关"就抓取
MUST_INCLUDE = ["韶关"] 
SEARCH_KEYWORDS = ["韶关市妇幼保健院", "韶关妇幼", "韶关 产科", "韶关 避雷"]
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
    """
    【核心修复】
    不管输入是 JSON 还是普通文本，最后强制转换成 'k=v; k=v' 的字符串
    解决 'dict object has no attribute split' 问题
    """
    if not raw_input:
        return None
    
    # 1. 尝试看看是不是 JSON 格式的字典
    try:
        cookie_dict = json.loads(raw_input)
        if isinstance(cookie_dict, dict):
            # 如果是字典，把它拼回成字符串 "key=value; key=value"
            print("检测到 JSON 格式 Cookie，正在转换为字符串...")
            cookie_parts = []
            for k, v in cookie_dict.items():
                cookie_parts.append(f"{k}={v}")
            return "; ".join(cookie_parts)
    except:
        pass # 不是 JSON，那说明本身就是字符串
    
    # 2. 如果本身就是字符串，直接用，但清理一下首尾空格/引号
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

def main():
    print(">>> 启动小红书监控 (字符串强制版)...")
    
    try:
        # 1. 获取并处理 Cookie
        if not COOKIE_RAW:
            raise ValueError("未设置 XHS_COOKIE")

        # 强制转换为字符串
        final_cookie = get_valid_cookie_string(COOKIE_RAW)
        
        # 打印一下类型（不打印内容）确认修复
        print(f"Cookie 类型已修正为: {type(final_cookie)}") 

        # 2. 初始化客户端 (传入字符串)
        client = XhsClient(cookie=final_cookie)
        
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
        # 抛出异常确保 Action 变红
        raise e

if __name__ == "__main__":
    main()
