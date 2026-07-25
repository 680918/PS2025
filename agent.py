from tools.tools import get_learning_history
from llm import llm_reason



def personal_growth_agent(question):


    print("用户：")
    print(question)


    # 调用LLM判断

    decision = llm_reason(
        question,
        None
    )


    print("\nLLM判断：")

    print(decision)



    if decision["need_tool"]:


        tool_name = decision["tool"]


        print("\n调用Tool:")
        print(tool_name)


        history = get_learning_history()


        print("\nTool返回:")
        print(history)


        print("\nLLM生成答案:")

        print(
            "根据你的学习历史，"
            "今天继续学习Tool Calling实践。"
        )


    else:

        print(
            "直接回答问题"
        )



personal_growth_agent(
    "我今天应该学习什么？"
)