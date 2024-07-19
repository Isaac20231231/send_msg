import requests
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
    desc="watchdog监听文件变化发送消息&微信命令发送消息",
    version="2.1",
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
        self.start_watch()  # 默认启动 watchdog 监听

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
        elif content.startswith("$send_msg"):
            try:
                # 提取接收者名称列表
                receiver_start = content.find('[')
                receiver_end = content.find(']', receiver_start)
                if receiver_start != -1 and receiver_end != -1:
                    receiver_names = [name.strip() for name in content[receiver_start + 1:receiver_end].split(',')]
                    content = content[receiver_end + 1:].strip()
                else:
                    receiver_names = []

                # 提取群聊名称列表
                group_start = content.find('group[')
                if group_start != -1:
                    group_end = content.find(']', group_start)
                    if group_end != -1:
                        group_names = [name.strip() for name in content[group_start + 6:group_end].split(',')]
                        content = content[:group_start].strip()
                    else:
                        group_names = []
                else:
                    group_names = []

                # 判断是否@所有人
                if "所有人" in receiver_names or "all" in receiver_names:
                    receiver_names = ["所有人"]

                self.send_message(receiver_names, content, group_names)

                reply = Reply()
                reply.type = ReplyType.INFO
                reply.content = "消息发送成功."
                e_context['reply'] = reply
            except Exception as e:
                reply = Reply()
                reply.type = ReplyType.ERROR
                reply.content = f"消息发送失败: {str(e)}"
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
            with open(self.file_path, 'r', encoding='utf-8') as file:
                data = file.read().strip()
                if data:  # 判断文件内容是否为空
                    data_list = json.loads(data)
                    for data in data_list:
                        self.process_message(data)
                    with open(self.file_path, 'w', encoding='utf-8') as file:
                        file.write('')
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"读取文件 {self.file_path} 出错: {e}")

    def process_message(self, data):
        try:
            receiver_name = data["receiver_name"]  # 获取接收者名称
            content = data["message"]  # 获取消息内容
            group_name = data["group_name"]  # 获取群聊名称

            self.send_message(receiver_name, content, group_name)
        except Exception as e:
            logger.error(f"处理消息时发生异常: {e}")

    # 下载文件到本地的函数
    def download_file(self, url):
        """
        下载文件到本地
        :param url: 文件的URL
        """
        try:
            response = requests.get(url)
            if response.status_code == 200:
                # 提取文件名
                file_name = os.path.basename(url)
                # 创建临时文件
                with open(file_name, 'wb') as file:
                    file.write(response.content)
                return file_name
            else:
                return None
        except Exception as e:
            logger.error(f"下载文件时发生异常: {e}")
            return None

    # 定义发送消息的函数
    def send_msg(self, msg_type, content, to_user_name, at_content=None):
        """
        实际发送消息函数
        :param msg_type: 消息类型
        :param content: 消息内容
        :param to_user_name: 接收者的 UserName
        :param at_content: @的内容
        """
        if msg_type == 'text':
            if at_content:
                itchat.send(f'{at_content} {content}', to_user_name)
            else:
                itchat.send(content, to_user_name)
        elif msg_type in ['img', 'video', 'file']:
            # 如果是图片、视频或文件,先下载到本地
            local_file_path = self.download_file(content)
            if local_file_path:
                itchat.send(at_content, to_user_name)
                if msg_type == 'img':
                    itchat.send_image(local_file_path, to_user_name)
                elif msg_type == 'video':
                    itchat.send_video(local_file_path, to_user_name)
                elif msg_type == 'file':
                    itchat.send_file(local_file_path, to_user_name)
                # 发送完成后删除本地临时文件
                os.remove(local_file_path)
            else:
                raise ValueError(f"无法下载文件: {content}")

    def send_message(self, receiver_names, content, group_names=None):
        """
        发送消息
        :param receiver_names: 接收者名称列表
        :param content: 消息内容
        :param group_names: 群聊名称列表
        """
        global media_type, content_at
        try:
            # 更新 itchat 的内部缓存
            itchat.get_friends(update=True)
            itchat.get_chatrooms(update=True)

            # 判断消息类型
            if content.startswith(("http://", "https://")):
                if content.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".img")):
                    media_type = "img"
                elif content.lower().endswith((".mp4", ".avi", ".mov", ".pdf")):
                    media_type = "video"
                elif content.lower().endswith((".doc", ".docx", ".xls", "xlsx", ".zip", ".rar", "txt")):
                    media_type = "file"
                else:
                    logger.warning(f"不支持的文件类型: {content}")
            else:
                media_type = "text"

            if group_names:
                for group_name in group_names:
                    chatrooms = itchat.search_chatrooms(name=group_name)
                    if not chatrooms:
                        raise ValueError(f"没有找到对应的群聊：{group_name}")
                    chatroom = chatrooms[0]

                    if receiver_names and any(receiver_names):
                        for receiver_name in receiver_names:
                            if receiver_name == "所有人":
                                content_at = f"@所有人 "
                            else:
                                # 先去群聊找对应的成员，找不到再去好友列表找（先用微信备注名查找，找不到用微信名）
                                member_found = False
                                for member in chatroom.MemberList:
                                    if member.NickName == receiver_name or member.DisplayName == receiver_name:
                                        content_at = f"@{member.NickName} "
                                        member_found = True
                                        break
                                if not member_found:
                                    friends = itchat.search_friends(remarkName=receiver_name)
                                    if not friends:
                                        friends = itchat.search_friends(name=receiver_name)
                                    if friends:
                                        content_at = f"@{friends[0].NickName} "
                                        member_found = True
                                if not member_found:
                                    raise ValueError(f"在群聊 {group_name} 中没有找到对应的成员：{receiver_name}")
                            self.send_msg(msg_type=media_type, content=content,
                                          to_user_name=chatroom.UserName, at_content=content_at)
                            logger.info(
                                f"手动发送微信群聊消息成功, 发送群聊:{group_name}, 接收者:{receiver_name}, 消息内容：{content}")
                    else:
                        self.send_msg(media_type, content, chatroom.UserName)
                        logger.info(f"手动发送微信群聊消息成功, 发送群聊:{group_name}, 消息内容：{content}")
            else:
                if receiver_names and any(receiver_names):
                    for receiver_name in receiver_names:
                        friends = itchat.search_friends(remarkName=receiver_name)
                        if not friends:
                            friends = itchat.search_friends(name=receiver_name)
                        if friends:
                            self.send_msg(media_type, content, friends[0].UserName)
                            logger.info(f"手动发送微信消息成功, 发送人:{friends[0].NickName} 消息内容：{content}")
                        else:
                            raise ValueError(f"没有找到对应的好友：{receiver_name}")
                else:
                    raise ValueError("接收者列表为空,无法发送个人消息")
        except Exception as e:
            logger.error(f"处理消息时发生异常: {e}")
            raise e

    def get_help_text(self, **kwargs):
        return ("1.watchdog监听文件变化插件,监听data.json文件变化发送微信通知.(默认启动)\n"
                "启动监听: $start watchdog\n停止监听: $stop watchdog\n查看监听状态: $check watchdog\n\n"
                "2.微信命令发送消息: \n"
                "2.1 发送个人消息: \n$send_msg [微信备注名1,微信备注名2] 消息内容\n"
                "2.2 发送群聊消息@指定人: \n$send_msg [微信备注名1,微信备注名2] 消息内容 group[群聊名称1,群聊名称2]\n"
                "2.3 发送群聊消息@所有人: \n$send_msg [所有人] 消息内容 group[群聊名称1,群聊名称2]\n"
                "2.4 发送群聊消息不@任何人: \n$send_msg [] 消息内容 group[群聊名称1,群聊名称2]")
