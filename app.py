# -*- coding: utf-8 -*-
"""黄河流域舆情独立系统入口。

本入口只提供服务端渲染的黄河流域 18 个视图，不加载长江流域、
用户中心、旧教学模块和其它蓝图的业务代码。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

from flask import Flask, jsonify, redirect, request, send_from_directory

load_dotenv(Path(__file__).with_name('.env'))


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY") or os.urandom(32)

    @app.route("/")
    def index():
        return redirect("/page/dashboard")

    @app.route("/page/dashboard")
    def dashboard():
        from service.dashboard import get_html

        force = request.args.get("force") == "1"
        html, err = get_html(force=force)
        if html is None:
            return (
                "<h3 style='color:#ff6b6b;font-family:monospace'>"
                "黄河流域仪表盘生成失败</h3><pre>%s</pre>"
                % (err or "未知错误"),
                500,
            )
        return html

    @app.route("/page/api/dashboard/refresh", methods=["POST"])
    def dashboard_refresh():
        from service.dashboard import refresh

        ok, msg = refresh(force=True)
        return jsonify({"status": "success" if ok else "error", "message": msg})

    frames_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_features", "frames")

    @app.route("/video/sheet/<path:filename>")
    def video_sheet(filename):
        if not os.path.splitext(filename)[1]:
            filename += ".jpg"
        return send_from_directory(frames_dir, filename)

    @app.route("/video_features/frames/<path:filename>")
    def video_frame(filename):
        return send_from_directory(frames_dir, filename)

    @app.route("/page/video_features/frames/<path:filename>")
    def video_frame_page_path(filename):
        return send_from_directory(frames_dir, filename)

    @app.route("/favicon.ico")
    def favicon():
        return ("", 204)

    @app.route("/page/chat", methods=["POST"])
    def chat():
        # 复用原系统聊天业务逻辑，仅按需加载，避免影响仪表盘冷启动。
        from view.page.page import ai_chat

        return ai_chat()

    @app.route("/page/api/data/refresh/status")
    def data_refresh_status():
        return jsonify({"status": "ok", "enabled": False, "running": False})

    @app.route("/page/api/data/refresh", methods=["POST"])
    def data_refresh_start():
        return jsonify({"status": "disabled"})

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok", "scope": "yellow-river"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5001")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )

