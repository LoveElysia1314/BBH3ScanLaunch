# -*- coding: utf-8 -*-
"""认证功能使用的验证码回调服务器。"""

import logging
import threading
from flask import Flask, abort, render_template, request


def create_captcha_server(template_dir: str, on_captcha, on_complete=None):
    """
    创建一个独立的验证码回调服务实例。

    Parameters
    ----------
    template_dir: str
        Flask 模板目录。
    on_captcha:
        收到验证码回传后的回调，接收解析后的 json body。
    """

    fapp = Flask(__name__, template_folder=template_dir)

    @fapp.route("/")
    def index():
        return render_template("index.html")

    @fapp.route("/geetest")
    def geetest():
        return render_template("geetest.html")

    @fapp.route("/ret", methods=["POST"])
    def ret():
        if not request.json:
            logging.info("请求错误")
            abort(400)
        input_data = request.json
        logging.debug(f"验证码数据接收: {input_data}")
        on_captcha(input_data)
        # 避免与当前请求上下文/线程冲突，延迟触发后续登录流程
        if on_complete:
            threading.Timer(1.0, on_complete).start()
        return "1"

    return fapp
