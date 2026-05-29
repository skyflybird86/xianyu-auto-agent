def run_web_server(port=5000):
    """启动Web服务器"""
    import socket
    import platform
    
    # 尝试绑定端口，如果失败则尝试其他端口
    host = '127.0.0.1' if platform.system() == 'Windows' else '0.0.0.0'
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    available_port = port
    for p in [port, 8080, 8081, 8082]:
        try:
            sock.bind((host, p))
            available_port = p
            sock.close()
            break
        except:
            continue

    sock.close()

    # 确保templates目录存在
    if not os.path.exists('templates'):
        os.makedirs('templates')

    # 如果模板文件不存在，创建一个
    if not os.path.exists('templates/index.html'):
        with open('templates/index.html', 'w', encoding='utf-8') as f:
            f.write(build_html())

    print(f"Web服务器已启动，访问 http://localhost:{available_port}")
    if USE_SHARED_STATE and 'add_log' in dir():
        add_log("INFO", f"Web服务器已启动，访问 http://localhost:{available_port}")
    app.run(host=host, port=available_port, debug=False, use_reloader=False)
