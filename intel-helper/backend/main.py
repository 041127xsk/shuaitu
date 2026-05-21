"""
率土战报情报库 - FastAPI 主应用
"""
import json
import os
import sys
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, get_database, Database
from intel_service import IntelService
from counter_service import CounterService
from logger_config import get_app_logger, get_db_logger, get_ai_logger, log_exception

# 初始化日志
app_logger = get_app_logger()
db_logger = get_db_logger()
ai_logger = get_ai_logger()


# ============================================================================
# 配置
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "screenshots"
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB

# 确保目录存在
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 数据模型
# ============================================================================

class HeroInput(BaseModel):
    name: str
    position: Optional[int] = None
    level: Optional[int] = None
    skill_1: Optional[str] = None
    skill_2: Optional[str] = None
    skill_3: Optional[str] = None


class ConfirmRequest(BaseModel):
    snapshot_id: int
    player_name: str
    season: str
    alliance: Optional[str] = None
    server: Optional[str] = None
    heroes: Optional[List[HeroInput]] = None
    enemy_side: str = "unknown"
    battle_result: str = "unknown"
    notes: Optional[str] = None
    team_name: Optional[str] = None


class CounterAnalyzeRequest(BaseModel):
    observed_team_id: int


class PlayerSearchResponse(BaseModel):
    id: int
    name: str
    alliance: Optional[str]
    server: Optional[str]
    season: str
    team_count: int
    latest_seen: Optional[str]


# ============================================================================
# 生命周期
# ============================================================================

db: Optional[Database] = None
intel_service: Optional[IntelService] = None
counter_service: Optional[CounterService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global db, intel_service, counter_service

    # 记录启动信息
    app_logger.info(f"=" * 50)
    app_logger.info(f"应用启动: 率土战报情报库")
    app_logger.info(f"启动时间: {datetime.now().isoformat()}")
    app_logger.info(f"工作目录: {BASE_DIR}")

    # 启动时初始化
    db_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'intel.db'}")
    db = init_database(db_url)
    intel_service = IntelService(db, str(UPLOAD_DIR))
    counter_service = CounterService(db)

    app_logger.info(f"数据库已初始化: {db_url}")
    app_logger.info(f"上传目录: {UPLOAD_DIR}")

    # 启动时清理未确认的旧快照（超过24小时的）
    try:
        cleaned = intel_service.cleanup_unconfirmed_snapshots(hours=24)
        if cleaned > 0:
            msg = f"启动时清理了 {cleaned} 个未确认的旧快照"
            app_logger.info(msg)
            print(msg)
    except Exception as e:
        msg = f"清理未确认快照时出错: {e}"
        app_logger.warning(msg)
        db_logger.error(msg, exc_info=True)

    yield

    # 关闭时清理
    app_logger.info("应用关闭")
    print("应用关闭")


# ============================================================================
# FastAPI 应用
# ============================================================================

app = FastAPI(
    title="率土战报情报库",
    description="个人战报情报管理工具，支持 OCR 识别、玩家搜索和克制分析",
    version="0.1.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# 异常处理器
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常处理器"""
    path = request.url.path
    method = request.method
    status_code = exc.status_code
    detail = exc.detail
    
    log_msg = f"[{method}] {path} -> {status_code} {detail}"
    
    if status_code >= 500:
        app_logger.error(log_msg)
    elif status_code >= 400:
        app_logger.warning(log_msg)
    else:
        app_logger.info(log_msg)
    
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器 - 捕获所有未处理的异常"""
    path = request.url.path
    method = request.method
    
    log_msg = f"[{method}] {path} 未处理的异常"
    log_exception(app_logger, exc, log_msg)
    
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误: {str(exc)}"}
    )


# ============================================================================
# 静态文件服务
# ============================================================================

# 挂载上传目录
if UPLOAD_DIR.exists():
    app.mount("/screenshots", StaticFiles(directory=str(UPLOAD_DIR)), name="screenshots")

# 挂载战法截图目录
HERO_SKILL_IMAGES_DIR = BASE_DIR / "data" / "hero_skill_images"
if HERO_SKILL_IMAGES_DIR.exists():
    app.mount("/hero_skill_images", StaticFiles(directory=str(HERO_SKILL_IMAGES_DIR)), name="hero_skill_images")

