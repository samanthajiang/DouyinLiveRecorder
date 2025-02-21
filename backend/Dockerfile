FROM python:3.11-slim

WORKDIR /app

RUN echo "deb http://deb.debian.org/debian bookworm main contrib non-free" > /etc/apt/sources.list \
    && echo "deb-src http://deb.debian.org/debian bookworm main contrib non-free" >> /etc/apt/sources.list \
    && echo "deb http://security.debian.org/debian-security bookworm-security main contrib non-free" >> /etc/apt/sources.list \
    && echo "deb-src http://security.debian.org/debian-security bookworm-security main contrib non-free" >> /etc/apt/sources.list

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
RUN sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list

# 你的其他命令
# 更新软件包列表并安装依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 安装系统依赖
RUN pip --version

# 复制项目文件
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# 创建日志目录
RUN mkdir -p logs downloads

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"] 