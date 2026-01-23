import os
import json
import time
import hashlib
import requests
from xhs import XhsClient

# --- 核心配置 ---

# 【修改1】把强制包含的词改成一个很通用的字，确保什么都能过
# 原来是: MUST_INCLUDE = ["韶关", "妇幼"] 
MUST_INCLUDE = ["的"]  # 只要文章里有“的”字就能过（几乎等于不过滤）

# 【修改2】搜索词改成超级热门的，保证必定有结果
# 原来是: SEARCH_KEYWORDS = ["韶关市妇幼保健院", "韶关妇幼", ...]
SEARCH_KEYWORDS = ["广东医院", "产科避雷"] 

# 负面敏感词（保持不变）
NEGATIVE_WORDS = ["避雷", "坑", "差", "事故", "垃圾", "无语", "投诉", "死", "黑"]

# 环境变量
COOKIE = os.environ.get("XHS_COOKIE")
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
    # 只保留最后1000条
    data = list(history_set)[-1000:]
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)

def check_relevance(text):
    """【铁律】内容必须包含关键词，否则视为垃圾丢弃"""
    for word in MUST_INCLUDE:
        if word not in text:
            return False
    return True

def main():
    print(">>> 启动小红书精准监控...")
    
    if not COOKIE:
        print("❌ 错误：未设置 XHS_COOKIE")
        # 如果没有Cookie，尝试发一条报错给微信，提醒你去设置
        send_wechat("❌ 监控中断", "请去 GitHub Settings -> Secrets 填写 XHS_COOKIE")
        return

    client = XhsClient(cookie=COOKIE)
    history = load_history()
    new_notes = []
    
    for keyword in SEARCH_KEYWORDS:
        print(f"正在搜索: {keyword}")
        try:
            # 搜索笔记，sort='time' 按时间排序
            notes = client.get_note_by_keyword(keyword, sort='time', page=1, page_size=20)
        except Exception as e:
            print(f"⚠️ 接口报错 (可能是Cookie过期): {e}")
            continue

        if not notes or 'items' not in notes:
            continue

        for note in notes['items']:
            # --- 数据提取 ---
            note_id = note.get('id')
            if not note_id: continue
            
            card = note.get('note_card', {})
            title = card.get('display_title', '无标题')
            desc = card.get('desc', '') # 获取笔记正文摘要
            user = card.get('user', {}).get('nickname', '未知')
            
            # --- 关键过滤步骤 ---
            full_text = title + desc
            
            # 1. 必须包含“韶关”和“妇幼”，否则跳过
            if not check_relevance(full_text):
                continue
                
            # 2. 去重
            uid = hashlib.md5(note_id.encode()).hexdigest()
            if uid in history:
                continue
            
            history.add(uid)
            
            # 3. 负面判定
            is_risk = False
            for risk_word in NEGATIVE_WORDS:
                if risk_word in full_text:
                    is_risk = True
                    break
            
            # --- 组装消息 ---
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
        # 发送心跳，证明脚本活着
        send_wechat("✅ 监控正常", f"脚本运行完毕，未发现关于“韶关妇幼”的新增笔记。\n时间: {time.strftime('%H:%M')}")

if __name__ == "__main__":
    main()
