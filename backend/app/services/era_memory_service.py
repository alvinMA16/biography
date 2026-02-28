"""
时代记忆服务
提供预生成时代记忆的查询和截取功能
首次访问时从数据库加载全量数据到内存，后续查询走缓存
"""
import datetime
import logging
import uuid
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import EraMemoryPreset
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EraMemoryItem:
    """内存中的时代记忆条目（脱离 SQLAlchemy session）"""
    id: str
    start_year: int
    end_year: int
    category: Optional[str]
    content: str


class EraMemoryService:
    """时代记忆服务（带内存缓存）"""

    def __init__(self):
        self._cache: Optional[List[EraMemoryItem]] = None

    def _ensure_cache(self, db: Session) -> List[EraMemoryItem]:
        """首次调用时从数据库加载全量数据到内存"""
        if self._cache is None:
            rows = db.query(EraMemoryPreset).order_by(EraMemoryPreset.start_year).all()
            self._cache = [
                EraMemoryItem(
                    id=r.id,
                    start_year=r.start_year,
                    end_year=r.end_year,
                    category=r.category,
                    content=r.content,
                )
                for r in rows
            ]
            logger.info(f"时代记忆缓存已加载，共 {len(self._cache)} 条")
        return self._cache

    def _invalidate_cache(self):
        """写操作后清空缓存，下次查询时重新加载"""
        self._cache = None

    def get_all(self, db: Session) -> List[EraMemoryItem]:
        """获取所有预生成的时代记忆"""
        return self._ensure_cache(db)

    def get_by_id(self, db: Session, memory_id: str) -> Optional[EraMemoryItem]:
        """根据 ID 获取时代记忆"""
        for m in self._ensure_cache(db):
            if m.id == memory_id:
                return m
        return None

    def get_for_year_range(self, db: Session, year_start: int, year_end: int) -> List[EraMemoryItem]:
        """
        根据年份区间获取时代记忆
        返回所有与 [year_start, year_end] 有交集的事件
        """
        return [
            m for m in self._ensure_cache(db)
            if m.start_year <= year_end and m.end_year >= year_start
        ]

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
        year_start = birth_year + age_start
        year_end = birth_year + age_end

        memories = self.get_for_year_range(db, year_start, year_end)

        if not memories:
            return ""

        lines = []
        for m in memories:
            if m.start_year == m.end_year:
                lines.append(f"- {m.content} ({m.start_year}年)")
            else:
                lines.append(f"- {m.content} ({m.start_year}-{m.end_year}年)")

        return "\n".join(lines)

    def get_for_user(self, db: Session, birth_year: int) -> str:
        """
        获取用户全部人生范围的时代记忆文本（用于话题生成等场景）

        Args:
            birth_year: 用户出生年份

        Returns:
            拼接好的时代记忆文本
        """
        current_year = datetime.datetime.now().year
        year_start = birth_year + 6  # 从童年开始
        year_end = current_year

        memories = self.get_for_year_range(db, year_start, year_end)

        if not memories:
            return ""

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
        self._invalidate_cache()
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
        memory = db.query(EraMemoryPreset).filter(EraMemoryPreset.id == memory_id).first()
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
        self._invalidate_cache()
        return memory

    def delete(self, db: Session, memory_id: str) -> bool:
        """删除时代记忆条目"""
        memory = db.query(EraMemoryPreset).filter(EraMemoryPreset.id == memory_id).first()
        if not memory:
            return False

        db.delete(memory)
        db.commit()
        self._invalidate_cache()
        return True


era_memory_service = EraMemoryService()
