import os
import json
import time
import hashlib
import requests
import traceback # 用于捕获详细报错
from xhs import XhsClient

# --- 核心配置 ---
MUST_INCLUDE = ["韶关"] 
SEARCH_KEYWORDS = ["韶关市妇幼保健院", "韶关妇幼", "韶关 产科", "韶关 避雷"]
NEGATIVE_WORDS = ["避雷", "坑", "差", "事故", "垃圾", "无语", "投诉", "死", "黑"]

# 环境变量
COOKIE_STR = os.environ.get("XHS_COOKIE")
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
HISTORY_FILE = "history.json"

def send_wechat(title, content):
    """发送微信推送"""
    if not PUSH_TOKEN: 
        print("❌ 未设置 PUSH_TOKEN，无法推送")
        return
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSH_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown" # 使用 markdown 格式以便显示代码块
    }
    try:
        resp = requests.post(url, json=data, timeout=10)
        print(f"📡 推送状态: {resp.status_code}")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

def manual_cookie_parse(cookie_str):
    """
    【暴力解析】不依赖任何库，手动切割字符串
    解决 'SimpleCookie' 可能解析失败的问题
    """
    if not cookie_str: return {}
    cookies = {}
    # 按分号分割
    for item in cookie_str.split(';'):
        # 只要有等号的都算
        if '=' in item:
            try:
                # 只切第一个等号，防止值里面也有等号
                k, v = item.split('=', 1)
                cookies[k.strip()] = v.strip()
            except:
                continue
    return cookies

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
    except Exception as e:
        print(f"❌ 保存历史文件失败: {e}")

def check_relevance(text):
    for word in MUST_INCLUDE:
        if word in text: return True
    return False

def main():
    print(">>> 启动小红书监控 (调试版)...")
    
    try:
        # 1. 检查 Cookie
        if not COOKIE_STR:
            raise ValueError("未设置 XHS_COOKIE，请去 GitHub Settings 填写！")

        # 2. 转换 Cookie
        print("正在解析 Cookie...")
        cookie_dict = manual_cookie_parse(COOKIE_STR)
        if not cookie_dict:
            raise ValueError("Cookie 解析为空！请检查复制的内容格式是否正确。")
            
        # 3. 初始化客户端
        client = XhsClient(cookie=cookie_dict)
        
        history = load_history()
        new_notes = []
        
        # 4. 循环搜索
        for keyword in SEARCH_KEYWORDS:
            print(f"正在搜索: {keyword}")
            try:
                notes = client.get_note_by_keyword(keyword, sort='time', page=1, page_size=20)
            except Exception as e:
                print(f"⚠️ 搜索 '{keyword}' 失败: {e}")
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
                
                # 过滤
                if not check_relevance(full_text): continue
                
                # 去重
                uid = hashlib.md5(note_id.encode()).hexdigest()
                if uid in history: continue
                history.add(uid)
                
                # 负面判定
                is_risk = any(w in full_text for w in NEGATIVE_WORDS)
                emoji = "🔴" if is_risk else "📝"
                
                link = f"https://www.xiaohongshu.com/explore/{note_id}"
                entry = f"{emoji} **[{title}]({link})**\n> {desc[:50]}..."
                new_notes.append(entry)
            
            time.sleep(2)

        # 5. 推送结果
        if new_notes:
            print(f"✅ 发现 {len(new_notes)} 条新笔记")
            title = f"📢 舆情日报 ({len(new_notes)}条)"
            content = "#### 🔍 监控结果\n\n" + "\n\n".join(new_notes)
            send_wechat(title, content)
            save_history(history)
        else:
            print("⭕ 无新增笔记")
            # 每天还是发个心跳，让你知道它活着
            send_wechat("✅ 监控运行正常", f"脚本运行成功，未发现新内容。\n时间: {time.strftime('%H:%M')}")

    except Exception as e:
        # --- 核心改动：捕捉所有未知错误并推送到微信 ---
        error_msg = traceback.format_exc()
        print(f"❌ 发生致命错误: {error_msg}")
        send_wechat("⚠️ 监控脚本崩溃", f"脚本运行出错，请查看详情：\n\n```\n{str(e)}\n```")
        # 抛出异常让 GitHub Action 依然显示红色，方便查看
        raise e

if __name__ == "__main__":
    main()
