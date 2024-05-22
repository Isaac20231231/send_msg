import json
import os
import threading
import time
from common.log import logger
from lib import itchat


class Watchdog:
    """
    看门狗类，用于监控文件变化
    """

    def __init__(self, filename, interval, callback):
        self.filename = filename  # 文件名
        self.interval = interval  # 检查间隔
        self.callback = callback  # 回调函数
        self.last_checked_content = None  # 上次读取的文件内容

    def check_file(self):
        try:
            with open(self.filename, 'r') as file:
                file_content = file.read().strip()
                if not file_content:
                    time.sleep(1)  # 休眠一秒钟
                    return

                try:
                    data_list = json.loads(file_content)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误: {e}")
                    return

                if data_list:
                    for data in data_list:
                        handle_message(data)
                    with open(self.filename, 'w') as file:
                        file.write('')
                else:
                    logger.error("读取的JSON数据为空,不执行发送")
        except Exception as e:
            logger.error(f"读取JSON文件异常: {e}")
            time.sleep(1)

    def start(self):
        while True:
            self.check_file()
            time.sleep(self.interval)


def handle_message(data: dict) -> None:
    """
    处理消息内容
    :param data: 消息内容
    """
    global file_path
    try:
        receiver_name = data["receiver_name"]  # 获取接收者名称
        message = data["message"]  # 获取消息内容
        group_name = data["group_name"]  # 获取群聊名称
        curdir = os.path.dirname(__file__)
        file_path = os.path.join(curdir, "data.json")

        # 判断是否是群聊
        if group_name:
            # 判断是否有@的名字,群聊消息,reviewer_name可以为空
            if receiver_name:
                chatroom = itchat.search_chatrooms(name=group_name)[0]  # 根据群聊名称查找群聊
                if receiver_name == "所有人" or receiver_name == "all":
                    message = f"@所有人 {message}"  # 拼接消息内容
                    itchat.send(msg=f"{message}", toUserName=chatroom.UserName)  # 发送消息
                else:
                    # 发送群聊消息,并且@指定好友
                    friends = itchat.instance.storageClass.search_friends(remarkName=receiver_name)
                    if friends:
                        nickname = friends[0].NickName
                        message = f"@{nickname} {message}"  # 拼接消息内容
                        itchat.send(msg=f"{message}", toUserName=chatroom.UserName)  # 发送消息
                    else:
                        # 如果没有找到指定好友,就直接发送消息,不@任何人
                        itchat.send(msg=message, toUserName=chatroom.UserName)  # 发送消息
                logger.info(f"手动发送微信群聊消息成功, 发送群聊:{group_name} 消息内容：{message}")
            else:
                # 发送群聊消息
                chatroom = itchat.search_chatrooms(name=group_name)  # 根据群聊名称查找群聊
                if chatroom:
                    itchat.send(msg=message, toUserName=chatroom[0].UserName)  # 发送消息
                    logger.info(f"手动发送微信群聊消息成功, 发送群聊:{group_name} 消息内容：{message}")
        else:
            remarkName = itchat.instance.storageClass.search_friends(remarkName=receiver_name)  # 根据好友备注名查找好友
            if remarkName:
                itchat.send(message, toUserName=remarkName[0].UserName)  # 发送消息
                logger.info(f"手动发送微信消息成功, 发送人:{remarkName[0].NickName} 消息内容：{message}")
            else:
                logger.error(f"没有找到对应的好友：{remarkName}")
    except Exception as e:
        logger.error(f"处理消息时发生异常: {e}")
    finally:
        # 发送消息后,从JSON文件中删除已发送的消息
        with open(file_path, 'r') as file:
            data_list = json.load(file)
        data_list.remove(data)
        # 将删除后的数据写入到文件中
        with open(file_path, 'w') as file:
            json.dump(data_list, file, ensure_ascii=False)
        logger.info(f"已从message.json文件中删除已发送的消息{data}")


def send_message():
    """
    发送消息
    """
    # 创建看门狗实例，监控 data.json 文件，每隔5秒检查一次，有变化时调用 handle_message 处理
    # curdir = Path(__file__).parent.parent.parent
    curdir = os.path.dirname(__file__)
    file_path = os.path.join(curdir, "data.json")
    # file_path = '/plugins/file_writer/data.json'
    watchdog = Watchdog(file_path, 5, handle_message)
    thread = threading.Thread(target=watchdog.start)  # 创建线程,并指定线程执行的函数
    thread.daemon = True  # 设置为守护线程
    thread.start()  # 启动线程


send_message()
