from fastapi import FastAPI, status, HTTPException, Form, Request

from user.service import register_user
from user.sqlite_repository import SQLiteUserRepository
from learning.journey_service import (
    create_learning_journey,
    start_learning_journey,
)
from learning.sqlite_journey_repository import (
    SQLiteLearningJourneyRepository,
)
from learning.sqlite_session_repository import (
    SQLiteLearningSessionRepository,
)
from learning.sqlite_evidence_repository import (
    SQLiteLearningEvidenceRepository,
)
from learning.sqlite_curriculum_repository import (
    SQLiteLearningCurriculumRepository,
)
from learning.continuity import (
    build_learning_continuity_context,
)
from fastapi.responses import HTMLResponse
from learning.session_service import (
    update_learning_session_feedback,
    get_or_create_learning_session,
)
from agent.controller import run_agent
from html import escape
from learning.evidence_submission_service import (
    submit_learning_evidence,
)


def create_app(
    database_dir,
):
    app = FastAPI()

    user_repository = SQLiteUserRepository(database_dir / "users.db")

    journey_repository = SQLiteLearningJourneyRepository(database_dir / "journeys.db")

    session_repository = SQLiteLearningSessionRepository(database_dir / "sessions.db")

    evidence_repository = SQLiteLearningEvidenceRepository(database_dir / "sessions.db")

    curriculum_repository = SQLiteLearningCurriculumRepository(
        database_dir / "curriculums.db"
    )

    @app.get(
        "/",
        response_class=HTMLResponse,
    )
    def home():
        return """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>AI Learning Coach</title>
        </head>
        <body>
            <h1>AI Learning Coach</h1>
            <p>你的长期学习伙伴</p>

            <h2>注册</h2>

            <form method="post" action="/web/register">
                <label>
                    姓名：
                    <input
                        type="text"
                        name="name"
                        required
                    >
                </label>

                <br>

                <label>
                    邮箱：
                    <input
                        type="email"
                        name="email"
                        required
                    >
                </label>

                <br>

                <button type="submit">
                    注册
                </button>
            </form>
        </body>
        </html>
        """

    @app.post(
        "/web/register",
        response_class=HTMLResponse,
    )
    def web_register(
        name: str = Form(...),
        email: str = Form(...),
    ):
        user = register_user(
            repository=user_repository,
            name=name,
            email=email,
        )

        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>注册成功</title>
        </head>
        <body>
            <h1>注册成功</h1>

            <p>姓名：{user.name}</p>
            <p>邮箱：{user.email}</p>

            <h2>创建学习目标</h2>

            <form method="post" action="/web/journeys">
                <input
                    type="hidden"
                    name="user_id"
                    value="{user.user_id}"
                >

                <label>
                    学习领域：
                    <input
                        type="text"
                        name="domain"
                        required
                    >
                </label>

                <br>

                <label>
                    学习目标：
                    <input
                        type="text"
                        name="goal"
                        required
                    >
                </label>

                <br>

                <button type="submit">
                    创建学习目标
                </button>
            </form>
        </body>
        </html>
        """

    @app.post(
        "/web/journeys",
        response_class=HTMLResponse,
    )
    def web_create_journey(
        user_id: str = Form(...),
        domain: str = Form(...),
        goal: str = Form(...),
    ):
        journey = create_learning_journey(
            repository=journey_repository,
            user_repository=user_repository,
            user_id=user_id,
            domain=domain,
            goal=goal,
        )

        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>学习目标创建成功</title>
        </head>
        <body>
            <h1>学习目标创建成功</h1>

            <p>学习领域：{journey.domain}</p>
            <p>学习目标：{journey.goal}</p>
            <p>状态：{journey.status}</p>

            <form
                method="post"
                action="/web/journeys/{journey.journey_id}/start"
            >
                <button type="submit">
                    开始学习
                </button>
            </form>
        </body>
        </html>
        """

    @app.post(
        "/journeys/{journey_id}/evidence",
        status_code=status.HTTP_201_CREATED,
    )
    def submit_evidence(
        journey_id: str,
        payload: dict,
    ):
        required_fields = (
            "user_id",
            "session_id",
            "task",
            "result",
            "assessment",
        )

        for field in required_fields:
            if field not in payload:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field} is required",
                )

        try:
            evidence = submit_learning_evidence(
                session_repository=session_repository,
                evidence_repository=evidence_repository,
                journey_id=journey_id,
                user_id=payload["user_id"],
                session_id=payload["session_id"],
                task=payload["task"],
                result=payload["result"],
                assessment=payload["assessment"],
                tests_passed=payload.get("tests_passed"),
                tests_total=payload.get("tests_total"),
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error

        return {
            "evidence_id": evidence.evidence_id,
            "session_id": evidence.session_id,
            "task": evidence.task,
            "result": evidence.result,
            "assessment": evidence.assessment,
            "tests_passed": evidence.tests_passed,
            "tests_total": evidence.tests_total,
        }

    @app.post(
        "/web/journeys/{journey_id}/start",
        response_class=HTMLResponse,
    )
    def web_start_journey(
        journey_id: str,
    ):
        journey = journey_repository.get_by_id(journey_id)

        if journey is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="journey not found",
            )

        try:
            session = start_learning_journey(
                repository=journey_repository,
                journey=journey,
                session_repository=session_repository,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>学习已开始</title>
        </head>
        <body>
            <h1>学习已开始</h1>

            <p>学习领域：{journey.domain}</p>
            <p>学习目标：{journey.goal}</p>
            <p>状态：{journey.status}</p>
            <p>当前主题：{session.topic}</p>
            <a href="/web/journeys/{journey.journey_id}/continue?user_id={journey.user_id}">
                继续学习
            </a>
        </body>
        </html>
        """

    @app.get(
        "/web/journeys/{journey_id}/continue",
        response_class=HTMLResponse,
    )
    def web_continue_journey(
        journey_id: str,
        user_id: str,
    ):
        journey = journey_repository.get_by_id_for_user(
            journey_id=journey_id,
            user_id=user_id,
        )

        if journey is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="journey not found",
            )

        continuity = build_learning_continuity_context(
            journey_id=journey.journey_id,
            repository=session_repository,
            user_id=user_id,
        )

        coach_task = run_agent(
            user_message="请根据我的学习目标和上一次学习反馈，安排今天的学习任务。",
            learning_journey={
                "domain": journey.domain,
                "goal": journey.goal,
            },
            learning_continuity_context=continuity,
            journey_id=journey.journey_id,
            user_id=user_id,
            learning_session_repository=session_repository,
            learning_evidence_repository=evidence_repository,
            learning_curriculum_repository=curriculum_repository,
        )

        get_or_create_learning_session(
            repository=session_repository,
            journey_id=journey.journey_id,
            user_id=user_id,
            topic=journey.domain,
        )
        safe_coach_task = escape(str(coach_task))

        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>继续学习</title>
        </head>
        <body>
            <h1>继续学习</h1>
            <h2>今天学习什么</h2>

            <p>{safe_coach_task}</p>

            <p>学习领域：{journey.domain}</p>
            <p>学习目标：{journey.goal}</p>

            <p>
                上次主题：
                {continuity.get("topic", "暂无")}
            </p>

            <p>
                理解程度：
                {continuity.get("understanding_score", "暂无")}
            </p>

            <p>
                难点：
                {continuity.get("difficulty", "暂无")}
            </p>

            <p>
                下一步：
                {continuity.get("next_step", "暂无")}
            </p>

            <h2>提交练习证据</h2>

            <form
                method="post"
                action="/web/journeys/{journey.journey_id}/evidence"
            >
                <input
                    type="hidden"
                    name="user_id"
                    value="{user_id}"
                >

                <label>
                    练习任务：
                    <input
                        type="text"
                        name="task"
                        required
                    >
                </label>

                <br>

                <label>
                    练习结果：
                    <input
                        type="text"
                        name="result"
                        required
                    >
                </label>

                <br>

                <label>
                    自我评估：
                    <input
                        type="text"
                        name="assessment"
                        required
                    >
                </label>

                <br>

                <label>
                    通过测试数：
                    <input
                        type="number"
                        name="tests_passed"
                        min="0"
                    >
                </label>

                <br>

                <label>
                    测试总数：
                    <input
                        type="number"
                        name="tests_total"
                        min="1"
                    >
                </label>

                <br>

                <button type="submit">
                    提交练习证据
                </button>
            </form>

            <h2>提交学习反馈</h2>

            <form
                method="post"
                action="/web/journeys/{journey.journey_id}/feedback"
            >
                <input
                    type="hidden"
                    name="user_id"
                    value="{user_id}"
                >

                <label>
                    理解程度：
                    <input
                        type="number"
                        name="understanding_score"
                        min="0"
                        max="100"
                        required
                    >
                </label>

                <br>

                <label>
                    当前难点：
                    <input
                        type="text"
                        name="difficulty"
                        required
                    >
                </label>

                <br>

                <label>
                    下一步：
                    <input
                        type="text"
                        name="next_step"
                        required
                    >
                </label>

                <br>

                <button type="submit">
                    提交学习反馈
                </button>
            </form>
        </body>
        </html>
        """

    @app.post(
        "/web/journeys/{journey_id}/evidence",
        response_class=HTMLResponse,
    )
    async def web_submit_evidence(
        journey_id: str,
        request: Request,
    ):
        form = await request.form()

        try:
            submit_learning_evidence(
                evidence_repository=evidence_repository,
                session_repository=session_repository,
                journey_id=journey_id,
                user_id=form["user_id"],
                session_id=form["session_id"],
                task=form["task"],
                result=form["result"],
                assessment=form["assessment"],
                tests_passed=(
                    int(form["tests_passed"]) if form.get("tests_passed") else None
                ),
                tests_total=(
                    int(form["tests_total"]) if form.get("tests_total") else None
                ),
            )

        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error
        return """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <body>
            <h1>练习证据已保存</h1>
            <a href="javascript:history.back()">
                返回学习页面
            </a>
        </body>
        </html>
        """

    @app.post(
        "/web/journeys/{journey_id}/feedback",
        response_class=HTMLResponse,
    )
    def web_submit_feedback(
        journey_id: str,
        user_id: str = Form(...),
        understanding_score: int = Form(...),
        difficulty: str = Form(...),
        next_step: str = Form(...),
    ):
        journey = journey_repository.get_by_id_for_user(
            journey_id=journey_id,
            user_id=user_id,
        )

        if journey is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="journey not found",
            )

        session = session_repository.get_latest_by_journey_for_user(
            journey_id=journey_id,
            user_id=user_id,
        )

        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="learning session not found",
            )

        try:
            updated_session = update_learning_session_feedback(
                repository=session_repository,
                session=session,
                understanding_score=understanding_score,
                difficulty=difficulty,
                next_step=next_step,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error

        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>学习反馈已保存</title>
        </head>
        <body>
            <h1>学习反馈已保存</h1>

            <p>
                理解程度：
                {updated_session.understanding_score}
            </p>

            <p>
                当前难点：
                {updated_session.difficulty}
            </p>

            <p>
                下一步：
                {updated_session.next_step}
            </p>

            <a
                href="/web/journeys/{journey_id}/continue?user_id={user_id}"
            >
                继续学习
            </a>
        </body>
        </html>
        """

    @app.post(
        "/users",
        status_code=status.HTTP_201_CREATED,
    )
    def create_user(payload: dict):
        user = register_user(
            repository=user_repository,
            name=payload["name"],
            email=payload["email"],
        )

        return {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
        }

    @app.post(
        "/journeys",
        status_code=status.HTTP_201_CREATED,
    )
    def create_journey(payload: dict):
        try:
            journey = create_learning_journey(
                repository=journey_repository,
                user_repository=user_repository,
                user_id=payload["user_id"],
                domain=payload["domain"],
                goal=payload["goal"],
                curriculum_topics=payload.get("curriculum_topics"),
                curriculum_repository=curriculum_repository,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error
        return {
            "journey_id": journey.journey_id,
            "user_id": journey.user_id,
            "domain": journey.domain,
            "goal": journey.goal,
            "status": journey.status,
        }

    @app.post(
        "/journeys/{journey_id}/start",
        status_code=status.HTTP_200_OK,
    )
    def start_journey(journey_id: str):
        journey = journey_repository.get_by_id(journey_id)

        if journey is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="journey not found",
            )

        try:
            session = start_learning_journey(
                repository=journey_repository,
                journey=journey,
                session_repository=session_repository,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

        return {
            "journey_id": journey.journey_id,
            "status": journey.status,
            "session_id": session.session_id,
        }

    @app.get(
        "/journeys/{journey_id}/continue",
        status_code=status.HTTP_200_OK,
    )
    def continue_journey(
        journey_id: str,
        user_id: str,
    ):
        journey = journey_repository.get_by_id_for_user(
            journey_id=journey_id,
            user_id=user_id,
        )

        if journey is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="journey not found",
            )

        continuity = build_learning_continuity_context(
            journey_id=journey_id,
            user_id=user_id,
            repository=session_repository,
        )

        return continuity

    return app
