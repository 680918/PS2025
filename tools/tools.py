from memory.memory import get_memory_context

def get_memory():

    return get_memory_context(
        "skill"
    )


TOOLS = {


    "get_memory_context":
    get_memory


}



def execute_tool(
    tool_name,
    arguments=None
):


    tool = TOOLS.get(
        tool_name
    )


    if tool is None:

        return {

            "status":
            "error",

            "message":
            f"Unknown tool:{tool_name}"

        }


    try:

        if arguments:

            return tool(
                **arguments
            )

        else:

            return tool()


    except Exception as e:


        return {

            "status":
            "error",

            "message":
            str(e)

        }