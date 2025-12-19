# backend/app/main.py

"""
Survey Builder API - FastAPI 메인
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import survey, export, graph  # graph 추가
from .services.graphrag import init_graphrag, close_graphrag


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    # 시작 시
    print("[App] 서버 시작...")
    init_graphrag()
    yield
    # 종료 시
    print("[App] 서버 종료...")
    close_graphrag()


app = FastAPI(
    title="Survey Builder API",
    description="설문지 생성 챗봇 백엔드 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(survey.router)
app.include_router(export.router)
app.include_router(graph.router)  # 🆕 추가

@app.get("/")
async def root():
    return {
        "message": "Survey Builder API",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}