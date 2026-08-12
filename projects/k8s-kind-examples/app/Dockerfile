# kind-examples 示例应用镜像
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8080
# exec 形式，便于信号传递与优雅退出
CMD ["python", "app.py"]
