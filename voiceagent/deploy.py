"""Deploy from the repository root without printing or bundling credentials."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import shutil

from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--secrets-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    backend = dotenv_values(root / "backend/.env")
    cloud = dotenv_values(root / "voiceagent/.env")
    env = dict(os.environ)
    for key in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        if not cloud.get(key):
            raise SystemExit(f"Missing {key} in voiceagent/.env")
        env[key] = cloud[key]
    secrets = {key: cloud.get(key) or backend.get(key) for key in (
        "GNANI_API_KEY", "GROQ_API_KEY", "GROQ_MODEL", "CONVERSATION_MAX_SECONDS")}
    secrets["DATABASE_URL"] = cloud.get("DATABASE_URL") or backend.get("DATABASE_URL") or backend.get("poolurl") or backend.get("URL")
    secrets["DATABASE_SSL_ROOT_CERT"] = "/etc/secrets/prod-ca-2021.crt"
    for key in ("GNANI_API_KEY", "GROQ_API_KEY", "DATABASE_URL"):
        if not secrets.get(key):
            raise SystemExit(f"Missing {key}")
    certificate = root / "backend/prod-ca-2021.crt"
    if not certificate.is_file():
        raise SystemExit("Missing backend/prod-ca-2021.crt")
    with tempfile.TemporaryDirectory(prefix="opencall-deploy-") as temporary:
        build = Path(temporary) / "build"
        build.mkdir()
        ignore = shutil.ignore_patterns(".env", ".env.*", "__pycache__", "*.pyc", "data", "*.crt", "service.json", ".agents")
        for directory in ("backend/app", "backend/tools", "voiceagent"):
            shutil.copytree(root / directory, build / directory, ignore=ignore)
        shutil.copy2(root / "backend/requirements.txt", build / "backend/requirements.txt")
        shutil.copy2(root / "Dockerfile", build / "Dockerfile")
        shutil.copy2(root / ".dockerignore", build / ".dockerignore")
        (build / "requirements.txt").write_text("livekit-agents[codecs]==1.8.9\n-r backend/requirements.txt\n")
        config = root / "livekit.toml"
        if config.is_file():
            shutil.copy2(config, build / "livekit.toml")
        secret_file = Path(temporary) / "worker.env"
        secret_file.touch(mode=0o600)
        lines = []
        for key, value in secrets.items():
            if value:
                if "\n" in value or "\r" in value:
                    raise SystemExit(f"Unexpected multiline value for {key}")
                lines.append(f"{key}={value}")
        secret_file.write_text("\n".join(lines) + "\n")
        command = ["lk", "--yes", "agent", "update-secrets" if args.secrets_only else "deploy" if args.update else "create"]
        if not args.update and not args.secrets_only:
            command += ["--region", args.region]
        command += ["--secrets-file", str(secret_file), "--secret-mount", str(certificate)]
        result = subprocess.run(command, cwd=build, env=env)
        if (build / "livekit.toml").is_file():
            shutil.copy2(build / "livekit.toml", config)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
