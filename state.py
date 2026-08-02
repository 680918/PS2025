class AgentState:


    def __init__(self,user_message):

        self.user_message = user_message

        self.tool_call = None

        self.tool_result = None

        self.final_answer = None