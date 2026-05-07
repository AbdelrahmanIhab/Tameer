"""
Upload all Space files to HuggingFace.
Usage:
    python deploy_to_hf.py --repo your-username/tameer-ml
"""

import argparse
from huggingface_hub import HfApi

FILES = [
    "app.py",
    "models.py",
    "requirements.txt",
    "Dockerfile",
    "efficientnet_b0.pth",
    "ppo.pth",
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="HF repo id, e.g. yourname/tameer-ml")
    args = parser.parse_args()

    api = HfApi()
    for fname in FILES:
        print(f"Uploading {fname} ...")
        api.upload_file(
            path_or_fileobj=fname,
            path_in_repo=fname,
            repo_id=args.repo,
            repo_type="space",
        )
        print(f"  done.")

    print(f"\nAll files uploaded.")
    print(f"Space: https://huggingface.co/spaces/{args.repo}")

if __name__ == "__main__":
    main()
