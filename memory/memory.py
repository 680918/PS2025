import os


MEMORY_PATH = "memory"


MEMORY_FILES = {

    "skill":
    "skill_map.md",

    "learning":
    "Learning_Log.md",

    "profile":
    "User_Profile.md",

    "project":
    "Project_State.md",

    "experience":
    "Experience_Memory.md"

}



def get_memory_context(memory_type):

    file_name = MEMORY_FILES.get(
        memory_type
    )


    if file_name is None:

        return {
            "status": "error",
            "message":
            f"Unknown memory type: {memory_type}"
        }


    file_path = os.path.join(
        MEMORY_PATH,
        file_name
    )


    try:

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            content = f.read()


        return {

            "status":"success",

            "memory_type":
            memory_type,

            "content":
            content

        }


    except FileNotFoundError:


        return {

            "status":"error",

            "message":
            f"Memory file not found: {file_name}"

        }



def update_memory(
    file_name,
    content
):

    file_path = os.path.join(
        MEMORY_PATH,
        file_name
    )


    with open(
        file_path,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(content)


    return {

        "status":
        "success",

        "file":
        file_name

    }