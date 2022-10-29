import argparse
import os
from subprocess import run
import shutil
import glob
import pdb
import yaml
from yaml import Loader

from typing import List, Tuple


def verify_path(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)

def check_python_ci_for_proxy(parsed_yaml):
    if "TestProxy" in parsed_yaml["extends"]["parameters"]:
        return True

    return False


def discover_python_status(work_dir: str, repo: str) -> List[Tuple[str, bool]]:
    if (not os.path.exists(os.path.join(work_dir, ".git"))):
        run(["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", "."], cwd=work_dir)

    packages = []

    # discover all service directories
    services = glob.glob(os.path.join(work_dir, "sdk/*/ci.yml"), recursive=True)

    for service_folder in services:
        globber = os.path.join(os.path.dirname(service_folder), "*", "setup.py")
        pkgs = glob.glob(globber, recursive=True)

        with open(service_folder, "r", encoding="utf-8") as f:
            parsed_yml = yaml.load(f, Loader=Loader)

        proxy_on = check_python_ci_for_proxy(parsed_yml)

        for pkg in pkgs:
            pkg_name = os.path.basename(os.path.dirname(pkg))
            packages.append((pkg_name, proxy_on))

    return packages


def discover_net_status(work_dir: str, repo: str) -> List[str]:
    pass


def discover_go_status(work_dir: str, repo: str) -> List[str]:
    pass


def discover_js_status(work_dir: str, repo: str) -> List[str]:
    pass


REPOS = {
    "Azure/azure-sdk-for-python": discover_python_status,
    "Azure/azure-sdk-for-js": discover_js_status,
    "Azure/azure-sdk-for-net": discover_net_status,
    "Azure/azure-sdk-for-go": discover_go_status,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generates a markdown report into the targeted work directory. This report highlights the total % of transition to the test-proxy."
    )

    parser.add_argument(
        "-w",
        "--work-directory",
        dest="work_directory",
        help="The directory where work will commence. If not provided, will create a folder under the current working directory.",
        required=False,
    )

    args = parser.parse_args()
    parsed_results = REPOS.copy()

    if not args.work_directory:
        args.work_directory = os.path.join(os.getcwd(), ".work")

    if not os.path.exists(args.work_directory):
        os.makedirs(args.work_directory)

    # walk all the repos, do the needful on each
    for repo in REPOS.keys():
        target_path = os.path.join(args.work_directory, repo.replace("/", "-"))
        verify_path(target_path)
        parsed_results[repo] = REPOS[repo](target_path, repo)

    print("# Test-Proxy Conversation Report")
    for repo in parsed_results.keys():
        if parsed_results[repo]:
            print(f"## {repo}")
            on_proxy = [package for package in parsed_results[repo] if package[1]]
            not_on_proxy = [package for package in parsed_results[repo] if not package[1]]
            print(f"{len(on_proxy)} out of {len(parsed_results[repo])} packages have been converted to the test-proxy.")
