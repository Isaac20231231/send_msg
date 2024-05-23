from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from plugins import *
import plugins
from lib import itchat


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        if event.src_path.endswith('data.json'):
            self.callback()


@plugins.register(
    name="file_watcher",
    desire_priority=180,
    hidden=True,
    desc="watchdog监听文件变化插件",
    version="0.1",
    author="Isaac"
)
class FileWatcherPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        curdir = os.path.dirname(__file__)
        self.file_path = os.path.join(curdir, "data.json")
        self.observer = Observer()
        self.event_handler = FileChangeHandler(self.handle_message)

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
            return
        content = e_context['context'].content
        if content == "$start watchdog":
            self.start_watch()
            e_context.action = EventAction.BREAK_PASS
            reply = Reply()
            reply.type = ReplyType.INFO
            reply.content = "watchdog started."
            e_context['reply'] = reply
            logger.info("watchdog监听已启动,监听data.json文件变化发送微信通知.")
            self.handle_message()  # 处理文件中的现有数据
        elif content == "$stop watchdog":
            self.stop_watch()
            e_context.action = EventAction.BREAK_PASS
            reply = Reply()
            reply.type = ReplyType.INFO
            reply.content = "watchdog stopped."
            e_context['reply'] = reply
            logger.info("watchdog监听已停止.写入文件data.json不再发送微信通知.")
        elif content == "$check watchdog":
            if self.observer.is_alive():
                reply = Reply()
                reply.type = ReplyType.INFO
                reply.content = "watchdog 正在运行,如需停止:关闭命令 $stop watchdog."
                e_context['reply'] = reply
            else:
                reply = Reply()
                reply.type = ReplyType.INFO
                reply.content = "watchdog 没在运行,如需启动:启动命令 $start watchdog."
                e_context['reply'] = reply
            e_context.action = EventAction.BREAK_PASS

    def start_watch(self):
        if not self.observer.is_alive():
            self.observer = Observer()
            self.observer.schedule(self.event_handler, path=os.path.dirname(self.file_path), recursive=False)
            self.observer.start()
            logger.info("watchdog started.")
        else:
            logger.info("watchdog is already running.")

    def stop_watch(self):
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.info("watchdog stopped.")
        else:
            logger.info("watchdog is not running.")

    def handle_message(self):
        try:
            with open(self.file_path, 'r') as file:
                data_list = json.load(file)
                for data in data_list:
                    self.process_message(data)
            with open(self.file_path, 'w') as file:
                file.write('')
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"读取文件 {self.file_path} 出错: {e}")

    def process_message(self, data):
        try:
            receiver_name = data["receiver_name"]  # 获取接收者名称
            content = data["message"]  # 获取消息内容
            group_name = data["group_name"]  # 获取群聊名称

            # 判断是否是群聊
            if group_name:
                chatroom = itchat.search_chatrooms(name=group_name)[0]  # 根据群聊名称查找群聊
                if receiver_name:
                    if receiver_name == "所有人" or receiver_name == "all":
                        content = f"@所有人 {content}"  # 拼接消息内容
                    else:
                        # 发送群聊消息,并且@指定好友
                        friends = itchat.search_friends(remarkName=receiver_name)
                        if friends:
                            nickname = friends[0].NickName
                            content = f"@{nickname} {content}"  # 拼接消息内容
                itchat.send(content, chatroom.UserName)
                logger.info(f"手动发送微信群聊消息成功, 发送群聊:{group_name} 消息内容：{content}")
            else:
                remarkName = itchat.search_friends(remarkName=receiver_name)  # 根据好友备注名查找好友
                if remarkName:
                    itchat.send(content, remarkName[0].UserName)
                    logger.info(f"手动发送微信消息成功, 发送人:{remarkName[0].NickName} 消息内容：{content}")
                else:
                    logger.error(f"没有找到对应的好友：{remarkName}")
        except Exception as e:
            logger.error(f"处理消息时发生异常: {e}")

    def get_help_text(self, **kwargs):
        return "watchdog监听文件变化插件,监听data.json文件变化发送微信通知."
