import socket, time

print("Testing TCP connection to 127.0.0.1:8001...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect(("127.0.0.1", 8001))
    print("TCP connected")
    s.send(b"GET /api/monitor/health HTTP/1.1\r\nHost: 127.0.0.1:8001\r\nConnection: close\r\n\r\n")
    data = s.recv(4096)
    print("Response:", data.decode("utf-8", errors="replace")[:200])
except Exception as e:
    print(f"Failed: {type(e).__name__}: {e}")
finally:
    s.close()
