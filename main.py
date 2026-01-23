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
    """清洗并确保 Cookie 是纯净的字符串"""
    if not raw_input: return ""
    try:
        # 尝试处理可能是 JSON 的情况
        cookie_dict = json.loads(raw_input)
        if isinstance(cookie_dict, dict):
            return "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
    except:
        pass
    # 否则直接返回去空格的字符串
    return str(raw_input).strip().strip('"').strip("'")

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

def main():
    print(">>> 启动小红书监控 (稳定性增强版)...")
    
    try:
        # 1. Cookie 深度检查
        final_cookie = get_valid_cookie_string(COOKIE_RAW)
        if not final_cookie or len(final_cookie) < 50:
            raise ValueError("Cookie 太短或为空，请重新从浏览器获取完整 Cookie。")

        # 2. 初始化客户端
        client = XhsClient(cookie=final_cookie)
        
        # 3. 核心功能可用性预检 (预防 'NoneType' object is not callable)
        if not hasattr(client, 'get_note_by_keyword') or client.get_note_by_keyword is None:
            raise TypeError("小红书接口初始化失败，通常是由于 Cookie 格式不被接受，请重新获取。")

        # 4. 执行活性检测
        print("🔍 正在探测 Cookie 活性...")
        try:
            # 搜索一个必定有结果的词
            test = client.get_note_by_keyword("你好", page=1, page_size=1)
            if not test or 'items' not in test or not test['items']:
                # 虽然没报错，但没数据，说明 Cookie 被小红书拦截了
                send_wechat("🚨 监控假死警告", "Cookie 虽然能用，但搜索不到任何数据。可能账号被风控或需要更新 Cookie。")
                return
        except Exception as e:
            # 活性检测直接报错，说明 Cookie 彻底坏了
            send_wechat("🚨 Cookie 已失效", f"小红书拒绝了连接请求。\n错误详情：{str(e)}\n请立即更新 GitHub Secrets。")
            return

        # 5. 正常监控逻辑
        print("✅ 活性检测通过，开始扫描...")
        history = load_history()
        new_notes = []
        
        for keyword in SEARCH_KEYWORDS:
            print(f"搜索关键词: {keyword}")
            notes = client.get_note_by_keyword(keyword, sort='time', page=1, page_size=15)
            
            if not notes or 'items' not in notes: continue

            for note in notes['items']:
                note_id = note.get('id')
                card = note.get('note_card', {})
                title = card.get('display_title', '无标题')
                desc = card.get('desc', '')
                
                # 关键词过滤
                full_text = title + desc
                if not any(word in full_text for word in MUST_INCLUDE): continue
                
                # 去重
                uid = hashlib.md5(note_id.encode()).hexdigest()
                if uid in history: continue
                history.add(uid)
                
                # 危险判定
                is_risk = any(w in full_text for w in NEGATIVE_WORDS)
                emoji = "🔴" if is_risk else "📝"
                risk_tag = "**[⚠️高危]** " if is_risk else ""
                
                link = f"https://www.xiaohongshu.com/explore/{note_id}"
                new_notes.append(f"{emoji} {risk_tag}**[{title}]({link})**\n> {desc[:40]}...")
            
            time.sleep(3) # 稍微慢一点，更像真人

        # 6. 推送结果
        if new_notes:
            send_wechat(f"📢 发现 {len(new_notes)} 条新笔记", "#### 🔍 监控日报\n\n" + "\n\n".join(new_notes))
            save_history(history)
        else:
            # 每天还是发个心跳回执
            send_wechat("✅ 监控运行正常", f"脚本运行完毕，暂无关于“韶关”的新内容。\n时间: {time.strftime('%H:%M')}")

    except Exception as e:
        error_msg = str(e)
        # 捕捉致命错误直接微信报送
        print(f"❌ 运行崩溃: {error_msg}")
        send_wechat("⚠️ 监控脚本崩溃", f"脚本发生致命错误：\n\n`{error_msg}`\n\n请检查 Cookie 是否填写正确或已过期。")
        raise e

if __name__ == "__main__":
    main()
