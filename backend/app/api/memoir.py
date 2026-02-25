from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db, SessionLocal
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
    content: Optional[str]
    order_index: int
    conversation_id: Optional[str] = None

    class Config:
        from_attributes = True


class MemoirListItem(BaseModel):
    id: str
    title: str
    status: str
    order_index: int
    conversation_start: Optional[str] = None
    conversation_end: Optional[str] = None

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


def complete_memoir_background(memoir_id: str, perspective: str):
    """后台完成回忆录内容生成"""
    db = SessionLocal()
    try:
        print(f"[Memoir] 开始生成回忆录内容: memoir_id={memoir_id}")
        memoir_service.complete_generation(db, memoir_id, perspective)
        print(f"[Memoir] 回忆录生成完成: memoir_id={memoir_id}")
    except Exception as e:
        print(f"[Memoir] 回忆录生成失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


@router.post("/generate-async")
def generate_memoir_async(
    user_id: str,
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """异步生成回忆录（立即返回）"""
    # 先创建一个"撰写中"状态的回忆录（包含标题）
    memoir = memoir_service.create_generating(
        db=db,
        user_id=user_id,
        conversation_id=request.conversation_id
    )

    # 后台生成内容
    background_tasks.add_task(
        complete_memoir_background,
        memoir.id,
        request.perspective
    )

    return {"status": "started", "memoir_id": memoir.id, "title": memoir.title}


@router.get("/user/{user_id}/list")
def list_memoirs(user_id: str, db: Session = Depends(get_db)):
    """获取用户的回忆录列表"""
    memoirs = memoir_service.get_user_memoirs(db, user_id)

    result = []
    for memoir in memoirs:
        item = {
            "id": memoir.id,
            "title": memoir.title,
            "status": memoir.status or "completed",
            "order_index": memoir.order_index,
            "conversation_start": None,
            "conversation_end": None
        }

        # 获取对话时间
        if memoir.conversation:
            if memoir.conversation.created_at:
                item["conversation_start"] = memoir.conversation.created_at.strftime("%Y-%m-%d %H:%M")
            if memoir.conversation.updated_at:
                item["conversation_end"] = memoir.conversation.updated_at.strftime("%Y-%m-%d %H:%M")

        result.append(item)

    return result


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


class RegenerateRequest(BaseModel):
    perspective: Optional[str] = "第一人称"


@router.post("/{memoir_id}/regenerate", response_model=MemoirResponse)
def regenerate_memoir(memoir_id: str, request: RegenerateRequest, db: Session = Depends(get_db)):
    """重新生成回忆录内容"""
    memoir = memoir_service.regenerate(
        db=db,
        memoir_id=memoir_id,
        perspective=request.perspective
    )
    if not memoir:
        raise HTTPException(status_code=404, detail="回忆录不存在或无法重新生成")
    return memoir
