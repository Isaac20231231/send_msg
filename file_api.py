from flask import Flask, request, jsonify
import json
from common.log import logger
import threading
import os

app = Flask(__name__)


def validate_data(data_list):
    if not isinstance(data_list, list):
        raise ValueError('data_list必须为列表类型')
    if not data_list:
        raise ValueError('data_list不能为空')
    for data in data_list:
        if not isinstance(data, dict):
            raise ValueError('data_list的每个元素必须为字典类型')
        if 'message' not in data:
            raise ValueError('每个消息必须包含message')


@app.route('/send_message', methods=['POST'])
def send_message():
    try:
        data_list = request.json.get('data_list', [])
        try:
            validate_data(data_list)
        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400

        curdir = os.path.dirname(__file__)
        config_path = os.path.join(curdir, "data.json")
        with open(config_path, 'w', encoding='utf-8') as file:
            json.dump(data_list, file, ensure_ascii=False)
        logger.info(f"写入成功,写入内容{data_list}")

        return jsonify({'status': 'success', 'message': '发送成功'}), 200
    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}")
        return jsonify({'status': 'error', 'message': '服务器内部错误'}), 500


class FileWriter:
    def __init__(self):
        super().__init__()
        self.flask_thread = threading.Thread(target=self.run_flask_app)
        self.flask_thread.start()

    def run_flask_app(self):
        app.run(host='0.0.0.0', port=5688, debug=False)
