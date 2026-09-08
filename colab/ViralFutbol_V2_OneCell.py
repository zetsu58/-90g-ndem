# Viral Futbol V2 - Google Colab tek hücre başlatıcı
# Tek akış: repo güncelle -> test -> güvenli canlı-haber dry-run.

import os
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/zetsu58/-90g-ndem.git"
BRANCH = "viral-engine-v2"
ROOT = Path("/content/viral-futbol-v2")


def sh(*args, cwd=None, env=None):
    print("$", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


print("=== VIRAL FUTBOL V2 / FREE COLAB LAUNCHER ===")

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

# Kurulum ve ücretsiz yerel testler.
sh(sys.executable, "-m", "pip", "install", "-q", "-e", ".", cwd=ROOT)
sh(sys.executable, "scripts/colab_test_v2.py", cwd=ROOT)

# Testler geçmeden bu satıra gelinmez. Ardından gerçek güncel haberleri analiz
# ederiz; MPT submit/render kesin olarak kapalı tutulur.
dry_env = os.environ.copy()
dry_env["NEWS_DRY_RUN"] = "true"
dry_env["NEWS_LANGUAGES"] = "tr"
sh(sys.executable, "scripts/v2_dry_run.py", cwd=ROOT, env=dry_env)

print("\n✅ V2 test + canlı haber dry-run tamamlandı.")
print("Repo:", ROOT)
print("Branch:", BRANCH)
print("🔒 Render kapalı: NEWS_DRY_RUN=true")
print("Sonuçta PRODUCE olan haberlerin Viral Score, kaynak, senaryo promptu ve medya terimlerini kontrol et.")
print("Gerekli API anahtarlarını Colab Secrets/ortam değişkenlerinde tut; notebook içine yazma.")
