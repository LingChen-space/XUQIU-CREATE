import os, sys, time
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
sys.path.insert(0, ".")

from app.heybox.hkey import fetch_hkey

print("Testing hkey...", flush=True)
start = time.time()
try:
    hkey, nonce, _time = fetch_hkey("/bbs/app/api/general/search/v1/")
    print(f"hkey={hkey[:20]}... nonce={nonce} time={_time} elapsed={time.time()-start:.1f}s")
except Exception as e:
    print(f"Failed after {time.time()-start:.1f}s: {type(e).__name__}: {e}")
