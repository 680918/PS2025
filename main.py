from agent.controller import run_agent
from core.logging_config import configure_logging
from memory.runtime import create_memory_service

configure_logging()


memory_service = create_memory_service()

user_input = input("请输入问题：")


answer = run_agent(
    user_input,
    memory_service=memory_service,
)


print("\nAI Coach:")
print(answer)
