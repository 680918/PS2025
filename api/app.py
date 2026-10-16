from fastapi import FastAPI, status, HTTPException, Form, Request

from user.service import register_user
from user.sqlite_repository import SQLiteUserRepository
from learning.journey_service import (
    create_learning_journey,
    start_learning_journey,
    complete_learning_journey,
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
from fastapi.staticfiles import StaticFiles
from api.public_pages import PUBLIC_STATIC_DIRECTORY, render_public_page
from api.email_verification_pages import (
    register_email_verification_pages,
    register_registration_verification_pages,
)
from api.registration_pages import register_registration_pages
from learning.session_service import (
    update_learning_session_feedback,
    get_or_create_learning_session,
)
from agent.controller import run_agent
from html import escape
from learning.evidence_submission_service import (
    submit_learning_evidence,
)
from learning.journey_curriculum_unit_of_work import (
    SQLiteJourneyCurriculumUnitOfWork,
)
from learning.curriculum_generation_service import (
    generate_curriculum_topics,
)
from learning.llm_curriculum_generator import (
    LLMCurriculumGenerator,
)
from learning.journey_completion_summary import (
    JourneyNotCompletedError,
    JourneyNotFoundError,
    build_journey_completion_summary_from_repositories,
)
from learning.llm_journey_completion_commentary import (
    LLMJourneyCompletionCommentary,
)
from learning.journey_completion_report_service import (
    get_or_create_journey_completion_report,
)
from learning.sqlite_journey_completion_report_repository import (
    SQLiteJourneyCompletionReportRepository,
)
from memory.runtime import (
    create_user_memory_service,
)
from memory.memory_reliability_run_record_runtime import (
    create_user_memory_reliability_run_record_store,
)
from memory.journey_memory_consolidation_service import (
    consolidate_journey_completion_summary,
)
from coach.context_builder import build_coach_context
from api.markdown_renderer import render_safe_markdown
from learning.llm_learning_feedback_extractor import (
    LLMLearningFeedbackExtractor,
)
from conversation.message import ConversationMessage
from conversation.sqlite_repository import (
    SQLiteConversationRepository,
)
from conversation.context import build_conversation_context


_DEFAULT_CURRICULUM_GENERATOR = object()
_DEFAULT_COMPLETION_COMMENTARY_GENERATOR = object()
_DEFAULT_LEARNING_FEEDBACK_EXTRACTOR = object()


def create_app(
    database_dir,
    curriculum_generator=_DEFAULT_CURRICULUM_GENERATOR,
    completion_commentary_generator=_DEFAULT_COMPLETION_COMMENTARY_GENERATOR,
    learning_feedback_extractor=_DEFAULT_LEARNING_FEEDBACK_EXTRACTOR,
    *,
    registration_mail=None,
):
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=PUBLIC_STATIC_DIRECTORY), name="static")

    if curriculum_generator is _DEFAULT_CURRICULUM_GENERATOR:
        curriculum_generator = LLMCurriculumGenerator()

    if completion_commentary_generator is _DEFAULT_COMPLETION_COMMENTARY_GENERATOR:
        completion_commentary_generator = LLMJourneyCompletionCommentary()

    if learning_feedback_extractor is _DEFAULT_LEARNING_FEEDBACK_EXTRACTOR:
        learning_feedback_extractor = LLMLearningFeedbackExtractor()

    user_repository = SQLiteUserRepository(database_dir / "users.db")
    register_email_verification_pages(app, user_repository)
    register_registration_verification_pages(app, user_repository)
    register_registration_pages(app, user_repository, mail_config=registration_mail)

    journey_repository = SQLiteLearningJourneyRepository(database_dir / "journeys.db")

    session_repository = SQLiteLearningSessionRepository(database_dir / "sessions.db")

    conversation_repository = SQLiteConversationRepository(
        database_dir / "conversations.db"
    )

    evidence_repository = SQLiteLearningEvidenceRepository(database_dir / "sessions.db")

    curriculum_repository = SQLiteLearningCurriculumRepository(
        database_dir / "curriculums.db"
    )

    journey_curriculum_unit_of_work = SQLiteJourneyCurriculumUnitOfWork(
        database_path=database_dir / "journeys.db",
        journey_repository=journey_repository,
        curriculum_repository=curriculum_repository,
    )

    completion_report_repository = SQLiteJourneyCompletionReportRepository(
        database_dir / "completion_reports.db"
    )

    def run_web_coach_turn(
        journey,
        user_id,
        user_message,
    ):
        continuity = build_learning_continuity_context(
            journey_id=journey.journey_id,
            repository=session_repository,
            user_id=user_id,
        )

        memory_service = create_user_memory_service(
            database_dir=database_dir,
            user_id=user_id,
        )

        memory_reliability_run_record_store = (
            create_user_memory_reliability_run_record_store(
                database_dir=database_dir,
                user_id=user_id,
            )
        )

        coach_context = build_coach_context(
            user_id=user_id,
            user_message=user_message,
            user_repository=user_repository,
            journey_repository=journey_repository,
            memory_service=None,
            journey_id=journey.journey_id,
        )

        conversation_context = build_conversation_context(
            repository=conversation_repository,
            journey_id=journey.journey_id,
            user_id=user_id,
            recent_limit=10,
        )

        agent_result = run_agent(
            user_message=user_message,
            memory_service=memory_service,
            memory_reliability_run_record_store=(memory_reliability_run_record_store),
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
            return_state=True,
            coach_context=coach_context,
            conversation_context=conversation_context,
        )

        if isinstance(agent_result, tuple):
            agent_state, coach_response = agent_result
        else:
            agent_state = None
            coach_response = agent_result

        return (
            continuity,
            agent_state,
            coach_response,
        )

    def render_conversation_history(
        conversation_history,
    ):
        conversation_history_html = ""

        for history_message in conversation_history:
            role = history_message["role"]
            content = history_message["content"]

            if role == "assistant":
                rendered_content = render_safe_markdown(
                    content,
                )
                speaker = "Coach"
            else:
                rendered_content = escape(str(content))
                speaker = "你"

            conversation_history_html += f"""
            <div>
                <strong>{speaker}：</strong>
                <div>
                    {rendered_content}
                </div>
            </div>
            """

        return conversation_history_html

    def render_journey_completion_page(
        journey,
        user_id,
    ):
        summary = build_journey_completion_summary_from_repositories(
            journey_repository=journey_repository,
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id=journey.journey_id,
            user_id=user_id,
        )

        memory_service = create_user_memory_service(
            database_dir=database_dir,
            user_id=user_id,
        )

        consolidate_journey_completion_summary(
            summary=summary,
            memory_service=memory_service,
        )

        commentary_html = ""

        if completion_commentary_generator is not None:
            try:
                report = get_or_create_journey_completion_report(
                    repository=completion_report_repository,
                    summary=summary,
                    user_id=user_id,
                    commentary_generator=completion_commentary_generator,
                )

                # 页面展示的 Summary 和 Commentary
                # 都使用已经持久化的同一份 Report。
                summary = report.summary

                safe_commentary = escape(str(report.commentary))

                commentary_html = f"""
                <h2>毕业评语</h2>
                <p>{safe_commentary}</p>
                """

            except RuntimeError:
                commentary_html = """
                <h2>毕业评语</h2>
                <p>毕业评语暂时不可用。</p>
                """

        safe_domain = escape(str(summary["domain"]))
        safe_goal = escape(str(summary["goal"]))

        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>学习旅程已完成</title>
        </head>
        <body>
            <h1>学习旅程已完成</h1>
            <p>恭喜你完成了当前课程计划。</p>

            <h2>学习总结</h2>

            <p>学习领域：{safe_domain}</p>
            <p>学习目标：{safe_goal}</p>
            <p>已完成学习次数：{summary["completed_sessions"]}</p>
            <p>最初理解度：{summary["first_understanding"]}</p>
            <p>最终理解度：{summary["latest_understanding"]}</p>
            <p>理解度变化：{summary["understanding_change"]}</p>
            <p>学习趋势：{summary["trend"]}</p>
            <p>学习证据数量：{summary["evidence_count"]}</p>
            <p>已完成任务：{summary["completed_tasks"]}</p>

            {commentary_html}
        </body>
        </html>
        """

    @app.get(
        "/",
        response_class=HTMLResponse,
    )
    def home():
        return render_public_page("home")

    @app.get("/web/login", response_class=HTMLResponse)
    def web_login_page():
        return render_public_page("login")

    @app.post(
        "/web/auth/login",
        response_class=HTMLResponse,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        include_in_schema=False,
    )
    def web_login_unavailable():
        # Do not read credentials or imply a successful login before auth exists.
        return render_public_page("login")

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

            <form method="post" action="/web/curriculums/preview">
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
                    生成课程计划
                </button>
            </form>
        </body>
        </html>
        """

    @app.post("/curriculums/preview")
    def preview_curriculum(payload: dict):
        if curriculum_generator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="curriculum generator is not configured",
            )

        try:
            topics = generate_curriculum_topics(
                domain=payload["domain"],
                goal=payload["goal"],
                generator=curriculum_generator,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="curriculum generation is unavailable",
            ) from error

        return {
            "curriculum_topics": topics,
        }

    @app.post(
        "/web/curriculums/preview",
        response_class=HTMLResponse,
    )
    def web_preview_curriculum(
        user_id: str = Form(...),
        domain: str = Form(...),
        goal: str = Form(...),
    ):
        if curriculum_generator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="curriculum generator is not configured",
            )

        try:
            topics = generate_curriculum_topics(
                domain=domain,
                goal=goal,
                generator=curriculum_generator,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="curriculum generation is unavailable",
            ) from error

        topic_items = "\n".join(f"<li>{escape(topic)}</li>" for topic in topics)

        topic_inputs = "\n".join(
            (
                '<input type="hidden" '
                'name="curriculum_topics" '
                f'value="{escape(topic, quote=True)}">'
            )
            for topic in topics
        )

        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>课程计划预览</title>
        </head>
        <body>
            <h1>课程计划预览</h1>

            <p>学习领域：{escape(domain)}</p>
            <p>学习目标：{escape(goal)}</p>

            <ol>
                {topic_items}
            </ol>

            <form method="post" action="/web/journeys">
                <input
                    type="hidden"
                    name="user_id"
                    value="{escape(user_id, quote=True)}"
                >

                <input
                    type="hidden"
                    name="domain"
                    value="{escape(domain, quote=True)}"
                >

                <input
                    type="hidden"
                    name="goal"
                    value="{escape(goal, quote=True)}"
                >

                {topic_inputs}

                <button type="submit">
                    确认创建学习旅程
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
        curriculum_topics: list[str] | None = Form(None),
    ):
        journey = create_learning_journey(
            repository=journey_repository,
            user_repository=user_repository,
            user_id=user_id,
            domain=domain,
            goal=goal,
            curriculum_topics=curriculum_topics,
            curriculum_repository=curriculum_repository,
            unit_of_work=journey_curriculum_unit_of_work,
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
                curriculum_repository=curriculum_repository,
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
        "/journeys/{journey_id}/completion-summary",
        status_code=status.HTTP_200_OK,
    )
    def get_journey_completion_summary(
        journey_id: str,
        user_id: str,
    ):
        try:
            return build_journey_completion_summary_from_repositories(
                journey_repository=journey_repository,
                session_repository=session_repository,
                evidence_repository=evidence_repository,
                journey_id=journey_id,
                user_id=user_id,
            )
        except JourneyNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error
        except JourneyNotCompletedError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

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

        if journey.status == "completed":
            return render_journey_completion_page(
                journey=journey,
                user_id=user_id,
            )

        user_message = "请根据我的学习目标和当前学习连续性状态，安排本次学习任务。"

        continuity, agent_state, coach_task = run_web_coach_turn(
            journey=journey,
            user_id=user_id,
            user_message=user_message,
        )

        if continuity.get("has_current_session") is True:
            session_topic = continuity.get(
                "current_topic",
                journey.domain,
            )
        else:
            session_topic = continuity.get(
                "topic",
                journey.domain,
            )

        planning_decision = None

        if agent_state is not None and agent_state.next_learning_task is not None:
            planning_decision = agent_state.next_learning_task["context"].get(
                "planning_decision"
            )

            if (
                planning_decision is not None
                and planning_decision.get("action") == "advance"
                and planning_decision.get("next_topic") is not None
            ):
                session_topic = planning_decision["next_topic"]

        if (
            planning_decision is not None
            and planning_decision.get("action") == "complete"
        ):
            complete_learning_journey(
                repository=journey_repository,
                journey=journey,
            )

            return render_journey_completion_page(
                journey=journey,
                user_id=user_id,
            )

        get_or_create_learning_session(
            repository=session_repository,
            journey_id=journey.journey_id,
            user_id=user_id,
            topic=session_topic,
        )
        rendered_coach_task = render_safe_markdown(
            coach_task,
        )

        if continuity.get("has_current_session") is True:
            continuity_topic_label = "当前主题"
            continuity_topic = continuity.get(
                "current_topic",
                "暂无",
            )
        else:
            continuity_topic_label = "上次主题"
            continuity_topic = continuity.get(
                "topic",
                "暂无",
            )

        conversation_history = build_conversation_context(
            repository=conversation_repository,
            journey_id=journey.journey_id,
            user_id=user_id,
            recent_limit=10,
        )

        conversation_history_html = render_conversation_history(
            conversation_history,
        )

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

            <div>
                {rendered_coach_task}
            </div>

            <p>学习领域：{journey.domain}</p>
            <p>学习目标：{journey.goal}</p>

            <p>
                {continuity_topic_label}：
                {continuity_topic}
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
            <h2>对话</h2>

            <div>
                {conversation_history_html}
            </div>

            <h2>继续对话</h2>

            <form
                method="post"
                action="/web/journeys/{journey.journey_id}/message"
            >
                <input
                    type="hidden"
                    name="user_id"
                    value="{escape(user_id, quote=True)}"
                >

                <label for="message">
                    告诉我你的进展、问题，或者你想继续学习的方向：
                </label>

                <br>

                <textarea
                    id="message"
                    name="message"
                    rows="6"
                    required
                ></textarea>

                <br>

                <button type="submit">
                    发送
                </button>
            </form>
        </body>
        </html>
        """

    @app.post(
        "/web/journeys/{journey_id}/message",
        response_class=HTMLResponse,
    )
    def web_send_journey_message(
        journey_id: str,
        user_id: str = Form(...),
        message: str = Form(...),
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

        _, _, coach_response = run_web_coach_turn(
            journey=journey,
            user_id=user_id,
            user_message=message,
        )

        conversation_repository.save(
            ConversationMessage(
                journey_id=journey.journey_id,
                user_id=user_id,
                role="user",
                content=message,
            )
        )

        conversation_repository.save(
            ConversationMessage(
                journey_id=journey.journey_id,
                user_id=user_id,
                role="assistant",
                content=coach_response,
            )
        )

        conversation_history = build_conversation_context(
            repository=conversation_repository,
            journey_id=journey.journey_id,
            user_id=user_id,
            recent_limit=10,
        )

        conversation_history_html = render_conversation_history(
            conversation_history,
        )

        feedback_confirmation = ""
        feedback_proposal = None

        if learning_feedback_extractor is not None:
            try:
                feedback_proposal = learning_feedback_extractor.extract(
                    message,
                )
            except RuntimeError:
                feedback_proposal = None

        if feedback_proposal is not None:
            understanding_score = feedback_proposal["understanding_score"]
            difficulty = feedback_proposal["difficulty"]
            next_step = feedback_proposal["next_step"]

            feedback_confirmation = f"""
                <h2>确认本次学习反馈</h2>

                <p>
                    理解程度：
                    {escape(str(understanding_score))}
                </p>

                <p>
                    当前难点：
                    {escape(str(difficulty))}
                </p>

                <p>
                    下一步：
                    {escape(str(next_step))}
                </p>

                <form
                    method="post"
                    action="/web/journeys/{journey.journey_id}/feedback"
                >
                    <input
                        type="hidden"
                        name="user_id"
                        value="{escape(user_id, quote=True)}"
                    >

                    <input
                        type="hidden"
                        name="understanding_score"
                        value="{escape(str(understanding_score), quote=True)}"
                    >

                    <input
                        type="hidden"
                        name="difficulty"
                        value="{escape(str(difficulty), quote=True)}"
                    >

                    <input
                        type="hidden"
                        name="next_step"
                        value="{escape(str(next_step), quote=True)}"
                    >

                    <button type="submit">
                        确认并保存
                    </button>
                </form>
                """

        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>继续学习</title>
        </head>
        <body>
            <h1>继续学习</h1>

            <h2>对话</h2>

            <div>
                {conversation_history_html}
            </div>

            {feedback_confirmation}

            <h2>继续对话</h2>

            <form
                method="post"
                action="/web/journeys/{journey.journey_id}/message"
            >
                <input
                    type="hidden"
                    name="user_id"
                    value="{escape(user_id, quote=True)}"
                >

                <label for="message">
                    告诉我你的进展、问题，或者你想继续学习的方向：
                </label>

                <br>

                <textarea
                    id="message"
                    name="message"
                    rows="6"
                    required
                ></textarea>

                <br>

                <button type="submit">
                    发送
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
                unit_of_work=journey_curriculum_unit_of_work,
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
                curriculum_repository=curriculum_repository,
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
