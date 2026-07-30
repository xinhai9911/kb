"""
app.py — 最小可部署服务（对应 [[entities/CI_CD 流水线实战]]）
演示：一个带 /healthz 和 /order 的 Flask 服务，供流水线冒烟测试与金丝雀验证。
"""
from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/healthz")
def healthz():
    return "ok", 200


@app.route("/order", methods=["POST"])
def place_order():
    user_id = request.json.get("user_id", "anon") if request.is_json else "anon"
    # 真实服务会下单、调下游；示例只回显
    return jsonify(order_id="o-12345", user_id=user_id), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
