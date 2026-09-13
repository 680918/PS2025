LEARNING_PATH = {
    "Python变量": "Python条件判断",
    "Python条件判断": "Python循环",
    "Python循环": "Python函数",
    "Python函数": "Python异常处理",
    "Python异常处理": "Python文件操作",
    "Python文件操作": "Python模块",
    "Python模块": "Python面向对象基础",
}


def get_next_topic(current_topic):
    return LEARNING_PATH.get(current_topic)
