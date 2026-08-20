class AgentState:

    
    def __init__(self,user_message):

        self.user_message=user_message

        self.plan=[]

        self.current_step=0

        self.tool_results={}

        self.retry_count=0
        self.replan_count=0
        self.max_retries = 1
        self.max_replans = 1

        self.last_result = None
           


    def update_step(self):

        self.current_step += 1



    def add_plan(self,plan):

        self.plan=plan


    def can_retry(self):
        return self.retry_count < self.max_retries

    def can_replan(self):
        return self.replan_count < self.max_replans

    def record_retry(self):
        self.retry_count += 1

    def record_replan(self):
        self.replan_count += 1   

    def add_tool_result(
        self,
        tool_name,
        result
    ):

        self.tool_results[tool_name]=result



    def get_state(self):

        return {

        "user_message":
        self.user_message,

        "plan":
        self.plan,

        "current_step":
        self.current_step,

        "tool_results":
        self.tool_results

        }    

    def get_tool_result(self, key):

        return self.tool_results.get(
            key
        )