from plugins import *
from flask import Flask, request, jsonify
import json
from common.log import logger
from plugins import Plugin, register
import threading

app = Flask(__name__)


def validate_data(data_list):
    # 检查data_list是否为列表类型
    if not isinstance(data_list, list):
        raise ValueError('data_list必须为列表类型')
    # 检查data_list是否为空
    if not data_list:
        raise ValueError('data_list不能为空')
    # 遍历data_list,检查每个元素是否包含必要的字段
    for data in data_list:
        if not isinstance(data, dict):
            raise ValueError('data_list的每个元素必须为字典类型')
        if 'message' not in data:
            raise ValueError('每个消息必须包含message')


@register(
    name="file_writer",
    desire_priority=120,
    hidden=False,
    desc="写入文件api",
    version="1.0",
    author="Isaac",
)
class FileWriter(Plugin):
    def __init__(self):
        super().__init__()

    @staticmethod
    @app.route('/send_message', methods=['POST'])
    def send_message():
        try:
            # 获取请求中的数据
            data_list = request.json.get('data_list', [])  # 获取消息列表
            try:
                validate_data(data_list)
            except ValueError as e:
                return jsonify({'status': 'error', 'message': str(e)}), 400

            curdir = os.path.dirname(__file__)
            # 配置文件路径
            config_path = os.path.join(curdir, "data.json")
            # 将数据写入到message.json文件中
            with open(config_path, 'w') as file:
                json.dump(data_list, file, ensure_ascii=False)
            logger.info(f"写入成功,写入内容{data_list}")

            return jsonify({'status': 'success', 'message': '发送成功'}), 200
        except Exception as e:
            logger.error(f"处理请求时发生错误: {str(e)}")
            return jsonify({'status': 'error', 'message': '服务器内部错误'}), 500

    def get_help_text(self, **kwargs):
        return "写入文件api插件,用来手动发送微信通知"

    # 启动Flask服务器的函数
    @staticmethod
    def run_flask_app():
        app.run(host='0.0.0.0', port=5688, debug=False)

    # 在单独的线程中启动Flask服务器
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
