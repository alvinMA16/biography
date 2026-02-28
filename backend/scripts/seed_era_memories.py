"""
从 era_memories.md 导入预设时代记忆数据到 era_memories_preset 表
"""
import sys
import os
import uuid
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal
from app.models.user import EraMemoryPreset

MD_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'era_memories.md')


def parse_md_table(filepath):
    """解析 markdown 表格，返回记录列表"""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        # 跳过表头、分隔行、空行
        if not line or line.startswith('| start_year') or line.startswith('|---') or line.startswith('| -'):
            continue
        # 解析数据行: | start_year | end_year | category | content |
        parts = [p.strip() for p in line.split('|')]
        # split('|') 会在首尾产生空字符串
        parts = [p for p in parts if p != '']
        if len(parts) < 4:
            continue

        start_year_str = parts[0].strip()
        end_year_str = parts[1].strip()
        category = parts[2].strip()
        content = parts[3].strip()

        # 处理 "至今" -> 2026
        try:
            start_year = int(start_year_str)
        except ValueError:
            continue
        if end_year_str == '至今':
            end_year = 2026
        else:
            try:
                end_year = int(end_year_str)
            except ValueError:
                continue

        # category 映射: "科技发展" -> "科技变迁" (与现有 schema 保持一致)
        category_map = {
            '科技发展': '科技变迁',
        }
        category = category_map.get(category, category)

        records.append({
            'start_year': start_year,
            'end_year': end_year,
            'category': category,
            'content': content,
        })

    return records


def main():
    if not os.path.exists(MD_FILE):
        print(f"[ERROR] 找不到文件: {MD_FILE}")
        return

    records = parse_md_table(MD_FILE)
    print(f"[解析] 从 md 文件读取到 {len(records)} 条记录")

    if not records:
        print("[ERROR] 无数据，退出")
        return

    db = SessionLocal()

    # 检查现有数据
    existing = db.query(EraMemoryPreset).count()
    if existing > 0:
        print(f"[WARNING] 表中已有 {existing} 条数据")
        confirm = input("是否清空后重新导入？(y/N): ")
        if confirm.lower() != 'y':
            print("取消")
            db.close()
            return
        db.query(EraMemoryPreset).delete()
        db.commit()
        print("已清空")

    count = 0
    for rec in records:
        memory = EraMemoryPreset(
            id=str(uuid.uuid4()),
            start_year=rec['start_year'],
            end_year=rec['end_year'],
            content=rec['content'],
            category=rec['category'],
        )
        db.add(memory)
        count += 1

    db.commit()
    print(f"[完成] 共写入 {count} 条时代记忆")
    db.close()


if __name__ == "__main__":
    main()
