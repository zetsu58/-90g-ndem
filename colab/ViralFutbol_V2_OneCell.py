# Viral Futbol V2 - Google Colab tek hücre başlatıcı
# Tek akış: repo güncelle -> test -> güvenli canlı-haber dry-run.

import os
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/zetsu58/-90g-ndem.git"
BRANCH = "viral-engine-v2"
ROOT = Path("/content/viral-futbol-v2")


def sh(*args, cwd=None, env=None, display=None):
    # display lets authenticated commands be logged without exposing secrets.
    shown = display if display is not None else " ".join(map(str, args))
    print("$", shown, flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


print("=== VIRAL FUTBOL V2 / FREE COLAB LAUNCHER ===")

token = os.environ.get("GH_TOKEN", "").strip()
auth_url = REPO if not token else REPO.replace("https://", f"https://x-access-token:{token}@")

if not ROOT.exists():
    sh(
        "git", "clone", "--depth", "1", "--branch", BRANCH, auth_url, ROOT,
        display=f"git clone --depth 1 --branch {BRANCH} <private-repo> {ROOT}",
    )
    # Never persist the token in .git/config after clone.
    sh("git", "remote", "set-url", "origin", REPO, cwd=ROOT)
else:
    # Fetch directly from the authenticated URL, but never print it. FETCH_HEAD
    # avoids temporarily writing the credential-bearing URL into the remote config.
    sh(
        "git", "fetch", "--depth", "1", auth_url, BRANCH,
        cwd=ROOT,
        display=f"git fetch --depth 1 <private-repo> {BRANCH}",
    )
    sh("git", "checkout", BRANCH, cwd=ROOT)
    sh("git", "reset", "--hard", "FETCH_HEAD", cwd=ROOT)
    sh("git", "remote", "set-url", "origin", REPO, cwd=ROOT)

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
print("🔒 GH_TOKEN komut çıktısına veya git remote adresine yazılmadı.")
print("Sonuçta PRODUCE olan haberlerin Viral Score, kaynak, senaryo promptu ve medya terimlerini kontrol et.")
print("Gerekli API anahtarlarını Colab Secrets/ortam değişkenlerinde tut; notebook içine yazma.")
