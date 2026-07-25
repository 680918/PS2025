from controller import run_agent



user_input = input(
    "请输入问题："
)


answer = run_agent(
    user_input
)


print("\nAI Coach:")
print(answer)