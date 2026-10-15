import uuid


class AgentState:
    def __init__(
        self,
        user_message,
        memory_service=None,
    ):

        self.user_message = user_message
        self.run_id = str(uuid.uuid4())

        self.memory_service = memory_service
        self.memory_context = {}
        self.memory_context_usage = None
        self.memory_context_budget_impact = None

        self.plan = []

        self.current_step = 0

        self.tool_results = {}

        self.retry_count = 0
        self.replan_count = 0
        self.max_retries = 1
        self.max_replans = 1

        self.last_result = None
        self.status = None  # New attribute to track the status of the last operation
        self.failure_stage = (
            None  # New attribute to track the stage where the failure occurred
        )
        self.knowledge_context = []
        self.routing_trace = None

        self.learning_continuity_context = {}
        self.next_learning_task = None

        self.conversation_context = []
        self.assembled_context = None
        self.context_intelligence_trace = None
        self.context_intelligence_result = None
        self.pending_knowledge_candidate = None
        self.knowledge_suggestion = None
        self.projected_contexts = {}
        self.context_conflicts = {}
        self.context_resolutions = {}
        self.context_resolution_trace = {}
        self.context_evaluation_results = {}
        self.context_evaluation_report = None

        self.coach_context = None

        self.memory_reliability_trace = None

    def update_step(self):

        self.current_step += 1

    def add_plan(self, plan):

        self.plan = plan

    def can_retry(self):
        return self.retry_count < self.max_retries

    def can_replan(self):
        return self.replan_count < self.max_replans

    def record_retry(self):
        self.retry_count += 1

    def record_replan(self):
        self.replan_count += 1

    def add_tool_result(self, tool_name, result):

        self.tool_results[tool_name] = result

    def set_memory_context(self, memory_context):
        self.memory_context = memory_context

    def set_memory_context_usage(
        self,
        memory_context_usage,
    ):
        self.memory_context_usage = memory_context_usage

    def set_memory_context_budget_impact(
        self,
        memory_context_budget_impact,
    ):
        self.memory_context_budget_impact = memory_context_budget_impact

    def set_coach_context(
        self,
        coach_context,
    ):
        self.coach_context = coach_context

    def get_state(self):

        return {
            "run_id": self.run_id,
            "user_message": self.user_message,
            "memory_context": self.memory_context,
            "memory_context_usage": self.memory_context_usage,
            "memory_context_budget_impact": (self.memory_context_budget_impact),
            "memory_reliability_trace": (self.memory_reliability_trace),
            "plan": self.plan,
            "current_step": self.current_step,
            "tool_results": self.tool_results,
            "status": self.status,
            "failure_stage": self.failure_stage,
            "last_result": self.last_result,
            "knowledge_context": self.knowledge_context,
            "routing_trace": self.routing_trace,
            "context_conflicts": self.context_conflicts,
            "context_resolutions": self.context_resolutions,
            "context_resolution_trace": self.context_resolution_trace,
            "context_evaluation_results": self.context_evaluation_results,
            "context_evaluation_report": self.context_evaluation_report,
            "context_intelligence_trace": self.context_intelligence_trace,
            "context_intelligence_result": self.context_intelligence_result,
            "pending_knowledge_candidate": self.pending_knowledge_candidate,
            "knowledge_suggestion": self.knowledge_suggestion,
        }

    def get_tool_result(self, key):

        return self.tool_results.get(key)

    def set_knowledge_context(self, knowledge_context):
        self.knowledge_context = knowledge_context

    def set_routing_trace(self, routing_trace):
        self.routing_trace = routing_trace

    def set_learning_continuity_context(
        self,
        learning_continuity_context,
    ):
        self.learning_continuity_context = learning_continuity_context

    def set_conversation_context(
        self,
        conversation_context,
    ):
        self.conversation_context = conversation_context

    def set_assembled_context(
        self,
        assembled_context,
    ):
        self.assembled_context = assembled_context

    def set_projected_contexts(
        self,
        projected_contexts,
    ):
        self.projected_contexts = projected_contexts

    def set_context_conflicts(
        self,
        context_conflicts,
    ):
        self.context_conflicts = context_conflicts

    def set_context_resolutions(
        self,
        context_resolutions,
    ):
        self.context_resolutions = context_resolutions

    def set_context_resolution_trace(
        self,
        context_resolution_trace,
    ):
        self.context_resolution_trace = context_resolution_trace

    def set_context_evaluation_results(
        self,
        context_evaluation_results,
    ):
        self.context_evaluation_results = context_evaluation_results

    def set_context_evaluation_report(
        self,
        report,
    ):
        self.context_evaluation_report = report

    def set_context_intelligence_trace(
        self,
        trace,
    ):
        self.context_intelligence_trace = trace

    def set_context_intelligence_result(
        self,
        result,
    ):
        self.context_intelligence_result = result

    def set_pending_knowledge_candidate(
        self,
        candidate,
    ):
        self.pending_knowledge_candidate = candidate

    def set_knowledge_suggestion(
        self,
        suggestion,
    ):
        self.knowledge_suggestion = suggestion

    def set_memory_reliability_trace(
        self,
        memory_reliability_trace,
    ):
        self.memory_reliability_trace = memory_reliability_trace
