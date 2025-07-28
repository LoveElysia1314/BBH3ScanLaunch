from flask import Flask, abort, render_template, request
import logging
import sys
from config_utils import config_manager

# 创建Flask应用
fapp = Flask(__name__)

# 禁用Werkzeug日志
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# 禁用Flask启动信息
cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

@fapp.route("/")
def index():
    return render_template("index.html")

@fapp.route("/geetest")
def geetest():
    return render_template("geetest.html")

@fapp.route('/ret', methods=["POST"])
def ret():
    if not request.json:
        print("[INFO] 请求错误")
        abort(400)
    print(f"[INFO] Input = {request.json}")
    config_manager.cap = request.json
    return "1"