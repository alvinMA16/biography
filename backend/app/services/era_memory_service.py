"""
时代记忆服务
提供预生成时代记忆的查询和截取功能
"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import EraMemoryPreset
from app.config import settings


class EraMemoryService:
    """时代记忆服务"""

    def get_all(self, db: Session) -> List[EraMemoryPreset]:
        """获取所有预生成的时代记忆"""
        return db.query(EraMemoryPreset).order_by(EraMemoryPreset.start_year).all()

    def get_by_id(self, db: Session, memory_id: str) -> Optional[EraMemoryPreset]:
        """根据 ID 获取时代记忆"""
        return db.query(EraMemoryPreset).filter(EraMemoryPreset.id == memory_id).first()

    def get_for_year_range(self, db: Session, year_start: int, year_end: int) -> List[EraMemoryPreset]:
        """
        根据年份区间获取时代记忆
        返回所有与 [year_start, year_end] 有交集的事件
        """
        return db.query(EraMemoryPreset).filter(
            EraMemoryPreset.start_year <= year_end,
            EraMemoryPreset.end_year >= year_start
        ).order_by(EraMemoryPreset.start_year).all()

    def get_for_topic(
        self,
        db: Session,
        birth_year: int,
        age_start: int,
        age_end: int
    ) -> str:
        """
        根据用户出生年份和话题年龄范围获取时代记忆文本

        Args:
            birth_year: 用户出生年份
            age_start: 话题对应的起始年龄
            age_end: 话题对应的结束年龄

        Returns:
            拼接好的时代记忆文本，可直接注入 prompt
        """
        # 计算年份区间
        year_start = birth_year + age_start
        year_end = birth_year + age_end

        # 查询时代记忆
        memories = self.get_for_year_range(db, year_start, year_end)

        if not memories:
            return ""

        # 拼接成文本
        lines = []
        for m in memories:
            if m.start_year == m.end_year:
                lines.append(f"- {m.content} ({m.start_year}年)")
            else:
                lines.append(f"- {m.content} ({m.start_year}-{m.end_year}年)")

        return "\n".join(lines)

    def should_use_preset(self) -> bool:
        """判断是否应该使用预生成的时代记忆"""
        return settings.service_region == "CN"

    def create(
        self,
        db: Session,
        start_year: int,
        end_year: int,
        content: str,
        category: Optional[str] = None
    ) -> EraMemoryPreset:
        """创建时代记忆条目"""
        import uuid
        memory = EraMemoryPreset(
            id=str(uuid.uuid4()),
            start_year=start_year,
            end_year=end_year,
            content=content,
            category=category
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return memory

    def update(
        self,
        db: Session,
        memory_id: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        content: Optional[str] = None,
        category: Optional[str] = None
    ) -> Optional[EraMemoryPreset]:
        """更新时代记忆条目"""
        memory = self.get_by_id(db, memory_id)
        if not memory:
            return None

        if start_year is not None:
            memory.start_year = start_year
        if end_year is not None:
            memory.end_year = end_year
        if content is not None:
            memory.content = content
        if category is not None:
            memory.category = category

        db.commit()
        db.refresh(memory)
        return memory

    def delete(self, db: Session, memory_id: str) -> bool:
        """删除时代记忆条目"""
        memory = self.get_by_id(db, memory_id)
        if not memory:
            return False

        db.delete(memory)
        db.commit()
        return True


era_memory_service = EraMemoryService()
