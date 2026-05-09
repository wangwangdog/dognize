"""A-Stock 健康检查 + 访问监控"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime

def check(service: str, port: int, path: str = "/"):
    """检查服务是否可达"""
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return {"status": "ok" if resp.status < 400 else "error", "code": resp.status, "body_len": len(resp.read())}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = {
        "time": now,
        "chanlun_pro": check("chanlun-pro", 9900, "/tv/config"),
        "a_stock_backend": check("a-stock-backend", 9901, "/api/ping"),
        "a_stock_frontend": check("chanlun-pro", 9900, "/a-stock/"),
        "api_proxy": check("chanlun-pro", 9900, "/api/ping"),
    }
    
    # systemd 状态
    for svc in ["chanlun-pro", "a-stock-backend"]:
        try:
            r = subprocess.run(["systemctl", "--user", "is-active", f"{svc}.service"],
                             capture_output=True, text=True, timeout=5)
            results[f"systemd_{svc}"] = r.stdout.strip()
        except:
            results[f"systemd_{svc}"] = "error"
    
    # 端口监听
    try:
        r = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5)
        results["port_9900"] = "9900" in r.stdout
        results["port_9901"] = "9901" in r.stdout
    except:
        pass
    
    # 输出
    all_ok = all(
        v.get("status") == "ok" if isinstance(v, dict) else True
        for k, v in results.items() if k != "time"
    )
    
    print(f"[{now}] {'✅ ALL OK' if all_ok else '❌ HAS ISSUES'}")
    for k, v in results.items():
        icon = "✅" if isinstance(v, dict) and v.get("status") == "ok" else \
               "✅" if v is True else \
               "❌" if v is False or (isinstance(v, str) and v == "inactive") else \
               "⚠️" if isinstance(v, str) and v == "active" else \
               "❌" if isinstance(v, dict) and v.get("status") == "error" else \
               "ℹ️"
        if isinstance(v, dict):
            print(f"  {icon} {k}: {v.get('status')} (HTTP {v.get('code')})")
        else:
            print(f"  {icon} {k}: {v}")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
