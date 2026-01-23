import os
import json
import time
import hashlib
import requests
import traceback
from xhs import XhsClient

# --- 🎯 核心配置区 (已修改) ---

# 1. 搜索关键词 (改成了更短、更广的大词)
# 逻辑：先用大词把帖子捞出来，再用下面的过滤器筛选
SEARCH_KEYWORDS = [
    "韶关 妇幼",   # 组合搜
    "韶关 产科",
    "韶关 生产",
    "韶关 生孩子",
    "韶关 避雷",   # 重点监控
    "妇幼保健院"   # 搜全名，依靠后面的 MUST_INCLUDE 来过滤地域
]

# 2. 地域/相关性过滤器 (防止搜到北京/上海的帖子)
# 只要帖子内容里包含以下【任意一个】词，就会被保留，否则丢弃
# 如果你想看全中国的妇幼新闻，就把这就改成: MUST_INCLUDE = []
MUST_INCLUDE = [
    "韶关", "武江", "浈江", "曲江", "翁源", "乳源", "始兴", 
    "仁化", "新丰", "乐昌", "南雄", "广东"
] 

# 3. 负面敏感词 (高亮标记)
NEGATIVE_WORDS = ["避雷", "坑", "差", "事故", "垃圾", "无语", "投诉", "死", "黑", "医疗纠纷"]

# 4. 抓取深度 (为了覆盖一天，我们多抓一点)
MAX_NOTES_PER_KEYWORD = 50 

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
    """清洗 Cookie"""
    if not raw_input: return ""
    try:
        cookie_dict = json.loads(raw_input)
        if isinstance(cookie_dict, dict):
            return "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
    except:
        pass
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

def check_relevance(text):
    """
    地域过滤逻辑：
    如果 MUST_INCLUDE 为空，则不过滤（看全中国）。
    如果不为空，则必须包含至少一个地名。
    """
    if not MUST_INCLUDE:
        return True
    for word in MUST_INCLUDE:
        if word in text: return True
    return False

def main():
    print(">>> 启动小红书广域监控 (24小时版)...")
    
    try:
        # 1. Cookie 检查
        final_cookie = get_valid_cookie_string(COOKIE_RAW)
        if not final_cookie or len(final_cookie) < 50:
            raise ValueError("Cookie 为空或无效，请去 GitHub 更新 Secrets！")

        client = XhsClient(cookie=final_cookie)

        # 2. 活性检测
        print("🔍 正在检测 Cookie 活性...")
        try:
            client.get_note_by_keyword("你好", page=1, page_size=1)
        except Exception as e:
            send_wechat("🚨 Cookie 失效报警", f"请立即更新 Cookie。\n错误信息：{e}")
            return

        print("✅ 检测通过，开始大范围扫描...")
        history = load_history()
        new_notes = []
        
        for keyword in SEARCH_KEYWORDS:
            print(f"正在深度搜索: {keyword} (Top {MAX_NOTES_PER_KEYWORD})")
            
            # 我们这里循环翻页，直到抓够 50 条，确保覆盖“一天内”
            # 小红书每页通常 20 条，所以我们要抓 3 页
            fetched_count = 0
            page = 1
            
            while fetched_count < MAX_NOTES_PER_KEYWORD:
                try:
                    # sort='time' 保证抓到的是最新的
                    notes = client.get_note_by_keyword(keyword, sort='time', page=page, page_size=20)
                except Exception as e:
                    print(f"⚠️ 翻页出错: {e}")
                    break

                if not notes or 'items' not in notes or not notes['items']:
                    break # 没数据了，停止

                for note in notes['items']:
                    fetched_count += 1
                    
                    note_id = note.get('id')
                    card = note.get('note_card', {})
                    title = card.get('display_title', '无标题')
                    desc = card.get('desc', '')
                    user = card.get('user', {}).get('nickname', '未知')
                    
                    full_text = title + desc
                    
                    # 1. 地域/相关性过滤 (关键！)
                    if not check_relevance(full_text): 
                        continue
                    
                    # 2. 去重
                    uid = hashlib.md5(note_id.encode()).hexdigest()
                    if uid in history: continue
                    history.add(uid)
                    
                    # 3. 组装
                    is_risk = any(w in full_text for w in NEGATIVE_WORDS)
                    emoji = "🔴" if is_risk else "📝"
                    risk_tag = "**[⚠️高危]** " if is_risk else ""
                    
                    link = f"https://www.xiaohongshu.com/explore/{note_id}"
                    entry = f"{emoji} {risk_tag}**[{title}]({link})**\n> 👤 {user}\n> 📄 {desc[:40]}..."
                    new_notes.append(entry)
                
                # 翻下一页
                page += 1
                time.sleep(2) # 礼貌等待

        if new_notes:
            print(f"✅ 筛选出 {len(new_notes)} 条有效本地情报")
            # 这里的标题改一下，显得更专业
            title = f"📢 妇幼舆情日报 ({len(new_notes)}条)"
            content = "#### 🔍 24小时全网监测\n\n" + "\n\n".join(new_notes)
            send_wechat(title, content)
            save_history(history)
        else:
            print("⭕ 暂无新增本地相关情报")
            send_wechat("✅ 监控正常", f"已完成 24小时 范围搜索。\n关键词覆盖：{SEARCH_KEYWORDS}\n未发现韶关及周边相关新增内容。")

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"❌ 运行崩溃: {error_msg}")
        send_wechat("⚠️ 监控脚本崩溃", f"详情：\n{str(e)}")
        raise e

if __name__ == "__main__":
    main()
