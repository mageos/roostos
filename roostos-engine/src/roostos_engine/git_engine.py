import os
import sys
import subprocess
from typing import List, Dict, Any, Optional

class GitEngine:
    """Orchestrates git version control operations for router configurations."""

    def __init__(self, repo_dir: str):
        self.repo_dir = repo_dir
        self._ensure_repo_exists()

    def _ensure_repo_exists(self) -> None:
        """Initializes git repo if missing and configures default git username/email."""
        git_dir = os.path.join(self.repo_dir, ".git")
        if not os.path.exists(git_dir):
            try:
                os.makedirs(self.repo_dir, exist_ok=True)
                subprocess.run(["git", "init"], cwd=self.repo_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Set dummy git credentials if not configured locally to prevent commit failures
                subprocess.run(["git", "config", "user.name", "RoostOS Router"], cwd=self.repo_dir, check=True)
                subprocess.run(["git", "config", "user.email", "admin@roostos.local"], cwd=self.repo_dir, check=True)
            except Exception as e:
                print(f"Warning: Failed to initialize Git repository in {self.repo_dir}: {e}", file=sys.stderr)

    def commit_changes(self, message: str) -> bool:
        """Stages all configuration YAML files and commits them with a description."""
        try:
            # Stage config files only
            subprocess.run(["git", "add", "*.yaml"], cwd=self.repo_dir, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Check if there are any changes staged
            status_res = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
            if not status_res.stdout.strip():
                print("No configuration changes detected. Skipping git commit.")
                return True

            subprocess.run(["git", "commit", "-m", message], cwd=self.repo_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"Warning: Git commit failed: {e}", file=sys.stderr)
            return False

    def get_commit_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the list of commit history entries (hash, author, date, message)."""
        try:
            # Format: hash|author|date|message
            res = subprocess.run(
                ["git", "log", f"-n", str(limit), "--pretty=format:%H|%an|%ad|%s", "--date=iso"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            history = []
            if res.stdout.strip():
                for line in res.stdout.split("\n"):
                    parts = line.split("|", 3)
                    if len(parts) == 4:
                        history.append({
                            "commit": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "description": parts[3]
                        })
            return history
        except Exception as e:
            print(f"Warning: Failed to retrieve Git log: {e}", file=sys.stderr)
            return []

    def rollback_to_commit(self, commit_hash: str) -> bool:
        """Rolls back config files to a specific commit point."""
        try:
            # Checkout YAML config files from specific commit
            subprocess.run(
                ["git", "checkout", commit_hash, "--", "*.yaml"],
                cwd=self.repo_dir,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Create a new commit to record the rollback action
            self.commit_changes(f"Rollback to configuration at commit {commit_hash[:8]}")
            return True
        except Exception as e:
            print(f"Warning: Git rollback failed: {e}", file=sys.stderr)
            return False
