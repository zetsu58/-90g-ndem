# Viral Futbol V2 - Google Colab tek hücre başlatıcı
# Bu dosyanın tamamını tek Colab hücresinde çalıştırabilirsiniz.

import os
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/zetsu58/-90g-ndem.git"
BRANCH = "viral-engine-v2"
ROOT = Path("/content/viral-futbol-v2")


def sh(*args, cwd=None):
    print("$", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


print("=== VIRAL FUTBOL V2 / FREE COLAB LAUNCHER ===")

# Private repo: Colab ortamında GH_TOKEN varsa HTTPS kimlik doğrulaması kullan.
token = os.environ.get("GH_TOKEN", "").strip()
clone_url = REPO
if token:
    clone_url = REPO.replace("https://", f"https://x-access-token:{token}@")

if not ROOT.exists():
    sh("git", "clone", "--depth", "1", "--branch", BRANCH, clone_url, ROOT)
else:
    sh("git", "fetch", "origin", BRANCH, cwd=ROOT)
    sh("git", "checkout", BRANCH, cwd=ROOT)
    sh("git", "reset", "--hard", f"origin/{BRANCH}", cwd=ROOT)

# Proje + test araçları
sh(sys.executable, "-m", "pip", "install", "-q", "-e", ".", cwd=ROOT)
sh(sys.executable, "scripts/colab_test_v2.py", cwd=ROOT)

print("\n✅ V2 kodu çekildi ve test aşaması tamamlandı.")
print("Repo:", ROOT)
print("Branch:", BRANCH)
print("\nDRY-RUN önerilir: gerçek render açmadan önce V2 haber seçimi/payload çıktısını kontrol et.")
print("Gerekli API anahtarlarını Colab Secrets/ortam değişkenlerinde tut; notebook içine yazma.")
