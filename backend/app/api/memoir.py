from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.services.memoir_service import memoir_service

router = APIRouter()


class GenerateRequest(BaseModel):
    conversation_id: str
    title: Optional[str] = None
    perspective: Optional[str] = "第一人称"


class UpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class MemoirResponse(BaseModel):
    id: str
    title: str
    content: str
    order_index: int

    class Config:
        from_attributes = True


class MemoirListItem(BaseModel):
    id: str
    title: str
    order_index: int

    class Config:
        from_attributes = True


@router.post("/generate", response_model=MemoirResponse)
def generate_memoir(user_id: str, request: GenerateRequest, db: Session = Depends(get_db)):
    """从对话生成回忆录"""
    memoir = memoir_service.generate_from_conversation(
        db=db,
        user_id=user_id,
        conversation_id=request.conversation_id,
        title=request.title,
        perspective=request.perspective
    )
    return memoir


@router.get("/user/{user_id}/list", response_model=List[MemoirListItem])
def list_memoirs(user_id: str, db: Session = Depends(get_db)):
    """获取用户的回忆录列表"""
    return memoir_service.get_user_memoirs(db, user_id)


@router.get("/{memoir_id}", response_model=MemoirResponse)
def get_memoir(memoir_id: str, db: Session = Depends(get_db)):
    """获取回忆录详情"""
    memoir = memoir_service.get_memoir(db, memoir_id)
    if not memoir:
        raise HTTPException(status_code=404, detail="回忆录不存在")
    return memoir


@router.put("/{memoir_id}", response_model=MemoirResponse)
def update_memoir(memoir_id: str, request: UpdateRequest, db: Session = Depends(get_db)):
    """更新回忆录"""
    memoir = memoir_service.update_memoir(
        db=db,
        memoir_id=memoir_id,
        title=request.title,
        content=request.content
    )
    if not memoir:
        raise HTTPException(status_code=404, detail="回忆录不存在")
    return memoir


@router.delete("/{memoir_id}")
def delete_memoir(memoir_id: str, db: Session = Depends(get_db)):
    """删除回忆录"""
    success = memoir_service.delete_memoir(db, memoir_id)
    if not success:
        raise HTTPException(status_code=404, detail="回忆录不存在")
    return {"message": "删除成功"}