# 挂载前端目录（放在 /static 前缀）
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

# 首页重定向到静态文件
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ============================================================================
# 工具函数
# ============================================================================

def get_intel_service() -> IntelService:
    """获取情报服务实例"""
    if intel_service is None:
        raise HTTPException(status_code=500, detail="服务未初始化")
    return intel_service


def get_counter_service() -> CounterService:
    """获取克制分析服务实例"""
    if counter_service is None:
        raise HTTPException(status_code=500, detail="服务未初始化")
    return counter_service


# ============================================================================
# 健康检查
# ============================================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "intel-helper"}


# ============================================================================
# 战报上传接口
# ============================================================================

@app.post("/intel/upload")
async def upload_screenshot(
    file: UploadFile = File(...),
    season: str = Form(...)
):
    """
    上传战报截图
    - 接收图片文件
    - 保存到 data/screenshots/
    - 计算 image_hash
    - 调用 OCR 模块识别文字
    - 返回 raw_ocr_text 和 suggested 数据
    """
    app_logger.info(f"[Upload] 开始上传文件: {file.filename}, 赛季: {season}")
    
    intel = get_intel_service()

    # 验证文件类型
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        msg = f"不支持的文件类型: {file.content_type}"
        app_logger.warning(f"[Upload] {msg}")
        raise HTTPException(
            status_code=400,
            detail=msg
        )

    # 验证文件大小
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        msg = f"文件大小超过限制: {len(contents) / 1024 / 1024:.1f}MB > {MAX_FILE_SIZE / 1024 / 1024:.1f}MB"
        app_logger.warning(f"[Upload] {msg}")
        raise HTTPException(
            status_code=400,
            detail=msg
        )

    # 保存临时文件
    temp_path = UPLOAD_DIR / f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(contents)

    try:
        # 处理上传 (可能包含 OCR/AI 调用)
        app_logger.info(f"[Upload] 开始处理: {temp_path}")
        result = intel.upload_screenshot(str(temp_path), season)
        app_logger.info(f"[Upload] 处理完成, snapshot_id: {result.get('snapshot_id')}")

        # 删除临时文件
        temp_path.unlink(missing_ok=True)

        if not result.get("success"):
            error_msg = result.get("error", "未知错误")
            ai_logger.warning(f"[Upload] 处理失败: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        return result

    except HTTPException:
        raise
    except Exception as e:
        # 删除临时文件
        temp_path.unlink(missing_ok=True)
        error_msg = f"上传处理失败: {str(e)}"
        ai_logger.error(error_msg, exc_info=True)
        app_logger.error(f"[Upload] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/intel/confirm")
async def confirm_intel(request: ConfirmRequest):
    """
    确认并保存情报
    - 用户手动确认后保存
    - 不覆盖历史队伍，每次新增 observed_team
    """
    app_logger.info(f"[Confirm] 确认情报: player={request.player_name}, season={request.season}, snapshot_id={request.snapshot_id}")
    
    intel = get_intel_service()

    # 验证必填字段
    if not request.player_name:
        app_logger.warning("[Confirm] 玩家名为空")
        raise HTTPException(status_code=400, detail="玩家名不能为空")
    if not request.season:
        app_logger.warning("[Confirm] 赛季为空")
        raise HTTPException(status_code=400, detail="赛季不能为空")

    # 处理武将数据
    heroes = None
    if request.heroes:
        heroes = [h.model_dump() for h in request.heroes]
        app_logger.info(f"[Confirm] 武将数量: {len(heroes)}")

    try:
        result = intel.confirm_intel(
            snapshot_id=request.snapshot_id,
            player_name=request.player_name,
            season=request.season,
            alliance=request.alliance,
            server=request.server,
            heroes=heroes,
            enemy_side=request.enemy_side,
            battle_result=request.battle_result,
            notes=request.notes,
            team_name=request.team_name
        )

        if not result.get("success"):
            error_msg = result.get("error", "确认失败")
            db_logger.error(f"[Confirm] 保存失败: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        app_logger.info(f"[Confirm] 确认成功: {result.get('message')}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"保存情报失败: {str(e)}"
        db_logger.error(error_msg, exc_info=True)
        app_logger.error(f"[Confirm] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/intel/snapshots")
async def list_snapshots(
    confirmed: Optional[bool] = None,
    limit: int = Query(default=50, ge=1, le=100)
):
    """列出快照"""
    intel = get_intel_service()

    with db.get_session() as session:
        from database import IntelSnapshot
        query = session.query(IntelSnapshot)

        if confirmed is not None:
            query = query.filter(IntelSnapshot.confirmed == confirmed)

        snapshots = query.order_by(IntelSnapshot.created_at.desc()).limit(limit).all()

        return [s.to_dict() for s in snapshots]


# ============================================================================
# 玩家搜索接口
# ============================================================================

@app.get("/players/search")
async def search_players(
    q: str = Query(default="", description="搜索关键词"),
    season: Optional[str] = Query(default=None, description="赛季筛选"),
    limit: int = Query(default=20, ge=1, le=100)
):
    """
    搜索玩家
    - 支持模糊搜索
    - 支持按赛季筛选
    - 返回玩家名、同盟、赛季、历史队伍数量、最近出现时间
    """
    intel = get_intel_service()
    results = intel.search_players(q, season, limit)
    return {"results": results, "count": len(results)}


@app.get("/players/{player_id}")
async def get_player_detail(player_id: int):
    """
    获取玩家详情
    - 玩家基础信息
    - 所有历史队伍
    - 每个队伍的武将
    - 每个队伍关联的截图路径
    """
    intel = get_intel_service()
    player = intel.get_player_detail(player_id)

    if not player:
        raise HTTPException(status_code=404, detail="玩家不存在")

    return player


@app.get("/seasons")
async def get_seasons():
    """获取所有赛季列表"""
    intel = get_intel_service()
    seasons = intel.get_all_seasons()
    return {"seasons": seasons}


@app.post("/cleanup/unconfirmed")
async def cleanup_unconfirmed(hours: int = 24):
    """
    清理未确认的旧快照
    - 删除超过指定时间的未确认快照（识别后未保存的）
    - 同时删除对应的截图文件
    """
    intel = get_intel_service()
    deleted_count = intel.cleanup_unconfirmed_snapshots(hours=hours)
    return {"deleted_count": deleted_count, "message": f"已清理 {deleted_count} 个未确认的旧快照"}


@app.get("/players/all")
async def get_all_players():
    """
    获取所有已统计的玩家列表
    - 返回所有玩家及其简要队伍信息
    """
    intel = get_intel_service()
    players = intel.get_all_players()
    return {"players": players, "count": len(players)}


# ============================================================================
# 克制分析接口
# ============================================================================

@app.post("/counter/analyze")
async def analyze_counter(request: CounterAnalyzeRequest):
    """
    克制分析
    - 根据敌方队伍武将 tags 判断敌方队伍类型
    - 输出 enemy_tags
    - 输出推荐克制方向
    """
    counter = get_counter_service()
    result = counter.analyze_team(request.observed_team_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@app.get("/counter/batch/{player_id}")
async def batch_analyze(player_id: int):
    """批量分析玩家的所有队伍"""
    counter = get_counter_service()
    result = counter.batch_analyze(player_id)
    return result


# ============================================================================
# 武将接口
# ============================================================================

@app.get("/heroes")
async def list_heroes():
    """获取所有武将列表"""
    intel = get_intel_service()
    heroes = intel.get_all_heroes()
    return {"heroes": heroes}


@app.get("/heroes/search")
async def search_heroes(q: str = Query(..., min_length=1)):
    """搜索武将"""
    intel = get_intel_service()
    all_heroes = intel.get_all_heroes()

    # 简单模糊匹配
    results = [h for h in all_heroes if q.lower() in h["name"].lower()]
    return {"heroes": results, "count": len(results)}


@app.post("/heroes")
async def create_hero(hero_data: dict):
    """创建武将"""
    from database import Hero
    
    db = get_database()
    with db.get_session() as session:
        # 检查是否已存在
        existing = session.query(Hero).filter(Hero.name == hero_data.get("name")).first()
        if existing:
            raise HTTPException(status_code=400, detail="武将已存在")
        
        hero = Hero(
            name=hero_data.get("name"),
            camp=hero_data.get("camp"),
            troop_type=hero_data.get("troop_type"),
            attack=hero_data.get("attack"),
            defense=hero_data.get("defense"),
            speed=hero_data.get("speed"),
            tags=",".join(hero_data.get("tags", [])) if hero_data.get("tags") else None,
            skill_name=hero_data.get("skill_name"),
            skill_desc=hero_data.get("skill_desc"),
            skill_type=hero_data.get("skill_type"),
            skill_trigger_rate=hero_data.get("skill_trigger_rate"),
            skill_images_json=json.dumps(hero_data.get("skill_images", [])) if hero_data.get("skill_images") else None
        )
        session.add(hero)
        session.flush()
        
        return {"hero": hero.to_dict(), "message": "武将创建成功"}


@app.put("/heroes/{hero_id}")
async def update_hero(hero_id: int, hero_data: dict):
    """更新武将"""
    from database import Hero
    
    db = get_database()
    with db.get_session() as session:
        hero = session.query(Hero).filter(Hero.id == hero_id).first()
        if not hero:
            raise HTTPException(status_code=404, detail="武将不存在")
        
        # 更新字段
        if "name" in hero_data:
            hero.name = hero_data["name"]
        if "camp" in hero_data:
            hero.camp = hero_data["camp"]
        if "troop_type" in hero_data:
            hero.troop_type = hero_data["troop_type"]
        if "attack" in hero_data:
            hero.attack = hero_data["attack"]
        if "defense" in hero_data:
            hero.defense = hero_data["defense"]
        if "speed" in hero_data:
            hero.speed = hero_data["speed"]
        if "tags" in hero_data:
            hero.tags = ",".join(hero_data["tags"]) if hero_data["tags"] else None
        if "skill_name" in hero_data:
            hero.skill_name = hero_data["skill_name"]
        if "skill_desc" in hero_data:
            hero.skill_desc = hero_data["skill_desc"]
        if "skill_type" in hero_data:
            hero.skill_type = hero_data["skill_type"]
        if "skill_trigger_rate" in hero_data:
            hero.skill_trigger_rate = hero_data["skill_trigger_rate"]
        if "skill_images" in hero_data:
            hero.skill_images_json = json.dumps(hero_data["skill_images"]) if hero_data["skill_images"] else None
        
        return {"hero": hero.to_dict(), "message": "武将更新成功"}


@app.delete("/heroes/{hero_id}")
async def delete_hero(hero_id: int):
    """删除武将"""
    from database import Hero

    db = get_database()
    with db.get_session() as session:
        hero = session.query(Hero).filter(Hero.id == hero_id).first()
        if not hero:
            raise HTTPException(status_code=404, detail="武将不存在")

        hero_name = hero.name
        session.delete(hero)

        return {"message": f"武将 {hero_name} 已删除"}


# ============================================================================
# 玩家队伍 CRUD 接口
# ============================================================================

class PlayerTeamCreate(BaseModel):
    player_id: str
    team_name: str
    hero_lineup: Optional[List[str]] = []
    level: Optional[int] = 1
    power: Optional[int] = 0
    notes: Optional[str] = None


class PlayerTeamUpdate(BaseModel):
    player_id: Optional[str] = None
    team_name: Optional[str] = None
    hero_lineup: Optional[List[str]] = None
    level: Optional[int] = None
    power: Optional[int] = None
    notes: Optional[str] = None


@app.post("/player-teams")
async def create_player_team(team_data: PlayerTeamCreate):
    """创建玩家队伍"""
    from database import PlayerTeam
    
    app_logger.info(f"[PlayerTeam] 创建队伍: player={team_data.player_id}, name={team_data.team_name}")

    try:
        with db.get_session() as session:
            team = PlayerTeam(
                player_id=team_data.player_id,
                team_name=team_data.team_name,
                hero_lineup=json.dumps(team_data.hero_lineup) if team_data.hero_lineup is not None else None,
                level=team_data.level,
                power=team_data.power,
                notes=team_data.notes
            )
            session.add(team)
            session.flush()
            result = {"team": team.to_dict(), "message": "队伍创建成功"}
            app_logger.info(f"[PlayerTeam] 创建成功: id={team.id}")
            return result
    except Exception as e:
        error_msg = f"创建队伍失败: {str(e)}"
        db_logger.error(error_msg, exc_info=True)
        app_logger.error(f"[PlayerTeam] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/player-teams")
async def list_player_teams(player_id: Optional[str] = None):
    """获取玩家队伍列表"""
    from database import PlayerTeam

    app_logger.info(f"[PlayerTeam] 查询列表: player_id={player_id or '全部'}")

    try:
        with db.get_session() as session:
            query = session.query(PlayerTeam)
            if player_id:
                query = query.filter(PlayerTeam.player_id == player_id)
            teams = query.order_by(PlayerTeam.updated_at.desc()).all()
            return {"teams": [t.to_dict() for t in teams], "count": len(teams)}
    except Exception as e:
        error_msg = f"查询队伍列表失败: {str(e)}"
        db_logger.error(error_msg, exc_info=True)
        app_logger.error(f"[PlayerTeam] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/player-teams/{team_id}")
async def get_player_team(team_id: int):
    """获取单个队伍详情"""
    from database import PlayerTeam

    app_logger.info(f"[PlayerTeam] 查询详情: team_id={team_id}")

    try:
        with db.get_session() as session:
            team = session.query(PlayerTeam).filter(PlayerTeam.id == team_id).first()
            if not team:
                app_logger.warning(f"[PlayerTeam] 队伍不存在: id={team_id}")
                raise HTTPException(status_code=404, detail="队伍不存在")
            return team.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"查询队伍详情失败: {str(e)}"
        db_logger.error(error_msg, exc_info=True)
        app_logger.error(f"[PlayerTeam] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.put("/player-teams/{team_id}")
async def update_player_team(team_id: int, team_data: PlayerTeamUpdate):
    """更新玩家队伍"""
    from database import PlayerTeam

    app_logger.info(f"[PlayerTeam] 更新队伍: team_id={team_id}")

    try:
        with db.get_session() as session:
            team = session.query(PlayerTeam).filter(PlayerTeam.id == team_id).first()
            if not team:
                app_logger.warning(f"[PlayerTeam] 队伍不存在: id={team_id}")
                raise HTTPException(status_code=404, detail="队伍不存在")

            if team_data.player_id is not None:
                team.player_id = team_data.player_id
            if team_data.team_name is not None:
                team.team_name = team_data.team_name
            if team_data.hero_lineup is not None:
                team.hero_lineup = json.dumps(team_data.hero_lineup)
            if team_data.level is not None:
                team.level = team_data.level
            if team_data.power is not None:
                team.power = team_data.power
            if team_data.notes is not None:
                team.notes = team_data.notes
            
            result = {"team": team.to_dict(), "message": "队伍更新成功"}
            app_logger.info(f"[PlayerTeam] 更新成功: id={team_id}")
            return result
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"更新队伍失败: {str(e)}"
        db_logger.error(error_msg, exc_info=True)
        app_logger.error(f"[PlayerTeam] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.delete("/player-teams/{team_id}")
async def delete_player_team(team_id: int):
    """删除玩家队伍"""
    from database import PlayerTeam

    app_logger.info(f"[PlayerTeam] 删除队伍: team_id={team_id}")

    try:
        with db.get_session() as session:
            team = session.query(PlayerTeam).filter(PlayerTeam.id == team_id).first()
            if not team:
                app_logger.warning(f"[PlayerTeam] 队伍不存在: id={team_id}")
                raise HTTPException(status_code=404, detail="队伍不存在")

            team_name = team.team_name
            session.delete(team)
            
            app_logger.info(f"[PlayerTeam] 删除成功: {team_name}")
            return {"message": f"队伍 '{team_name}' 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"删除队伍失败: {str(e)}"
        db_logger.error(error_msg, exc_info=True)
        app_logger.error(f"[PlayerTeam] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    with db.get_session() as session:
        team = session.query(PlayerTeam).filter(PlayerTeam.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="队伍不存在")

        team_name = team.team_name
        session.delete(team)

        return {"message": f"队伍 '{team_name}' 已删除"}


# ============================================================================
# 前端页面
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """首页"""
    frontend_path = BASE_DIR / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(str(frontend_path))
    return """
    <html>
        <head><title>率土战报情报库</title></head>
        <body>
            <h1>率土战报情报库</h1>
            <p>前端文件未找到，请确保 frontend/index.html 存在</p>
            <p>API 文档: <a href="/docs">/docs</a></p>
        </body>
    </html>
    """
